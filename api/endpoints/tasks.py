# -*- coding: utf-8 -*-
import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, status, HTTPException, File, UploadFile, Body

from api.schemas import (
    TaskRequest,
    TaskResponse,
    StatusResponse,
    ResultResponse,
    LogResponse,
)
from core.taskexecution import taskexecution
from config.config import Config
from utils.exceptions import TaskNotFoundError
from storage.db import get_task, get_logs, insert_log, update_task, create_task
from api.rate_limiter import RateLimiter
from utils.logger import logger

router = APIRouter()

# 使用单例限流器
rate_limiter = RateLimiter.get_instance()


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP 地址"""
    if request.client:
        return request.client.host
    return "unknown"


async def _process_task(request: Request, task_content: str) -> dict:
    """处理任务（公共逻辑）"""
    # 检查任务长度
    if len(task_content) > Config.API_MAX_TASK_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"任务内容超过限制（最大 {Config.API_MAX_TASK_LENGTH} 字符）"
        )
    
    # 检查限流
    client_ip = _get_client_ip(request)
    if not rate_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请稍后重试（每分钟最多 {Config.API_RATE_LIMIT_PER_MINUTE} 次）"
        )

    task_id = str(uuid.uuid4())
    logger.info(f"创建任务: {task_id}")
    create_task(task_id, task_content)
    task = asyncio.create_task(_execute_task(task_id, task_content))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)

    return {"task_id": task_id}


@router.post(
    "/run",
    response_model=TaskResponse,
    responses={
        400: {"description": "任务参数错误"},
        413: {"description": "任务内容超过限制"},
        429: {"description": "请求过于频繁"}
    }
)
async def run_task_text(request: Request, req: TaskRequest) -> dict:
    """提交测试用例生成任务（文本方式）
    
    通过 JSON 正文传入文本需求。
    
    Args:
        req: 包含 task 字段的 JSON 请求体
    
    Returns:
        任务 ID
    """
    task_content = req.task
    logger.info(f"接收到文本请求，内容长度: {len(task_content)}")
    return await _process_task(request, task_content)


@router.post(
    "/run/file",
    response_model=TaskResponse,
    responses={
        400: {"description": "文件解析失败"},
        413: {"description": "文件大小超过限制"},
        429: {"description": "请求过于频繁"}
    }
)
async def run_task_file(request: Request, file: UploadFile = File(...)) -> dict:
    """提交测试用例生成任务（文件上传方式）
    
    通过文件上传需求文档（支持 .txt, .md 格式）。
    
    Args:
        file: 上传的需求文件
    
    Returns:
        任务 ID
    """
    logger.info(f"接收到文件上传请求: {file.filename}")
    
    # 检查文件类型
    filename = file.filename or ""
    file_ext = Path(filename).suffix.lower().lstrip(".") if filename else ""
    
    if file_ext not in ["txt", "md", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，支持: txt, md, markdown"
        )
    
    # 读取文件内容
    try:
        content = await file.read()
        
        # 检查文件大小
        if len(content) > Config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制（最大 {Config.MAX_FILE_SIZE // (1024 * 1024)}MB）"
            )
        
        task_content = content.decode("utf-8").strip()
        logger.info(f"文件解析完成: {filename}, 内容长度: {len(task_content)}")
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，无法解析为UTF-8文本")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
    
    return await _process_task(request, task_content)


async def _execute_task(task_id: str, task: str) -> None:
    """异步执行任务"""
    try:
        logger.info(f"任务开始执行: {task_id}")
        update_task(task_id, status="running")
        logger.info(f"任务状态已更新为 running: {task_id}")
        
        result = await taskexecution(task=task, task_id=task_id, isapi=True)
        
        update_task(task_id, status="success", result=result)
        logger.info(f"任务执行成功: {task_id}")
    except Exception as e:
        update_task(task_id, status="failed")
        insert_log(task_id, "SYSTEM", str(e)[:Config.LOG_ERROR_MAX_LENGTH])
        logger.error(f"任务执行失败: {task_id}: {e}")


@router.get(
    "/task/{task_id}",
    response_model=StatusResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_status(task_id: str) -> dict:
    """获取任务状态"""
    logger.info(f"查询任务状态: {task_id[:8]}...")
    try:
        row = get_task(task_id)
        logger.info(f"任务状态查询成功: {task_id[:8]}... -> {row[2]}")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id[:8]}...")
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "id": row[0],
        "task": row[1],
        "status": row[2],
        "created_at": row[4],
        "updated_at": row[5],
    }


@router.get(
    "/result/{task_id}",
    response_model=ResultResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_result(task_id: str) -> dict:
    """获取任务结果"""
    logger.info(f"查询任务结果: {task_id[:8]}...")
    try:
        row = get_task(task_id)
        logger.info(f"任务结果查询成功: {task_id[:8]}...")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id[:8]}...")
        raise HTTPException(status_code=404, detail="任务不存在")

    result = json.loads(row[3]) if row[3] else None
    logger.info(f"返回结果长度: {len(str(result))} 字符")
    return {"result": result}


@router.get(
    "/logs/{task_id}",
    response_model=LogResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_task_logs(task_id: str) -> dict:
    """获取任务日志"""
    logger.info(f"查询任务日志: {task_id[:8]}...")
    try:
        get_task(task_id)
        logger.info(f"任务存在检查成功: {task_id[:8]}...")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id[:8]}...")
        raise HTTPException(status_code=404, detail="任务不存在")

    logs = get_logs(task_id)
    logger.info(f"获取日志 {len(logs)} 条: {task_id[:8]}...")
    return {
        "task_id": task_id,
        "logs": logs,
        "total": len(logs)
    }



