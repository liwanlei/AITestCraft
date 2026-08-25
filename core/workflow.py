# -*- coding: utf-8 -*-
from typing import Any, Dict, List

from core.context import Context
from core.node import Node
from utils.logger import logger


class Workflow:
    """
    工作流引擎，管理节点注册与执行顺序

    职责：
    - 节点注册（add_node）与边注册（add_edge）
    - 单节点执行（run_single_node）
    - 串行执行（run）
    - 执行顺序计算（_get_execution_order）

    并行执行和断点恢复功能分别在 parallel_workflow 和 checkpoint_workflow 模块中。
    """

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

    async def run_single_node(self, node_name: str, ctx: Context) -> Context:
        node = self.nodes[node_name]
        logger.info(f"节点开始: [{node_name}]")
        ctx = await node.run(ctx)
        logger.info(f"节点完成: [{node_name}]")
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