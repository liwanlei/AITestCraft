# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config.config import Config


class TaskRequest(BaseModel):
    """任务请求模型"""
    task: str = Field(..., description="测试需求内容", max_length=Config.API_MAX_TASK_LENGTH)


class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str = Field(..., description="任务ID")


class StatusResponse(BaseModel):
    """任务状态响应模型"""
    id: str = Field(..., description="任务ID")
    task: str = Field(..., description="任务内容")
    status: str = Field(..., description="任务状态")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class ResultResponse(BaseModel):
    """任务结果响应模型"""
    result: Optional[Any] = Field(None, description="执行结果")


class LogResponse(BaseModel):
    """任务日志响应模型"""
    task_id: str = Field(..., description="任务ID")
    logs: List[Dict[str, Any]] = Field(..., description="日志列表")
    total: int = Field(..., description="日志总数")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    detail: str = Field(..., description="错误信息")
    code: Optional[int] = Field(None, description="错误码")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
