# -*- coding: utf-8 -*-
import json
import re
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from config.config import Config
from core.schemas import TESTCASE_SCHEMA, GAP_SCHEMA
from core.context import Context
from core.node import Node
from core.workflow import Workflow
from utils.logger import logger

# 工作流节点执行顺序
WORKFLOW_NODE_ORDER = ["requirement", "testpoint", "aggregator", "testcase", "review", "coverage", "gap"]


class NodeConfig(NamedTuple):
    name: str
    agent: Any
    input_fn: Callable[[Context], str]
    output_key: str
    schema: Optional[Dict] = None
    condition: Optional[Callable[[Context], bool]] = None
    model_settings: Optional[Dict] = None
    output_format: str = "json"


def _build_requirement_input(ctx: Context) -> str:
    return ctx["task"]


def _build_testpoint_input(ctx: Context) -> str:
    return ctx.get("requirement", "")


def _build_aggregator_input(ctx: Context) -> str:
    module_testpoints = ctx.get("module_testpoints")
    if isinstance(module_testpoints, str):
        return module_testpoints
    if isinstance(module_testpoints, dict) and module_testpoints:
        parts = []
        for module_id, testpoints in module_testpoints.items():
            parts.append(f"### {module_id}\n\n{testpoints}")
        return "\n\n".join(parts)
    return ctx.get("testpoint", "")


def _get_testpoints_text(ctx: Context) -> str:
    grouped = ctx.get("grouped_testpoints", "")
    if grouped:
        return grouped
    return ctx.get("unique_testpoints", "")


def _build_testcase_input(ctx: Context) -> str:
    grouped = ctx.get("grouped_testpoints", "")
    if grouped:
        return grouped
    testpoints = ctx.get("testpoint", "")
    if testpoints:
        return testpoints
    return ctx.get("unique_testpoints", "")


def _build_review_coverage_input(ctx: Context) -> str:
    parts = []
    requirement = ctx.get("requirement", "")
    parts.append(f"## 需求信息\n{requirement}")

    grouped = ctx.get("grouped_testpoints", "")
    if grouped:
        parts.append(f"## 测试点\n{grouped}")
    else:
        testpoints = _get_testpoints_text(ctx)
        parts.append(f"## 测试点\n{testpoints}")

    cases = ctx.get("testcase")
    if cases:
        parts.append(f"## 测试用例\n{_to_text(cases)}")

    return "\n\n".join(parts)


def _extract_risk_level(coverage_text: str) -> str:
    if re.search(r"风险等级\s*[:：]\s*high", coverage_text, re.IGNORECASE):
        return "high"
    if re.search(r"风险等级\s*[:：]\s*medium", coverage_text, re.IGNORECASE):
        return "medium"
    return "low"


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning(f"_to_text 序列化失败: {e}")
        return default


def _build_gap_input(ctx: Context) -> str:
    cases_text = _to_text(ctx.get("testcase"), "[]")
    review_text = _to_text(ctx.get("review", ""))
    coverage_text = _to_text(ctx.get("coverage", ""))
    risk_level = _extract_risk_level(coverage_text)

    parts = [f"## 测试用例\n{cases_text}"]
    parts.append(f"## 评审结果\n{review_text}")
    parts.append(f"## 覆盖率分析\n{coverage_text}")
    parts.append(f"## 风险等级\n{risk_level}")
    return "\n\n".join(parts)


def _gap_condition(ctx: Context) -> bool:
    review_text = _to_text(ctx.get("review", ""))
    coverage_text = _to_text(ctx.get("coverage", ""))

    try:
        high_risk = bool(re.search(r"风险等级\s*[:：]\s*high", coverage_text, re.IGNORECASE))
        medium_risk = bool(re.search(r"风险等级\s*[:：]\s*medium", coverage_text, re.IGNORECASE))
        has_issues = bool(re.search(r"问题列表", review_text)) and bool(re.search(r"^\s*-\s+\S", review_text, re.MULTILINE))
        has_missing = bool(re.search(r"未覆盖场景", coverage_text)) and bool(re.search(r"^\s*-\s+\S", coverage_text, re.MULTILINE))
    except re.error as e:
        logger.warning(f"_gap_condition 正则匹配异常: {e}")
        return False

    return high_risk or medium_risk or has_issues or has_missing


def _parse_modules(requirement_text: str) -> List[Dict[str, str]]:
    modules = []
    pattern = re.compile(
        r'\|\s*(M\d+)\s*\|\s*([^|]+?)\s*\|\s*(P[012])\s*\|\s*([^|]+?)\s*\|'
    )
    for match in pattern.finditer(requirement_text):
        modules.append({
            "id": match.group(1).strip(),
            "name": match.group(2).strip(),
            "priority": match.group(3).strip(),
            "content": match.group(4).strip()
        })

    detail_sections = re.split(r'\n(?=##\s+M\d+\s*:)', requirement_text)
    detail_map = {}
    for section in detail_sections:
        detail_match = re.match(r'^##\s+(M\d+)\s*:\s*(.+)', section.strip())
        if detail_match:
            module_id = detail_match.group(1).strip()
            detail_map[module_id] = section.strip()

    for m in modules:
        if m["id"] in detail_map:
            m["detail"] = detail_map[m["id"]]
        else:
            m["detail"] = f"## {m['id']}: {m['name']}\n\n{m['content']}"

    return modules


def _build_module_testpoint_inputs(ctx: Context) -> List[Dict[str, str]]:
    requirement_text = ctx.get("requirement", "")
    modules = _parse_modules(requirement_text)
    if len(modules) <= Config.MODULE_SPLIT_THRESHOLD:
        return [{"module_id": "ALL", "input": requirement_text}]
    return [
        {
            "module_id": m["id"],
            "input": m["detail"]
        }
        for m in modules
    ]


def build_workflow(agents: Dict[str, Any], model_configs: Optional[Dict[str, Dict]] = None) -> Workflow:
    if model_configs is None:
        model_configs = {}

    wf = Workflow()

    node_configs = [
        NodeConfig("requirement", agents["requirement"], _build_requirement_input, "requirement", output_format="md"),
        NodeConfig("testpoint", agents["testpoint"], _build_testpoint_input, "testpoint", output_format="md"),
        NodeConfig("aggregator", agents["aggregator"], _build_aggregator_input, "grouped_testpoints", output_format="md"),
        NodeConfig("testcase", agents["testcase"], _build_testcase_input, "testcase", output_format="md"),
        NodeConfig("review", agents["review"], _build_review_coverage_input, "review", output_format="md",
                   model_settings=model_configs.get("review", {}).get("settings")),
        NodeConfig("coverage", agents["coverage"], _build_review_coverage_input, "coverage", output_format="md",
                   model_settings=model_configs.get("coverage", {}).get("settings")),
        NodeConfig("gap", agents["gap"], _build_gap_input, "final_cases", GAP_SCHEMA, _gap_condition),
    ]

    for cfg in node_configs:
        wf.add_node(Node(
            name=cfg.name,
            agent=cfg.agent,
            input_fn=cfg.input_fn,
            output_key=cfg.output_key,
            schema=cfg.schema,
            condition=cfg.condition,
            model_settings=cfg.model_settings,
            output_format=cfg.output_format
        ))

    edges = [
        ("requirement", "testpoint"),
        ("testpoint", "aggregator"),
        ("aggregator", "testcase"),
        ("testcase", "review"),
        ("review", "coverage"),
        ("coverage", "gap"),
    ]

    for from_node, to_node in edges:
        wf.add_edge(from_node, to_node)

    return wf
