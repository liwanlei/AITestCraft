# -*- coding: utf-8 -*-
import json
import uuid

import httpx
from fastapi import Request

from config.config import Config
from core.taskexecution import taskexecution
from storage.repositories import insert_log, update_task, create_task, get_last_completed_node
from utils.logger import logger

from api.recovery import _create_tracked_task


async def process_task(request: Request, task_content: str, case_id: str = None) -> dict:
    task_id = str(uuid.uuid4())
    logger.info(f"创建任务: {task_id}")
    create_task(task_id, task_content)
    _create_tracked_task(_execute_task_with_retry(task_id, task_content, case_id=case_id))

    return {"task_id": task_id}


async def _call_save_ai_result(case_id: str, task_id: str, case_content: dict) -> None:
    """调用 /api/case/saveAiResult 接口回写AI生成的用例"""
    try:
        payload = {
            "caseId": case_id,
            "taskId": task_id,
            "caseContent": case_content
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                Config.SAVE_AI_RESULT_URL,
                json=payload
            )
            if resp.status_code == 200:
                logger.info(f"saveAiResult 调用成功: caseId={case_id}, taskId={task_id}")
            else:
                logger.warning(f"saveAiResult 调用失败: status={resp.status_code}, body={resp.text}")
    except Exception as e:
        logger.error(f"saveAiResult 调用异常: caseId={case_id}, error={e}")


async def _execute_task_with_retry(
    task_id: str,
    task: str,
    from_checkpoint: bool = False,
    is_recovery: bool = False,
    case_id: str = None,
) -> None:
    max_retries = Config.NODE_MAX_RETRY
    retry_count = 0

    action_label = "恢复" if is_recovery else "执行"

    while retry_count <= max_retries:
        try:
            logger.info(f"任务{action_label}: {task_id} (尝试 {retry_count + 1}/{max_retries + 1})")

            if from_checkpoint:
                last_node = get_last_completed_node(task_id)
                if last_node:
                    logger.info(f"将从节点 [{last_node}] 的后续节点恢复执行")
                else:
                    logger.info(f"未找到已完成节点，将从头开始执行")
                    from_checkpoint = False

            update_task(task_id, status="running")
            logger.info(f"任务状态已更新为 running: {task_id}")

            result = await taskexecution(task=task, task_id=task_id, isapi=True, from_checkpoint=from_checkpoint)

            update_task(task_id, status="success", result=result)
            logger.info(f"任务{action_label}成功: {task_id}")

            # 如果传入了 caseId，生成 KityMinder 格式并回写
            if case_id:
                from formatters import KityMinderFormatter
                from api.services.result_service import _parse_result_data

                testcases, _ = _parse_result_data(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
                if testcases:
                    formatter = KityMinderFormatter()
                    metadata = {
                        "title": "测试用例文档",
                        "requirement": task,
                        "generated_at": "",
                        "total_count": len(testcases),
                        "coverage": 0
                    }
                    case_content = formatter.format(testcases, metadata)
                    await _call_save_ai_result(case_id, task_id, case_content)
                else:
                    logger.warning(f"caseId={case_id} 但用例为空，跳过 saveAiResult 调用")

            return
        except Exception as e:
            retry_count += 1
            error_msg = str(e)

            if retry_count <= max_retries:
                last_node = get_last_completed_node(task_id)
                if last_node:
                    from_checkpoint = True
                    logger.info(f"任务{action_label}失败，发现已完成节点 [{last_node}]，下次重试将从断点恢复")
                logger.warning(f"任务{action_label}失败，将重试 ({retry_count}/{max_retries}): {task_id}: {error_msg}")
                insert_log(task_id, "SYSTEM", f"{action_label}失败，正在重试 ({retry_count}/{max_retries}): {error_msg}")
            else:
                logger.error(f"任务{action_label}失败，已达到最大重试次数: {task_id}: {error_msg}")
                update_task(task_id, status="failed")
                insert_log(task_id, "SYSTEM", f"{action_label}失败，已达到最大重试次数: {error_msg}")


async def execute_task(task_id: str, task: str, from_checkpoint: bool = False) -> None:
    await _execute_task_with_retry(task_id, task, from_checkpoint, is_recovery=False)


async def recover_task(task_id: str, task: str, from_checkpoint: bool = False) -> None:
    await _execute_task_with_retry(task_id, task, from_checkpoint=True, is_recovery=True)