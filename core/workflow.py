# -*- coding: utf-8 -*-
from typing import Dict, List, Optional

from core.context import Context
from core.node import Node
from storage.repositories import get_node_status
from utils.logger import logger


class Workflow:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.name] = node

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges.setdefault(from_node, []).append(to_node)

    async def run(self, start_node: str, ctx: Context) -> Context:
        stack = [start_node]

        while stack:
            node_name = stack.pop()
            node = self.nodes[node_name]

            logger.info(f"节点开始: [{node_name}]")
            ctx = await node.run(ctx)

            next_nodes = self.edges.get(node_name, [])
            output_keys = [self.nodes[n].output_key for n in next_nodes]
            logger.info(f"节点完成: [{node_name}], 输出键: {output_keys}")

            for next_node in reversed(next_nodes):
                stack.append(next_node)

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
        if last_completed and last_completed in execution_order:
            start_idx = execution_order.index(last_completed) + 1
        
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
