# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from api.schemas import TaskResponse
from api.services.knowledge_service import (
    submit_knowledge_task,
    get_knowledge_task_status,
    get_knowledge_task_result,
    refresh_knowledge_base
)
from storage.knowledge_repositories import get_knowledge_base, list_knowledge_bases, get_knowledge_items, get_changed_items, get_knowledge_base_with_items


def _format_datetime(dt_str: str) -> str:
    """格式化 ISO 时间戳为可读格式"""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/extract", response_model=TaskResponse)
async def extract_knowledge(case_ids: List[str]):
    """
    提交知识提取任务
    
    Args:
        case_ids: 用例 ID 列表
        
    Returns:
        任务 ID
    """
    if not case_ids:
        raise HTTPException(status_code=400, detail="用例 ID 列表不能为空")
    
    task_id = str(uuid.uuid4())
    result = await submit_knowledge_task(task_id, case_ids)
    return result


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询知识提取任务状态
    
    Args:
        task_id: 任务 ID
        
    Returns:
        任务状态信息
    """
    status = await get_knowledge_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """
    获取知识提取任务结果
    
    Args:
        task_id: 任务 ID
        
    Returns:
        提取结果
    """
    result = await get_knowledge_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在或无结果")
    return result


@router.get("/bases")
async def list_bases(status: Optional[str] = "active"):
    """
    查询知识库列表
    
    Args:
        status: 知识库状态筛选
        
    Returns:
        知识库列表
    """
    bases = list_knowledge_bases(status)
    # 格式化返回数据
    formatted = []
    for b in bases:
        modules = b.get("modules", [])
        if isinstance(modules, str):
            import json
            try:
                modules = json.loads(modules)
            except Exception:
                modules = []
        formatted.append({
            "id": b.get("id", ""),
            "title": b.get("title", ""),
            "modules": modules,
            "item_count": b.get("item_count", 0),
            "created_at": _format_datetime(b.get("created_at", "")),
            "updated_at": _format_datetime(b.get("updated_at", "")),
        })
    return {"total": len(formatted), "items": formatted}


@router.get("/bases/{kb_id}")
async def get_base_detail(kb_id: str):
    """
    查询知识库详情
    
    Args:
        kb_id: 知识库 ID
        
    Returns:
        知识库详情（含所有知识点）
    """
    try:
        # 使用合并查询减少数据库访问次数
        kb = get_knowledge_base_with_items(kb_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 格式化返回（items 和 changes 已包含在 kb 中）
    result = {
        "id": kb["id"],
        "title": kb["title"],
        "description": kb.get("description", ""),
        "markdown_content": kb.get("markdown_content", ""),
        "status": kb["status"],
        "created_at": _format_datetime(kb.get("created_at", "")),
        "updated_at": _format_datetime(kb.get("updated_at", "")),
        "items": kb.get("items", []),
        "changes": kb.get("changes", [])
    }
    
    return result


@router.put("/bases/{kb_id}/refresh")
async def refresh_base(kb_id: str, case_ids: Optional[List[str]] = None):
    """
    刷新知识库（增量更新）
    
    检测用例变更并增量更新知识库中的知识点。
    使用时间戳对比检测变更，基于用例ID进行冲突解决。
    
    Args:
        kb_id: 知识库 ID
        case_ids: 可选，指定要更新的用例ID列表；不指定则检查所有源用例
    
    Returns:
        更新结果
    """
    try:
        result = await refresh_knowledge_base(kb_id, case_ids)
        return result
    except ValueError:
        raise HTTPException(status_code=404, detail="知识库不存在")
