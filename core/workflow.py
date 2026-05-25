# -*- coding: utf-8 -*-
import asyncio
from typing import Any, Dict, List, Optional

from core.context import Context
from core.node import Node
from core.retry import run_with_retry
from storage.repositories import get_node_status, update_node_status
from utils.logger import logger
from utils.token_utils import extract_usage_info, extract_token_counts


class Workflow:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.name] = node

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges.setdefault(from_node, []).append(to_node)

    async def run(self, start_node: str, ctx: Context) -> Context:
        current = start_node

        while current:
            node = self.nodes[current]
            logger.info(f"节点开始: [{current}]")
            ctx = await node.run(ctx)

            next_nodes = self.edges.get(current, [])
            output_keys = [self.nodes[n].output_key for n in next_nodes]
            logger.info(f"节点完成: [{current}], 输出键: {output_keys}")

            if next_nodes:
                current = next_nodes[0]
            else:
                current = None

        return ctx

    async def run_from_checkpoint(self, start_node: str, ctx: Context) -> Context:
        """
        从断点恢复执行，跳过已完成的节点
        
        Args:
            start_node: 起始节点名称
            ctx: 执行上下文
            
        Returns:
            执行后的上下文
        """
        task_id = ctx.get("task_id", "")
        
        # 获取节点状态
        node_statuses = get_node_status(task_id)
        logger.info(f"从断点恢复: 任务 {task_id[:8]}..., 已完成节点: {len(node_statuses)}")
        
        # 找出最后一个完成的节点
        last_completed = None
        for node_name, status_info in node_statuses.items():
            if status_info.get("status") == "completed":
                # 尝试获取 updated_at 确定顺序
                if last_completed is None or status_info.get("updated_at", "") > node_statuses.get(last_completed, {}).get("updated_at", ""):
                    last_completed = node_name
        
        if last_completed:
            logger.info(f"最后一个完成节点: [{last_completed}], 将从其后续节点恢复")
        else:
            logger.info(f"未找到已完成节点，将从头开始执行")
        
        # 构建节点执行顺序
        execution_order = self._get_execution_order(start_node)
        
        # 确定起始索引
        start_idx = 0
        if last_completed:
            node_to_index = {name: i for i, name in enumerate(execution_order)}
            completed_idx = node_to_index.get(last_completed)
            if completed_idx is not None:
                start_idx = completed_idx + 1
        
        # 加载所有已完成节点的输出到上下文（关键修复）
        logger.info(f"加载已完成节点的缓存结果...")
        for node_name in execution_order[:start_idx]:
            if node_name in node_statuses:
                status_info = node_statuses[node_name]
                if status_info.get("status") == "completed":
                    cached_result = status_info.get("result")
                    if cached_result and isinstance(cached_result, dict) and "output" in cached_result:
                        node = self.nodes.get(node_name)
                        if node:
                            output_key = node.output_key
                            ctx.set(output_key, cached_result["output"])
                            logger.info(f"已加载节点 [{node_name}] 的缓存结果到 {output_key}")
        
        # 从断点开始执行
        remaining_nodes = execution_order[start_idx:]
        logger.info(f"需要执行的节点: {remaining_nodes}")
        
        for node_name in remaining_nodes:
            node = self.nodes[node_name]
            
            # 检查节点是否已存在已完成状态（可能在之前的检查中遗漏）
            if node_name in node_statuses and node_statuses[node_name].get("status") == "completed":
                cached_result = node_statuses[node_name].get("result")
                if cached_result and isinstance(cached_result, dict) and "output" in cached_result:
                    output_key = node.output_key
                    ctx.set(output_key, cached_result["output"])
                    logger.info(f"节点 [{node_name}] 使用缓存结果，跳过执行")
                    continue
            
            logger.info(f"节点开始: [{node_name}] (从断点恢复)")
            ctx = await node.run(ctx)
            
            next_nodes = self.edges.get(node_name, [])
            output_keys = [self.nodes[n].output_key for n in next_nodes]
            logger.info(f"节点完成: [{node_name}], 输出键: {output_keys}")

        return ctx

    def _get_execution_order(self, start_node: str) -> List[str]:
        """
        获取节点执行顺序（DFS）
        
        Args:
            start_node: 起始节点
            
        Returns:
            节点名称列表，按执行顺序排列
        """
        visited = set()
        order = []
        
        def dfs(node_name: str):
            if node_name in visited:
                return
            visited.add(node_name)
            order.append(node_name)
            
            next_nodes = self.edges.get(node_name, [])
            for next_node in next_nodes:
                dfs(next_node)
        
        dfs(start_node)
        return order

    async def run_single_node(self, node_name: str, ctx: Context) -> Context:
        node = self.nodes[node_name]
        logger.info(f"节点开始: [{node_name}]")
        ctx = await node.run(ctx)
        logger.info(f"节点完成: [{node_name}]")
        return ctx

    async def run_parallel(self, node_name: str, ctx: Context, inputs: List[Dict[str, str]], output_key: str) -> Context:
        task_id = ctx.get("task_id", "")
        node = self.nodes[node_name]

        update_node_status(task_id, node_name, "running")
        ctx["token_stats"].ensure_node(node_name)

        async def _run_single_module(item: Dict[str, str]) -> tuple:
            module_id = item["module_id"]
            payload = item["input"]
            try:
                logger.info(f"执行 [{node_name}] 模块: {module_id}")
                result = await run_with_retry(
                    node.agent, payload,
                    retries=node.max_retry,
                    timeout=node.timeout,
                    model_settings=node.model_settings
                )
                raw = result.text
                raw_str = str(raw).strip() if raw else ""
                usage_info = extract_usage_info(result)
                return module_id, raw_str, usage_info
            except Exception as e:
                logger.error(f"执行 [{node_name}] 模块 {module_id} 失败: {e}")
                return module_id, "", None

        if not inputs:
            logger.warning(f"执行 [{node_name}] 无输入模块，跳过并行执行")
            update_node_status(task_id, node_name, "completed", {"output": {}})
            ctx.set("module_testpoints", {})
            return ctx

        if len(inputs) == 1:
            results = [await _run_single_module(inputs[0])]
        else:
            logger.info(f"并行执行 [{node_name}]，模块数: {len(inputs)}")
            results = await asyncio.gather(*[_run_single_module(item) for item in inputs])

        module_results = {}
        total_input_tokens = 0
        total_output_tokens = 0
        failed_count = 0

        for module_id, raw_str, usage_info in results:
            if not raw_str:
                failed_count += 1
            module_results[module_id] = raw_str
            if usage_info:
                input_tokens, output_tokens = extract_token_counts(usage_info)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                ctx["token_stats"].add(node_name, {
                    "input_token_count": input_tokens,
                    "output_token_count": output_tokens,
                    "total_token_count": input_tokens + output_tokens
                })

        if failed_count > 0:
            total_modules = len(inputs)
            failure_rate = failed_count / total_modules
            logger.warning(
                f"执行 [{node_name}] 部分模块失败: {failed_count}/{total_modules} "
                f"(失败率 {failure_rate:.0%})"
            )
            if failure_rate > 0.5:
                logger.error(
                    f"执行 [{node_name}] 超过半数模块失败 ({failed_count}/{total_modules})，"
                    f"后续节点可能产生不完整结果"
                )

        token_usage_data = None
        if total_input_tokens > 0 or total_output_tokens > 0:
            token_usage_data = {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens
            }

        ctx.set("module_testpoints", module_results)
        update_node_status(task_id, node_name, "completed", {"output": module_results}, token_usage=token_usage_data)
        logger.info(f"执行 [{node_name}] 完成，模块数: {len(module_results)}")

        return ctx
