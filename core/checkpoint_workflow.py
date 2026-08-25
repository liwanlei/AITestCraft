# -*- coding: utf-8 -*-
from typing import Any, Dict, List

from core.context import Context
from core.workflow import Workflow
from storage.repositories import get_node_status
from utils.logger import logger


async def run_from_checkpoint(workflow: Workflow, start_node: str, ctx: Context) -> Context:
    """
    从断点恢复执行，跳过已完成的节点

    当任务因异常中断后，通过数据库中的节点状态记录，
    自动跳过已完成节点，仅从断点处继续执行。

    Args:
        workflow: 工作流实例
        start_node: 起始节点名称
        ctx: 执行上下文

    Returns:
        执行后的上下文
    """
    task_id = ctx.get("task_id", "")

    node_statuses = get_node_status(task_id)
    is_resuming = any(s.get("status") == "completed" for s in node_statuses.values())
    logger.info(f"任务 {task_id[:8]}..., 已完成节点: {len(node_statuses)}, 断点恢复: {is_resuming}")

    last_completed = None
    for node_name, status_info in node_statuses.items():
        if status_info.get("status") == "completed":
            if last_completed is None or status_info.get("updated_at", "") > node_statuses.get(last_completed, {}).get("updated_at", ""):
                last_completed = node_name

    if last_completed:
        logger.info(f"最后一个完成节点: [{last_completed}], 将从其后续节点恢复")
    else:
        logger.info(f"未找到已完成节点，将从头开始执行")

    execution_order = _get_execution_order(workflow, start_node)

    start_idx = 0
    if last_completed:
        node_to_index = {name: i for i, name in enumerate(execution_order)}
        completed_idx = node_to_index.get(last_completed)
        if completed_idx is not None:
            start_idx = completed_idx + 1

    logger.info(f"加载已完成节点的缓存结果...")
    for node_name in execution_order[:start_idx]:
        if node_name in node_statuses:
            status_info = node_statuses[node_name]
            if status_info.get("status") == "completed":
                cached_result = status_info.get("result")
                if cached_result and isinstance(cached_result, dict) and "output" in cached_result:
                    node = workflow.nodes.get(node_name)
                    if node:
                        output_key = node.output_key
                        ctx.set(output_key, cached_result["output"])
                        logger.info(f"已加载节点 [{node_name}] 的缓存结果到 {output_key}")

    remaining_nodes = execution_order[start_idx:]
    logger.info(f"需要执行的节点: {remaining_nodes}")

    for node_name in remaining_nodes:
        node = workflow.nodes[node_name]

        if node_name in node_statuses and node_statuses[node_name].get("status") == "completed":
            cached_result = node_statuses[node_name].get("result")
            if cached_result and isinstance(cached_result, dict) and "output" in cached_result:
                output_key = node.output_key
                ctx.set(output_key, cached_result["output"])
                logger.info(f"节点 [{node_name}] 使用缓存结果，跳过执行")
                continue

        logger.info(f"节点开始: [{node_name}]{' (断点恢复)' if is_resuming else ''}")
        ctx = await node.run(ctx)

        next_nodes = workflow.edges.get(node_name, [])
        output_keys = [workflow.nodes[n].output_key for n in next_nodes]
        logger.info(f"节点完成: [{node_name}], 输出键: {output_keys}")

    return ctx


def _get_execution_order(workflow: Workflow, start_node: str) -> List[str]:
    """
    获取节点执行顺序（DFS）

    Args:
        workflow: 工作流实例
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

        next_nodes = workflow.edges.get(node_name, [])
        for next_node in next_nodes:
            dfs(next_node)

    dfs(start_node)
    return order