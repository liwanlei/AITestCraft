# -*- coding: utf-8 -*-
import json
from typing import Any, Dict, Optional

from agent_framework import SkillsProvider

from agents.base import build_agents
from config.config import Config
from core.context import Context, TokenStats
from core.workflow import build_workflow
from storage.db import insert_log
from utils.logger import logger


_providers: Optional[Dict[str, SkillsProvider]] = None


def _create_providers() -> Dict[str, SkillsProvider]:
    """创建或获取缓存的技能提供者字典"""
    global _providers
    if _providers is None:
        _providers = {
            key: SkillsProvider(str(Config.SKILLS_DIR / dirname))
            for key, dirname in Config.SKILL_NAMES.items()
        }
    return _providers


async def taskexecution(task_id: str, task: str, isapi: bool = False) -> Any:
    short_id = task_id[:8]
    logger.info(f"========== 任务开始执行 ==========")
    logger.info(f"任务ID: {short_id}...")
    logger.info(f"任务内容长度: {len(task)} 字符")
    logger.info(f"API模式: {isapi}")
    
    # 初始化组件
    logger.debug("正在初始化技能提供者...")
    providers = _create_providers()
    logger.info(f"技能提供者数量: {len(providers)}")
    logger.debug("正在构建Agent...")
    agents = build_agents(providers)
    logger.debug("正在构建工作流...")
    wf = build_workflow(agents)
    
    # 设置上下文
    ctx = Context()
    ctx.set("task", task)
    ctx.set("token_stats", TokenStats())
    ctx.set("task_id", task_id)
    ctx.set("isapi", isapi)

    # 记录任务开始
    insert_log(task_id, "WORKFLOW", json.dumps({
        "event": "start",
        "detail": task[:Config.LOG_TASK_MAX_LENGTH]
    }, ensure_ascii=False))
    logger.info(f"任务已创建，等待工作流执行...")

    try:
        logger.info(f"========== 工作流开始执行 ==========")
        result_ctx = await wf.run("requirement", ctx)
        logger.info(f"========== 工作流执行完成 ==========")
    except Exception as e:
        error_detail = str(e)[:Config.LOG_ERROR_MAX_LENGTH]
        insert_log(task_id, "WORKFLOW", json.dumps({
            "event": "error",
            "detail": error_detail
        }, ensure_ascii=False))
        logger.error(f"任务执行失败: {e}")
        raise

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
    for node_name, node_stats in stats["nodes"].items():
        logger.info(f"  [{node_name}] 输入: {node_stats['input']}, 输出: {node_stats['output']}, 总计: {node_stats['total']}")

    # 返回结果
    if "final_cases" in result_ctx:
        result = result_ctx["final_cases"]
        logger.info(f"任务完成，使用最终测试用例")
    else:
        result = result_ctx.get("testcase", {})
        logger.info(f"任务完成，使用测试用例")
    
    logger.info(f"结果长度: {len(str(result))} 字符")
    logger.info(f"========== 任务执行完成 ==========")

    return result
