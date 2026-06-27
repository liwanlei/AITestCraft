# -*- coding: utf-8 -*-
from typing import Any, Callable, Dict, Optional

from core.context import Context
from core.node import Node
from core.workflow import Workflow
from utils.logger import logger


def _build_summarize_input(ctx: Context) -> str:
    """构建 summarize-modules 节点输入"""
    cases = ctx.get("cases", "[]")
    case_count = len(cases) if isinstance(cases, list) else 0
    logger.info(f"[知识提取] 准备归纳需求，已获取 {case_count} 个用例")
    
    if not isinstance(cases, list) or not cases:
        return "[]"
    
    # 精简用例信息，只保留归纳所需的关键字段
    simplified = []
    for case in cases:
        simplified.append({
            "case_id": case.get("case_id", case.get("id", "")),
            "module": case.get("module", ""),
            "priority": case.get("priority", ""),
            "name": case.get("name", case.get("title", "")),
            "precondition": case.get("precondition", ""),
            "steps": case.get("steps", ""),
            "expected": case.get("expected", case.get("assert", case.get("assertion", "")))
        })
    
    import json
    return json.dumps(simplified, ensure_ascii=False)


def _build_dedup_input(ctx: Context) -> str:
    """构建 dedup 节点输入"""
    module_knowledge = ctx.get("module_knowledge", "")
    if isinstance(module_knowledge, list):
        import json
        module_knowledge = json.dumps(module_knowledge, ensure_ascii=False)
    logger.info(f"[知识提取] 准备去重处理，输入内容长度: {len(module_knowledge)} 字符")
    return module_knowledge


def _build_resolve_conflicts_input(ctx: Context) -> str:
    """构建 resolve-conflicts 节点输入"""
    deduped_items = ctx.get("deduped_items", "[]")
    if isinstance(deduped_items, list):
        item_count = len(deduped_items)
        import json
        deduped_items = json.dumps(deduped_items, ensure_ascii=False)
    else:
        try:
            item_count = len(json.loads(deduped_items)) if deduped_items else 0
        except Exception:
            item_count = 0
    logger.info(f"[知识提取] 准备冲突解决，待处理知识点: {item_count} 个")
    return deduped_items


def _build_consolidate_input(ctx: Context) -> str:
    """构建 consolidate-knowledge 节点输入"""
    resolved_items = ctx.get("resolved_items", "[]")
    if isinstance(resolved_items, list):
        item_count = len(resolved_items)
        import json
        resolved_items = json.dumps(resolved_items, ensure_ascii=False)
    else:
        try:
            item_count = len(json.loads(resolved_items)) if resolved_items else 0
        except Exception:
            item_count = 0
    logger.info(f"[知识提取] 准备汇总持久化，已解决知识点: {item_count} 个")
    return resolved_items


def build_knowledge_workflow(
    agents: Dict[str, Any],
    model_configs: Optional[Dict[str, Dict]] = None
) -> Workflow:
    """
    构建知识提取工作流（4节点）

    用例获取（fetch-cases）由代码完成（_fetch_cases_by_code），
    因为 LLM 无法调用外部 API。工作流从 summarize-modules 开始。

    节点流程：
    summarize-modules → dedup-knowledge → resolve-conflicts → consolidate-knowledge

    Args:
        agents: Agent 字典
        model_configs: 模型配置

    Returns:
        配置好的工作流实例
    """
    if model_configs is None:
        model_configs = {}

    wf = Workflow()

    # 定义节点配置（fetch-cases 由代码完成，不纳入工作流）
    node_configs = [
        ("summarize-modules", agents.get("summarize-modules"), _build_summarize_input, "module_knowledge", "json"),
        ("dedup-knowledge", agents.get("dedup-knowledge"), _build_dedup_input, "deduped_items", "json"),
        ("resolve-conflicts", agents.get("resolve-conflicts"), _build_resolve_conflicts_input, "resolved_items", "json"),
        ("consolidate-knowledge", agents.get("consolidate-knowledge"), _build_consolidate_input, "final_knowledge", "mixed"),
    ]

    for name, agent, input_fn, output_key, output_format in node_configs:
        if agent is None:
            logger.warning(f"[知识提取] Agent for node {name} is not available, skipping")
            continue
        node_model_settings = model_configs.get(name)
        wf.add_node(Node(
            name=name,
            agent=agent,
            input_fn=input_fn,
            output_key=output_key,
            output_format=output_format,
            model_settings=node_model_settings
        ))

    # 定义边（节点执行顺序）
    edges = [
        ("summarize-modules", "dedup-knowledge"),
        ("dedup-knowledge", "resolve-conflicts"),
        ("resolve-conflicts", "consolidate-knowledge"),
    ]

    for from_node, to_node in edges:
        wf.add_edge(from_node, to_node)

    logger.info("[知识提取] 工作流构建完成，共 4 个节点（fetch-cases 由代码完成）")
    return wf
