# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, status, HTTPException, File, UploadFile, Form

from api.schemas import TaskResponse, StatusResponse, ResultResponse, LogResponse, MultiFormatResult, XMindFormats
from api.services.content_resolver import resolve_file_content, resolve_doc_content
from api.services.task_service import process_task
from formatters import MarkdownFormatter, XMindFormatter
from storage.repositories import get_task, get_logs
from utils.exceptions import TaskNotFoundError
from utils.json_utils import parse_markdown_table
from utils.logger import logger

router = APIRouter()

markdown_formatter = MarkdownFormatter()
xmind_formatter = XMindFormatter()

# 结果文件存储目录
RESULT_DIR = Path("result")


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
) -> dict:
    """提交测试用例生成任务

    支持三种输入方式（优先级：file > doc_url > task）：
    - task: 文本需求
    - doc_url: 文档链接（支持飞书/TAPD/语雀/石墨/Confluence）
    - file: 文件上传（md/txt/pdf）

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

    return await process_task(request, task_content)


@router.get(
    "/task/{task_id}",
    response_model=StatusResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_status(task_id: str) -> dict:
    logger.info(f"查询任务状态: {task_id}")
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
    try:
        task = get_task(task_id)
        logger.info(f"任务结果查询成功: {task_id[:8]}...")
    except TaskNotFoundError:
        logger.warning(f"任务不存在: {task_id[:8]}...")
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查任务状态
    task_status = task.get("status", "")
    if task_status == "running":
        return {"result": None, "message": "任务执行中", "status": "running"}
    elif task_status == "pending":
        return {"result": None, "message": "任务等待执行", "status": "pending"}
    elif task_status == "failed":
        return {"result": None, "message": "任务执行失败", "status": "failed"}

    result_data = json.loads(task["result"]) if task["result"] else None
    if result_data is None:
        return {"result": None, "message": "任务无结果", "status": task_status}

    # 兼容多种格式：列表、字典、Markdown 表格字符串
    if isinstance(result_data, list):
        testcases = result_data
        coverage = 0
    elif isinstance(result_data, dict):
        testcases = result_data.get("testcases", [])
        coverage = result_data.get("coverage", 0)
    elif isinstance(result_data, str):
        if result_data.strip().startswith("|"):
            testcases = parse_markdown_table(result_data)
            logger.info(f"将 Markdown 表格转换为 JSON，共 {len(testcases)} 条用例")
            coverage = 0
        else:
            testcases = []
            coverage = 0
    else:
        testcases = []
        coverage = 0

    metadata = {
        "title": "测试用例文档",
        "requirement": task.get("task", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(testcases),
        "coverage": coverage
    }

    try:
        markdown_content = markdown_formatter.format(testcases, metadata)
    except Exception as e:
        logger.error(f"Markdown 格式化失败: {e}")
        markdown_content = ""

    try:
        xmind_8_bytes = xmind_formatter.format_8(testcases, metadata)
    except Exception as e:
        logger.error(f"XMind 8 格式化失败: {e}")
        xmind_8_bytes = b""
        xmind_8_failed = True
    else:
        xmind_8_failed = False

    try:
        xmind_2023_bytes = xmind_formatter.format_2023(testcases, metadata)
    except Exception as e:
        logger.error(f"XMind 2023 格式化失败: {e}")
        xmind_2023_bytes = b""
        xmind_2023_failed = True
    else:
        xmind_2023_failed = False

    # 确保结果目录存在
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # 定义文件名（使用 task_id）
    json_path = RESULT_DIR / f"{task_id}.json"
    md_path = RESULT_DIR / f"{task_id}.md"
    xmind_8_path = RESULT_DIR / f"{task_id}_xmind8.xmind"
    xmind_2023_path = RESULT_DIR / f"{task_id}_xmind2023.xmind"

    # 保存 JSON 文件
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON 文件已保存: {json_path}")
    except Exception as e:
        logger.error(f"保存 JSON 文件失败: {e}")
        json_path = None

    # 保存 Markdown 文件
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Markdown 文件已保存: {md_path}")
    except Exception as e:
        logger.error(f"保存 Markdown 文件失败: {e}")
        md_path = None

    # 保存 XMind 8 文件
    try:
        with open(xmind_8_path, "wb") as f:
            f.write(xmind_8_bytes)
        logger.info(f"XMind 8 文件已保存: {xmind_8_path}")
    except Exception as e:
        logger.error(f"保存 XMind 8 文件失败: {e}")
        xmind_8_path = None

    # 保存 XMind 2023 文件
    try:
        with open(xmind_2023_path, "wb") as f:
            f.write(xmind_2023_bytes)
        logger.info(f"XMind 2023 文件已保存: {xmind_2023_path}")
    except Exception as e:
        logger.error(f"保存 XMind 2023 文件失败: {e}")
        xmind_2023_path = None

    xmind_formats = XMindFormats(
        xmind_8=xmind_formatter.encode_base64(xmind_8_bytes),
        xmind_2023=xmind_formatter.encode_base64(xmind_2023_bytes),
        xmind_8_filename=f"{task_id}_xmind8.xmind",
        xmind_2023_filename=f"{task_id}_xmind2023.xmind"
    )

    multi_format_result = MultiFormatResult(
        json=result_data,
        markdown=markdown_content,
        xmind=xmind_formats
    )

    result = {
        "result": multi_format_result,
        "files": {
            "json": str(json_path) if json_path else None,
            "markdown": str(md_path) if md_path else None,
            "xmind_8": str(xmind_8_path) if xmind_8_path else None,
            "xmind_2023": str(xmind_2023_path) if xmind_2023_path else None
        }
    }

    logger.info(f"返回多格式结果，Markdown: {len(markdown_content)} 字符，XMind: {len(xmind_8_bytes)} 字节")
    return result


@router.get(
    "/logs/{task_id}",
    response_model=LogResponse,
    responses={404: {"description": "任务不存在"}}
)
async def get_task_logs(task_id: str) -> dict:
    logger.info(f"查询任务日志: {task_id}")
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
