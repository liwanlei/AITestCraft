# -*- coding: utf-8 -*-
import json
import threading
from typing import Any, Dict, List, Optional

import httpx

from agent_framework import SkillsProvider

from agents.base import build_agents
from config.config import Config
from core.context import Context, TokenStats
from core.node import NodeExecutionError
from core.workflow_builders import build_workflow, _build_module_testpoint_inputs, _parse_modules, WORKFLOW_NODE_ORDER
from storage.repositories import insert_log, get_node_status
from utils.case_parser import parse_case_tree
from utils.logger import logger
from utils.exceptions import WorkflowError

# 工作流启动节点名称常量
WORKFLOW_START_NODE = "requirement"

_providers: Optional[Dict[str, SkillsProvider]] = None
_providers_lock = threading.Lock()


def _fetch_cases_by_code(case_ids: List[str]) -> tuple:
    """
    通过代码调用外部用例服务获取用例数据并解析
    
    LLM 无法调用外部 API，因此 fetch-cases 步骤需要通过代码完成：
    1. 调用外部用例服务 API 获取原始数据
    2. 使用 case_parser 解析树形结构为标准格式
    
    Args:
        case_ids: 用例 ID 列表
        
    Returns:
        (标准化用例列表, categoryName)
    """
    base_url = Config.CASE_SERVICE_BASE_URL
    api_path = Config.CASE_SERVICE_GET_CASE_API
    
    if not base_url:
        logger.warning("[知识提取] 未配置 CASE_SERVICE_BASE_URL，无法获取用例数据")
        return [], ""
    
    all_cases = []
    category_name = ""
    
    for case_id in case_ids:
        try:
            url = f"{base_url.rstrip('/')}{api_path}"
            resp = httpx.get(url, params={"caseId": case_id}, timeout=Config.KNOWLEDGE_FETCH_TIMEOUT)
            resp.raise_for_status()
            raw_data = resp.json()
            
            # 提取 categoryName
            if not category_name:
                category_name = raw_data.get("data", {}).get("categoryName", "")
            
            # 使用 case_parser 解析树形结构
            cases = parse_case_tree(raw_data)
            all_cases.extend(cases)
            
            logger.debug(f"[知识提取] 用例 {case_id} 解析成功，提取 {len(cases)} 条")
        except Exception as e:
            logger.warning(f"[知识提取] 用例 {case_id} 获取/解析失败: {e}")
            continue
    
    return all_cases, category_name


def _create_providers() -> Dict[str, SkillsProvider]:
    global _providers
    with _providers_lock:
        if _providers is None:
            _providers = {
                key: SkillsProvider(str(Config.SKILLS_DIR / dirname))
                for key, dirname in Config.SKILL_NAMES.items()
            }
    return _providers


def reset_providers() -> None:
    global _providers
    with _providers_lock:
        _providers = None


async def _run_workflow(wf: Any, ctx: Context, skip_completed: set = None) -> Context:
    if skip_completed:
        logger.info(f"使用断点恢复模式，跳过已完成节点: {skip_completed}")
        return await wf.run_from_checkpoint(WORKFLOW_START_NODE, ctx)

    result_ctx = await wf.run_single_node("requirement", ctx)

    requirement_text = result_ctx.get("requirement", "")
    modules = _parse_modules(requirement_text)

    if len(modules) > Config.MODULE_SPLIT_THRESHOLD:
        logger.info(f"检测到 {len(modules)} 个模块，超过阈值 {Config.MODULE_SPLIT_THRESHOLD}，启用分块并行处理")
        module_inputs = _build_module_testpoint_inputs(result_ctx)
        result_ctx = await wf.run_parallel("testpoint", result_ctx, module_inputs, "testpoint")
        result_ctx = await wf.run_single_node("aggregator", result_ctx)
    else:
        logger.info(f"模块数 {len(modules)} 未超过阈值 {Config.MODULE_SPLIT_THRESHOLD}，使用标准工作流")
        result_ctx = await wf.run_single_node("testpoint", result_ctx)

    for node_name in WORKFLOW_NODE_ORDER:
        skip_nodes = {"requirement", "testpoint", "aggregator", "gap"}
        if node_name in skip_nodes:
            continue
        result_ctx = await wf.run_single_node(node_name, result_ctx)

    try:
        result_ctx = await wf.run_single_node("gap", result_ctx)
    except Exception as e:
        logger.warning(f"gap 节点执行失败（用例遗漏补充未完成）: {e}")

    return result_ctx


async def taskexecution(task_id: str, task: str, isapi: bool = False, from_checkpoint: bool = False) -> Any:
    short_id = task_id
    logger.info(f"{'='*60}")
    logger.info(f"用例生成流程 - 任务开始")
    logger.info(f"{'='*60}")
    logger.info(f"任务ID: {short_id}")
    logger.info(f"API模式: {isapi}")
    logger.info(f"断点恢复: {from_checkpoint}")
    
    # 打印流程输入
    task_preview = task[:2000] if len(task) > 2000 else task
    task_suffix = f"\n... (已截断，共 {len(task)} 字符)" if len(task) > 2000 else ""
    logger.info(f"流程输入 - 需求内容 ({len(task)} 字符):\n{task_preview}{task_suffix}")
    logger.info(f"{'='*60}")
    
    # 初始化组件
    logger.debug("正在初始化技能提供者...")
    providers = _create_providers()
    logger.info(f"技能提供者数量: {len(providers)}")
    logger.debug("正在构建Agent...")
    agents = build_agents(providers, model_configs=Config.NODE_MODEL_SETTINGS)
    logger.debug("正在构建工作流...")
    wf = build_workflow(agents, model_configs=Config.NODE_MODEL_SETTINGS)
    
    # 设置上下文
    ctx = Context()
    ctx.set("task", task)
    if from_checkpoint:
        node_statuses = get_node_status(task_id)
        token_stats = TokenStats.from_persisted(node_statuses)
        logger.info(f"从数据库恢复 Token 统计: {len(node_statuses)} 个节点, 总计 {token_stats.total_tokens} tokens")
    else:
        token_stats = TokenStats()
    ctx.set("token_stats", token_stats)
    ctx.set("task_id", task_id)
    ctx.set("isapi", isapi)

    # 记录任务开始
    insert_log(task_id, "WORKFLOW", json.dumps({
        "event": "start" if not from_checkpoint else "resume",
        "detail": task
    }, ensure_ascii=False))
    logger.info(f"任务已创建，等待工作流执行...")

    try:
        logger.info(f"========== 工作流开始执行 ==========")
        skip_completed = None
        if from_checkpoint:
            node_statuses = get_node_status(task_id)
            skip_completed = {n for n, s in node_statuses.items() if s.get("status") == "completed"}
            if skip_completed:
                logger.info(f"断点恢复，跳过已完成节点: {skip_completed}")

        result_ctx = await _run_workflow(wf, ctx, skip_completed=skip_completed)

        logger.info(f"========== 工作流执行完成 ==========")
    except Exception as e:
        error_detail = str(e)
        insert_log(task_id, "WORKFLOW", json.dumps({
            "event": "error",
            "detail": error_detail
        }, ensure_ascii=False))
        logger.error(f"任务执行失败: {e}")
        raise
    else:
        # 记录任务完成
        stats = result_ctx["token_stats"].report()
        insert_log(task_id, "WORKFLOW", json.dumps({
            "event": "complete",
            "detail": stats
        }, ensure_ascii=False))
        
        logger.info(f"========== Token使用统计 ==========")
        logger.info(f"总输入Token: {stats['workflow']['input_tokens']}")
        logger.info(f"总输出Token: {stats['workflow']['output_tokens']}")
        logger.info(f"总Token: {stats['workflow']['total_tokens']}")
        for node_info in stats["nodes"]:
            logger.info(f"  [{node_info['name']}] 输入: {node_info['input']}, 输出: {node_info['output']}, 总计: {node_info['total']}")

        # 返回结果
        if "final_cases" in result_ctx and result_ctx["final_cases"]:
            result = result_ctx["final_cases"]
            result_source = "final_cases (补充后的最终用例)"
        elif result_ctx.get("testcase"):
            result = result_ctx["testcase"]
            result_source = "testcase (生成的测试用例)"
        else:
            # 检查是否有其他可用的测试用例数据
            for key in ["unique_testpoints", "testpoint", "requirement"]:
                if result_ctx.get(key):
                    result = result_ctx[key]
                    result_source = f"{key} (降级结果)"
                    break
            else:
                error_msg = "工作流执行结果中既没有 final_cases 也没有 testcase"
                logger.error(error_msg)
                logger.error(f"result_ctx 的键: {list(result_ctx) if result_ctx else 'None'}")
                raise WorkflowError(error_msg)
        
        # 打印流程输出
        result_str = str(result)
        result_preview = result_str[:3000] if len(result_str) > 3000 else result_str
        result_suffix = f"\n... (已截断，共 {len(result_str)} 字符)" if len(result_str) > 3000 else ""
        logger.info(f"{'='*60}")
        logger.info(f"用例生成流程 - 任务完成")
        logger.info(f"{'='*60}")
        logger.info(f"结果来源: {result_source}")
        logger.info(f"流程输出 ({len(result_str)} 字符):\n{result_preview}{result_suffix}")
        logger.info(f"{'='*60}")

        return result


async def knowledgeexecution(task_id: str, case_ids: list, isapi: bool = False, from_checkpoint: bool = False) -> Any:
    """
    知识提取任务执行入口
    
    Args:
        task_id: 任务 ID
        case_ids: 用例 ID 列表
        isapi: 是否 API 模式
        from_checkpoint: 是否断点恢复
        
    Returns:
        提取结果
    """
    short_id = task_id[:Config.LOG_TASK_ID_LENGTH]
    logger.info(f"{'='*60}")
    logger.info(f"[知识提取] 任务开始执行")
    logger.info(f"[知识提取] 任务ID: {short_id}")
    logger.info(f"[知识提取] 用例数量: {len(case_ids)}")
    logger.info(f"[知识提取] 用例ID列表: {case_ids}")
    logger.info(f"[知识提取] API模式: {isapi}")
    logger.info(f"[知识提取] 断点恢复: {from_checkpoint}")
    logger.info(f"{'='*60}")
    
    try:
        # 阶段1: 初始化组件
        logger.info(f"[知识提取] [阶段1/6] 初始化组件...")
        providers = _create_providers()
        logger.info(f"[知识提取]   ✓ 技能提供者数量: {len(providers)}")
        
        agents = build_agents(providers, model_configs=Config.NODE_MODEL_SETTINGS)
        logger.info(f"[知识提取]   ✓ Agent构建完成")
        
        # 阶段2: 构建工作流
        logger.info(f"[知识提取] [阶段2/6] 构建知识提取工作流...")
        from core.knowledge_workflow_builders import build_knowledge_workflow
        wf = build_knowledge_workflow(agents, model_configs=Config.NODE_MODEL_SETTINGS)
        logger.info(f"[知识提取]   ✓ 工作流构建完成，节点数: {len(wf.nodes)}")
        
        # 阶段3: 设置上下文
        logger.info(f"[知识提取] [阶段3/6] 设置执行上下文...")
        ctx = Context()
        ctx.set("case_ids", case_ids)
        ctx.set("task_id", task_id)
        ctx.set("isapi", isapi)
        
        if from_checkpoint:
            node_statuses = get_node_status(task_id)
            token_stats = TokenStats.from_persisted(node_statuses)
            logger.info(f"[知识提取]   ✓ 从持久化恢复Token统计")
        else:
            token_stats = TokenStats()
            logger.info(f"[知识提取]   ✓ 新建Token统计")
        ctx.set("token_stats", token_stats)
        
        # 阶段4: 记录任务开始
        logger.info(f"[知识提取] [阶段4/6] 记录任务日志...")
        insert_log(task_id, "KNOWLEDGE_WORKFLOW", json.dumps({
            "event": "start",
            "case_ids": case_ids,
            "node_count": len(wf.nodes)
        }, ensure_ascii=False))
        logger.info(f"[知识提取]   ✓ 任务日志已记录")
        
        # 阶段5: 执行工作流
        logger.info(f"[知识提取] [阶段5/6] 执行工作流...")
        
        # 通过代码获取用例数据（LLM 无法调用外部 API，fetch-cases 由代码完成）
        logger.info(f"[知识提取]   通过代码获取用例数据...")
        cases, category_name = _fetch_cases_by_code(case_ids)
        ctx.set("cases", cases)
        ctx.set("category_name", category_name)
        logger.info(f"[知识提取]   ✓ 获取到 {len(cases)} 个用例, categoryName: {category_name or '未知'}")
        
        # 从 summarize-modules 节点开始执行工作流
        logger.info(f"[知识提取]   开始执行节点: summarize-modules")
        try:
            result_ctx = await wf.run_from_checkpoint("summarize-modules", ctx)
        except NodeExecutionError as e:
            # resolve-conflicts 节点失败时，透传 deduped 数据
            if "resolve-conflicts" in str(e):
                logger.warning(f"[知识提取] resolve-conflicts 节点失败，透传 deduped 数据")
                deduped = ctx.get("deduped_items", [])
                ctx.set("resolved_items", deduped)
                result_ctx = await wf.run_from_checkpoint("consolidate-knowledge", ctx)
            else:
                raise
        logger.info(f"[知识提取]   ✓ 工作流执行完成")
        
        # 阶段6: 处理结果
        logger.info(f"[知识提取] [阶段6/6] 处理结果...")
        
        # 记录任务完成
        stats = result_ctx["token_stats"].report()
        insert_log(task_id, "KNOWLEDGE_WORKFLOW", json.dumps({
            "event": "complete",
            "detail": stats
        }, ensure_ascii=False))
        
        # 返回结果
        result = result_ctx.get("final_knowledge", "")
        category_name = ctx.get("category_name", "")
        result_length = len(str(result))
        
        # 输出Token统计
        logger.info(f"{'='*60}")
        logger.info(f"[知识提取] 任务执行完成")
        logger.info(f"[知识提取] 结果长度: {result_length} 字符")
        logger.info(f"[知识提取] Token统计:")
        logger.info(f"[知识提取]   总输入Token: {stats['workflow']['input_tokens']}")
        logger.info(f"[知识提取]   总输出Token: {stats['workflow']['output_tokens']}")
        logger.info(f"[知识提取]   总Token消耗: {stats['workflow']['total_tokens']}")
        for node_info in stats["nodes"]:
            logger.info(f"[知识提取]   [{node_info['name']}] 输入: {node_info['input']}, 输出: {node_info['output']}, 总计: {node_info['total']}")
        logger.info(f"{'='*60}")
        
        return {"result": result, "category_name": category_name}
        
    except Exception as e:
        insert_log(task_id, "KNOWLEDGE_WORKFLOW", json.dumps({
            "event": "error",
            "detail": str(e),
            "case_ids": case_ids
        }, ensure_ascii=False))
        logger.error(f"{'='*60}")
        logger.error(f"[知识提取] 任务执行失败")
        logger.error(f"[知识提取] 任务ID: {short_id}")
        logger.error(f"[知识提取] 错误信息: {str(e)}")
        logger.error(f"{'='*60}")
        raise
