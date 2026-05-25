# -*- coding: utf-8 -*-
import asyncio
from typing import List, Dict, Any, Set

from storage.repositories import get_tasks_by_status, update_task, get_last_completed_node
from utils.logger import logger
from config.config import Config

_background_tasks: Set[asyncio.Task] = set()


def _create_tracked_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def recover_interrupted_tasks(max_recover: int = None) -> int:
    """
    恢复中断的任务（从断点恢复）
    
    Args:
        max_recover: 最大恢复任务数，默认使用配置中的 TASK_RECOVERY_MAX_COUNT
        
    Returns:
        实际恢复的任务数量
    """
    # 使用配置中的默认值
    if max_recover is None:
        max_recover = Config.TASK_RECOVERY_MAX_COUNT
    
    # 获取需要恢复的任务（running 和 pending 状态）
    tasks = get_tasks_by_status(["running", "pending"])
    
    if not tasks:
        logger.info("未发现需要恢复的任务")
        return 0
    
    # 按创建时间倒序排列，最新任务优先
    tasks = sorted(tasks, key=lambda x: x["created_at"], reverse=True)
    
    # 限制最大恢复数量
    tasks_to_recover = tasks[:max_recover]
    logger.info(f"发现 {len(tasks)} 个需要恢复的任务，将恢复前 {len(tasks_to_recover)} 个")
    
    recovered_count = 0
    for task in tasks_to_recover:
        task_id = task["id"]
        task_content = task["task"]
        
        try:
            logger.info(f"开始恢复任务: {task_id[:8]}...")
            
            # 获取最后一个完成的节点
            last_node = get_last_completed_node(task_id)
            use_checkpoint = bool(last_node)
            if last_node:
                logger.info(f"任务 {task_id[:8]} 将从节点 [{last_node}] 的后续节点恢复")
            else:
                logger.info(f"任务 {task_id[:8]} 未找到已完成节点，将从头开始执行")
            
            # 将任务状态更新为 running
            update_task(task_id, status="running")
            
            from api.services.task_service import recover_task
            _create_tracked_task(recover_task(task_id, task_content, from_checkpoint=use_checkpoint))
            
            recovered_count += 1
            logger.info(f"任务已入队恢复: {task_id[:8]}...")
            
            # 间隔启动，避免启动时压力过大
            await asyncio.sleep(Config.TASK_RECOVERY_INTERVAL)
            
        except Exception as e:
            logger.error(f"恢复任务失败 {task_id[:8]}...: {e}")
            # 标记为失败
            update_task(task_id, status="failed")
    
    logger.info(f"任务恢复完成，共恢复 {recovered_count}/{len(tasks_to_recover)} 个任务")
    return recovered_count
