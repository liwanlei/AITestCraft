# -*- coding: utf-8 -*-
import json
import threading
from typing import Any, Dict, Optional

from agent_framework import SkillsProvider

from agents.base import build_agents
from config.config import Config
from core.context import Context, TokenStats
from core.workflow_builders import build_workflow, _build_module_testpoint_inputs, _parse_modules, WORKFLOW_NODE_ORDER
from storage.repositories import insert_log, get_node_status
from utils.logger import logger
from utils.exceptions import WorkflowError

# 工作流启动节点名称常量
WORKFLOW_START_NODE = "requirement"

_providers: Optional[Dict[str, SkillsProvider]] = None
_providers_lock = threading.Lock()


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
        skip_nodes = {"requirement", "testpoint", "aggregator"}
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
    logger.info(f"========== 任务开始执行 ==========")
    logger.info(f"任务ID: {short_id}")
    logger.info(f"任务内容长度: {len(task)} 字符")
    logger.info(f"API模式: {isapi}")
    logger.info(f"断点恢复: {from_checkpoint}")
    
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
            logger.info(f"任务完成，使用最终测试用例")
        elif result_ctx.get("testcase"):
            result = result_ctx["testcase"]
            logger.info(f"任务完成，使用测试用例")
        else:
            # 检查是否有其他可用的测试用例数据
            for key in ["unique_testpoints", "testpoint", "requirement"]:
                if result_ctx.get(key):
                    result = result_ctx[key]
                    logger.info(f"任务完成，使用 {key} 作为结果")
                    break
            else:
                error_msg = "工作流执行结果中既没有 final_cases 也没有 testcase"
                logger.error(error_msg)
                logger.error(f"result_ctx 的键: {list(result_ctx) if result_ctx else 'None'}")
                raise WorkflowError(error_msg)
        
        logger.info(f"结果长度: {len(str(result))} 字符")
        logger.info(f"========== 任务执行完成 ==========")

        return result
