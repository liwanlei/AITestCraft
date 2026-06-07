# -*- coding: utf-8 -*-
import re
from typing import Optional

from fastapi import APIRouter, Request, status, HTTPException, File, UploadFile, Form

from api.schemas import TaskResponse, StatusResponse, ResultResponse, LogResponse
from api.services.content_resolver import resolve_file_content, resolve_doc_content
from api.services.task_service import process_task
from api.services.result_service import build_result
from storage.repositories import get_task, get_logs
from utils.exceptions import TaskNotFoundError
from utils.logger import logger

router = APIRouter()

# UUID 格式验证正则（允许标准 UUID 和短格式）
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}$', re.IGNORECASE)


def validate_task_id(task_id: str) -> str:
    """验证 task_id 格式，防止路径遍历攻击"""
    if not task_id or not isinstance(task_id, str):
        raise HTTPException(status_code=400, detail="无效的任务 ID")
    
    # 验证 UUID 格式
    if not UUID_PATTERN.match(task_id):
        raise HTTPException(status_code=400, detail="任务 ID 格式无效")
    
    # 清理路径字符（双重防护）
    safe_id = task_id.replace("..", "").replace("/", "").replace("\\", "")
    
    # 确保清理后仍然匹配 UUID 格式
    if safe_id != task_id:
        raise HTTPException(status_code=400, detail="任务 ID 包含非法字符")
    
    return safe_id


@router.post(
    "/run",
    response_model=TaskResponse,
    responses={
        400: {"description": "参数错误或解析失败"},
        401: {"description": "文档平台 token 无效或已过期"},
        404: {"description": "文档不存在或无权限"},
        413: {"description": "内容超过限制"},
        422: {"description": "参数校验失败"},
        501: {"description": "功能未配置"}
    }
)
async def run_task(
    request: Request,
    task: Optional[str] = Form(None),
    doc_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    caseId: Optional[str] = Form(None),
) -> dict:
    """提交测试用例生成任务

    支持三种输入方式（优先级：file > doc_url > task）：
    - task: 文本需求
    - doc_url: 文档链接（支持飞书/TAPD/语雀/石墨/Confluence）
    - file: 文件上传（md/txt/pdf）

    可选参数：
    - caseId: 用例ID，传入后任务完成时会自动调用 saveAiResult 接口回写结果

    至少需要提供一个参数。
    """
    if file:
        task_content = await resolve_file_content(file)
    elif doc_url:
        task_content = await resolve_doc_content(doc_url)
    elif task:
        task_content = task
        # 日志仅记录长度，避免记录敏感内容
        logger.info(f"接收到文本请求，内容长度: {len(task_content)}")
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="task、doc_url、file 至少需要提供一个"
        )

    return await process_task(request, task_content, case_id=caseId)


@router.get(
    "/task/{task_id}",
    response_model=StatusResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_status(task_id: str) -> dict:
    logger.info(f"查询任务状态: {task_id}")
    task_id = validate_task_id(task_id)
    try:
        task = get_task(task_id)
        logger.info(f"任务状态查询成功: {task_id} -> {task['status']}")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id}") 
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "id": task["id"],
        "task": task["task"],
        "status": task["status"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


@router.get(
    "/result/{task_id}",
    response_model=ResultResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_result(task_id: str) -> dict:
    logger.info(f"查询任务结果: {task_id}...")
    task_id = validate_task_id(task_id)
    try:
        task = get_task(task_id)
        logger.info(f"任务结果查询成功: {task_id[:8]}...")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id[:8]}...")
        raise HTTPException(status_code=404, detail="任务不存在")

    return build_result(task)


@router.get(
    "/logs/{task_id}",
    response_model=LogResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_task_logs(task_id: str) -> dict:
    logger.info(f"查询任务日志: {task_id}")
    task_id = validate_task_id(task_id)
    try:
        get_task(task_id)
        logger.info(f"任务存在检查成功: {task_id}")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id}")
        raise HTTPException(status_code=404, detail="任务不存在")

    logs = get_logs(task_id)
    logger.info(f"获取日志 {len(logs)} 条: {task_id}")
    return {
        "task_id": task_id,
        "logs": logs,
        "total": len(logs)
    }
