# =========================
# Workflow（DAG引擎）
# =========================
import json
from typing import Dict, List

from config.schemas import TESTCASE_SCHEMA, REVIEW_SCHEMA, COVERAGE_SCHEMA, GAP_SCHEMA
from core.context import Context
from core.node import Node
from utils.json_utils import safe_loads
from utils.logger import logger
from utils.retry import should_trigger


class Workflow:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, node: Node):
        self.nodes[node.name] = node

    def add_edge(self, from_node: str, to_node: str):
        self.edges.setdefault(from_node, []).append(to_node)

    async def _run_node(self, name: str, ctx: Context):
        node = self.nodes[name]
        logger.info(f"node start: {name}")

        # 1. 执行当前节点
        ctx = await node.run(ctx)

        # 2. 顺序执行后继节点（关键：单线程）
        next_nodes = self.edges.get(name, [])
        logger.info(f"node finish: {name}")
        logger.info(ctx)
        for n in next_nodes:
            ctx = await self._run_node(n, ctx)

        return ctx

    async def run(self, start_node: str, ctx: Context):
        return await self._run_node(start_node, ctx)

def build_workflow(agents):
    wf = Workflow()

    # -------- requirement --------
    wf.add_node(Node(
        "requirement",
        agents["requirement"],
        lambda ctx: ctx["task"],
        "requirement"
    ))

    # -------- testpoint --------
    wf.add_node(Node(
        "testpoint",
        agents["testpoint"],
        lambda ctx: json.dumps({"requirement": ctx["requirement"]}),
        "testpoint"
    ))

    # -------- dedup --------
    wf.add_node(Node(
        "dedup",
        agents["dedup"],
        lambda ctx: json.dumps({"testpoints": ctx["testpoint"]}),
        "unique_testpoints"
    ))

    # -------- testcase --------
    wf.add_node(Node(
        "testcase",
        agents["testcase"],
        lambda ctx: json.dumps({"testpoints": safe_loads(ctx["unique_testpoints"])["unique_testpoints"]}),
        "testcase",
        schema=TESTCASE_SCHEMA
    ))
    # -------- review --------
    wf.add_node(Node(
        "review",
        agents["review"],
        lambda ctx: json.dumps({
            "requirement": ctx.get("task"),
            "testpoints": safe_loads(ctx["unique_testpoints"])["unique_testpoints"],
            "cases": ctx.get("testcase", {})
        }, ensure_ascii=False),
        "review",
        schema=REVIEW_SCHEMA
    ))
    # -------- coverage --------
    wf.add_node(Node(
        "coverage",
        agents["coverage"],
        lambda ctx: json.dumps({
            "requirement": ctx.get("task"),
            "testpoints": safe_loads(ctx["unique_testpoints"])["unique_testpoints"],
            "cases": ctx.get("testcase")
        }, ensure_ascii=False),
        "coverage",
        schema=COVERAGE_SCHEMA
    ))
    # -------- gap --------
    wf.add_node(Node(
        "gap",
        agents["gap"],
        lambda ctx: json.dumps({
            "cases": ctx.get("testcase", {}),
            "issues": ctx.get("review", {}).get("issues", []),
            "coverage_missing": ctx.get("coverage", {}).get("missing", []),
            "risk_level": ctx.get("review", {}).get("risk_level", "low"),
        }),
        "final_cases",
        condition=lambda ctx: should_trigger(
            {**ctx.get("review", {}), **ctx.get("coverage", {})}
        ),
        schema=GAP_SCHEMA
    ))

    # DAG关系
    wf.add_edge("requirement", "testpoint")
    wf.add_edge("testpoint", "dedup")
    wf.add_edge("dedup", "testcase")
    wf.add_edge("testcase", "review")
    wf.add_edge("review", "coverage")
    wf.add_edge("coverage", "gap")

    return wf