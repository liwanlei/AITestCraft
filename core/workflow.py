# -*- coding: utf-8 -*-
import json
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from config.config import Config
from core.schemas import TESTCASE_SCHEMA, REVIEW_SCHEMA, COVERAGE_SCHEMA, GAP_SCHEMA
from core.context import Context
from core.node import Node
from utils.json_utils import safe_loads
from utils.logger import logger
from core.retry import should_trigger_gap_filler


def _filter_dict(data: Dict[str, Any], keys: tuple) -> Dict[str, Any]:
    """过滤字典，只保留指定的键"""
    return {k: v for k, v in data.items() if k in keys}


def _filter_requirement(req: Any) -> Any:
    """过滤需求数据，只保留关键字段"""
    if isinstance(req, dict):
        return _filter_dict(req, Config.REQUIREMENT_FILTER_KEYS)
    return req


def _filter_testpoints(tps: Any) -> Any:
    """过滤测试点数据，只保留关键字段"""
    if isinstance(tps, list):
        return [_filter_dict(tp, Config.TESTPOINT_FILTER_KEYS) for tp in tps if isinstance(tp, dict)]
    return tps


class NodeConfig(NamedTuple):
    name: str
    agent: Any
    input_fn: Callable[[Context], str]
    output_key: str
    schema: Optional[Dict] = None
    condition: Optional[Callable[[Context], bool]] = None


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


def _get_filtered_testpoints(ctx: Context) -> List[Dict[str, Any]]:
    """获取过滤后的测试点，避免重复解析"""
    if "filtered_testpoints" not in ctx:
        raw = ctx.get("unique_testpoints", "{}")
        parsed = safe_loads(raw)
        ctx.set("filtered_testpoints", _filter_testpoints(parsed.get("unique_testpoints", [])))
    return ctx["filtered_testpoints"]


def _build_requirement_input(ctx: Context) -> str:
    """构建需求解析节点的输入"""
    return ctx["task"]


def _build_testpoint_input(ctx: Context) -> str:
    """构建测试点提取节点的输入"""
    return json.dumps({"requirement": _filter_requirement(ctx["requirement"])}, ensure_ascii=False)


def _build_dedup_input(ctx: Context) -> str:
    """构建测试点去重节点的输入"""
    return json.dumps({"testpoints": ctx["testpoint"]})


def _build_testcase_input(ctx: Context) -> str:
    """构建测试用例生成节点的输入"""
    return json.dumps({"testpoints": _get_filtered_testpoints(ctx)}, ensure_ascii=False)


def _build_review_coverage_input(ctx: Context, input_type: str) -> str:
    """构建审查和覆盖率节点的公共输入
    
    Args:
        ctx: 上下文对象
        input_type: 输入类型（'review' 或 'coverage'）
    
    Returns:
        JSON 字符串形式的输入数据
    """
    data = {
        "requirement": _filter_requirement(ctx.get("requirement", {})),
        "testpoints": _get_filtered_testpoints(ctx),
    }
    
    cases = ctx.get("testcase")
    if input_type == "review":
        data["cases"] = cases or {}
    elif cases:
        data["cases"] = cases
    
    return json.dumps(data, ensure_ascii=False)


def _build_review_input(ctx: Context) -> str:
    """构建测试用例审查节点的输入"""
    return _build_review_coverage_input(ctx, "review")


def _build_coverage_input(ctx: Context) -> str:
    """构建覆盖率分析节点的输入"""
    return _build_review_coverage_input(ctx, "coverage")


def _build_gap_input(ctx: Context) -> str:
    """构建缺口填充节点的输入"""
    return json.dumps({
        "cases": ctx.get("testcase", {}),
        "issues": ctx.get("review", {}).get("issues", []),
        "coverage_missing": ctx.get("coverage", {}).get("missing", []),
        "risk_level": ctx.get("review", {}).get("risk_level", "low"),
    })


def _gap_condition(ctx: Context) -> bool:
    """判断是否需要执行缺口填充节点"""
    return should_trigger_gap_filler({**ctx.get("review", {}), **ctx.get("coverage", {})})


def build_workflow(agents: Dict[str, Any]) -> Workflow:
    """构建工作流
    
    Args:
        agents: 代理字典，包含各节点的执行代理
    
    Returns:
        配置好的工作流对象
    """
    wf = Workflow()

    # 节点配置列表
    node_configs = [
        NodeConfig("requirement", agents["requirement"], _build_requirement_input, "requirement"),
        NodeConfig("testpoint", agents["testpoint"], _build_testpoint_input, "testpoint"),
        NodeConfig("dedup", agents["dedup"], _build_dedup_input, "unique_testpoints"),
        NodeConfig("testcase", agents["testcase"], _build_testcase_input, "testcase", TESTCASE_SCHEMA),
        NodeConfig("review", agents["review"], _build_review_input, "review", REVIEW_SCHEMA),
        NodeConfig("coverage", agents["coverage"], _build_coverage_input, "coverage", COVERAGE_SCHEMA),
        NodeConfig("gap", agents["gap"], _build_gap_input, "final_cases", GAP_SCHEMA, _gap_condition),
    ]

    for cfg in node_configs:
        wf.add_node(Node(
            name=cfg.name,
            agent=cfg.agent,
            input_fn=cfg.input_fn,
            output_key=cfg.output_key,
            schema=cfg.schema,
            condition=cfg.condition
        ))

    # 边配置列表
    edges = [
        ("requirement", "testpoint"),
        ("testpoint", "dedup"),
        ("dedup", "testcase"),
        ("testcase", "review"),
        ("review", "coverage"),
        ("coverage", "gap"),
    ]

    # 创建边
    for from_node, to_node in edges:
        wf.add_edge(from_node, to_node)

    return wf
