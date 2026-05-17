# -*- coding: utf-8 -*-
import asyncio
import uuid

from fastapi import Request, HTTPException, status

from config.config import Config
from core.taskexecution import taskexecution
from storage.repositories import get_task, insert_log, update_task, create_task, get_last_completed_node
from utils.logger import logger


async def process_task(request: Request, task_content: str) -> dict:
    if len(task_content) > Config.API_MAX_TASK_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"任务内容超过限制（最大 {Config.API_MAX_TASK_LENGTH} 字符）"
        )

    task_id = str(uuid.uuid4())
    logger.info(f"创建任务: {task_id}")
    create_task(task_id, task_content)
    task = asyncio.create_task(execute_task(task_id, task_content))

    def _log_task_exception(t):
        if not t.cancelled() and t.exception():
            logger.error(f"后台任务异常: {t.exception()}")

    task.add_done_callback(_log_task_exception)

    return {"task_id": task_id}


async def execute_task(task_id: str, task: str, from_checkpoint: bool = False) -> None:
    """
    执行任务
    
    Args:
        task_id: 任务ID
        task: 任务内容
        from_checkpoint: 是否从断点恢复执行
    """
    max_retries = Config.NODE_MAX_RETRY
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info(f"任务开始执行: {task_id} (尝试 {retry_count + 1}/{max_retries + 1})")
            update_task(task_id, status="running")
            logger.info(f"任务状态已更新为 running: {task_id}")

            result = await taskexecution(task=task, task_id=task_id, isapi=True, from_checkpoint=from_checkpoint)

            update_task(task_id, status="success", result=result)
            logger.info(f"任务执行成功: {task_id}")
            return
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            
            if retry_count <= max_retries:
                # 检查是否有已完成的节点，如果有则从断点恢复
                last_node = get_last_completed_node(task_id)
                if last_node:
                    from_checkpoint = True
                    logger.info(f"任务执行失败，发现已完成节点 [{last_node}]，下次重试将从断点恢复")
                logger.warning(f"任务执行失败，将重试 ({retry_count}/{max_retries}): {task_id}: {error_msg}")
                insert_log(task_id, "SYSTEM", f"执行失败，正在重试 ({retry_count}/{max_retries}): {error_msg}")
            else:
                logger.error(f"任务执行失败，已达到最大重试次数: {task_id}: {error_msg}")
                update_task(task_id, status="failed")
                insert_log(task_id, "SYSTEM", f"执行失败，已达到最大重试次数: {error_msg}")


async def recover_task(task_id: str, task: str, from_checkpoint: bool = False) -> None:
    """
    从断点恢复执行任务
    
    Args:
        task_id: 任务ID
        task: 任务内容
        from_checkpoint: 是否从断点恢复执行
    """
    max_retries = Config.NODE_MAX_RETRY
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info(f"任务从断点恢复: {task_id} (尝试 {retry_count + 1}/{max_retries + 1})")
            
            # 获取最后一个完成的节点
            last_node = get_last_completed_node(task_id)
            if last_node:
                logger.info(f"将从节点 [{last_node}] 的后续节点恢复执行")
            else:
                logger.info(f"未找到已完成节点，将从头开始执行")
            
            update_task(task_id, status="running")
            logger.info(f"任务状态已更新为 running: {task_id}")

            result = await taskexecution(task=task, task_id=task_id, isapi=True, from_checkpoint=True)

            update_task(task_id, status="success", result=result)
            logger.info(f"任务恢复执行成功: {task_id}")
            return
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            
            if retry_count <= max_retries:
                logger.warning(f"任务恢复失败，将重试 ({retry_count}/{max_retries}): {task_id}: {error_msg}")
                insert_log(task_id, "SYSTEM", f"恢复失败，正在重试 ({retry_count}/{max_retries}): {error_msg}")
            else:
                logger.error(f"任务恢复失败，已达到最大重试次数: {task_id}: {error_msg}")
                update_task(task_id, status="failed")
                insert_log(task_id, "SYSTEM", f"恢复失败，已达到最大重试次数: {error_msg}")
