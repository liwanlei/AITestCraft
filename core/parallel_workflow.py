# -*- coding: utf-8 -*-
import asyncio
from typing import Any, Dict, List

from core.context import Context
from core.retry import run_with_retry
from core.workflow import Workflow
from storage.repositories import update_node_status
from utils.logger import logger
from utils.token_utils import extract_usage_info, extract_token_counts


async def run_parallel(workflow: Workflow, node_name: str, ctx: Context, inputs: List[Dict[str, str]], output_key: str) -> Context:
    """
    并行执行指定节点

    将输入列表分发给 agent 并发执行，汇总结果后存入上下文。
    适用于模块拆分后并行提取测试点等场景。

    Args:
        workflow: 工作流实例
        node_name: 要并行执行的节点名称
        ctx: 执行上下文
        inputs: 输入列表，每个元素为 {"module_id": ..., "input": ...}
        output_key: 输出在上下文中的键名

    Returns:
        执行后的上下文
    """
    task_id = ctx.get("task_id", "")
    node = workflow.nodes[node_name]

    update_node_status(task_id, node_name, "running")
    ctx["token_stats"].ensure_node(node_name)

    async def _run_single_module(item: Dict[str, str]) -> tuple:
        module_id = item["module_id"]
        payload = item["input"]
        try:
            input_preview = payload
            input_suffix = f"\n(，共 {len(payload)} 字符)"
            logger.info(f"节点 [{node_name}] 模块 [{module_id}] 输入内容 ({len(payload)} 字符):\n{input_preview}{input_suffix}")

            result = await run_with_retry(
                node.agent, payload,
                retries=node.max_retry,
                timeout=node.timeout,
                model_settings=node.model_settings
            )
            raw = result.text
            raw_str = str(raw).strip() if raw else ""

            output_preview = raw_str
            output_suffix = f"\n(，共 {len(raw_str)} 字符)"
            logger.info(f"节点 [{node_name}] 模块 [{module_id}] 输出内容 ({len(raw_str)} 字符):\n{output_preview}{output_suffix}")

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