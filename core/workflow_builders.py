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


def _build_dedup_input(ctx: Context) -> str:
    return ctx.get("testpoint", "")


def _get_testpoints_text(ctx: Context) -> str:
    return ctx.get("unique_testpoints", "")


def _build_testcase_input(ctx: Context) -> str:
    return _get_testpoints_text(ctx)


def _build_review_coverage_input(ctx: Context) -> str:
    parts = []
    requirement = ctx.get("requirement", "")
    parts.append(f"## 需求信息\n{requirement}")

    testpoints = _get_testpoints_text(ctx)
    parts.append(f"## 测试点\n{testpoints}")

    cases = ctx.get("testcase")
    if cases:
        cases_text = cases if isinstance(cases, str) else json.dumps(cases, ensure_ascii=False)
        parts.append(f"## 测试用例\n{cases_text}")

    return "\n\n".join(parts)


def _extract_risk_level(coverage_text: str) -> str:
    if re.search(r"风险等级\s*[:：]\s*high", coverage_text, re.IGNORECASE):
        return "high"
    if re.search(r"风险等级\s*[:：]\s*medium", coverage_text, re.IGNORECASE):
        return "medium"
    return "low"


def _build_gap_input(ctx: Context) -> str:
    cases = ctx.get("testcase")
    if cases is None:
        cases_text = "[]"
    elif isinstance(cases, str):
        cases_text = cases
    else:
        cases_text = json.dumps(cases, ensure_ascii=False)

    review = ctx.get("review", "")
    review_text = review if isinstance(review, str) else json.dumps(review, ensure_ascii=False)
    
    coverage = ctx.get("coverage", "")
    coverage_text = coverage if isinstance(coverage, str) else json.dumps(coverage, ensure_ascii=False)
    
    risk_level = _extract_risk_level(coverage_text)

    parts = [f"## 测试用例\n{cases_text}"]
    parts.append(f"## 评审结果\n{review_text}")
    parts.append(f"## 覆盖率分析\n{coverage_text}")
    parts.append(f"## 风险等级\n{risk_level}")
    return "\n\n".join(parts)


def _gap_condition(ctx: Context) -> bool:
    review = ctx.get("review", "")
    review_text = review if isinstance(review, str) else json.dumps(review, ensure_ascii=False)
    
    coverage = ctx.get("coverage", "")
    coverage_text = coverage if isinstance(coverage, str) else json.dumps(coverage, ensure_ascii=False)

    high_risk = bool(re.search(r"风险等级\s*[:：]\s*high", coverage_text, re.IGNORECASE))
    medium_risk = bool(re.search(r"风险等级\s*[:：]\s*medium", coverage_text, re.IGNORECASE))
    has_issues = bool(re.search(r"问题列表", review_text)) and bool(re.search(r"^\s*-\s+\S", review_text, re.MULTILINE))
    has_missing = bool(re.search(r"未覆盖场景", coverage_text)) and bool(re.search(r"^\s*-\s+\S", coverage_text, re.MULTILINE))

    return high_risk or medium_risk or has_issues or has_missing


def build_workflow(agents: Dict[str, Any], model_configs: Optional[Dict[str, Dict]] = None) -> Workflow:
    if model_configs is None:
        model_configs = {}

    wf = Workflow()

    node_configs = [
        NodeConfig("requirement", agents["requirement"], _build_requirement_input, "requirement", output_format="md"),
        NodeConfig("testpoint", agents["testpoint"], _build_testpoint_input, "testpoint", output_format="md"),
        NodeConfig("dedup", agents["dedup"], _build_dedup_input, "unique_testpoints", output_format="md"),
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
        ("testpoint", "dedup"),
        ("dedup", "testcase"),
        ("testcase", "review"),
        ("review", "coverage"),
        ("coverage", "gap"),
    ]

    for from_node, to_node in edges:
        wf.add_edge(from_node, to_node)

    return wf
