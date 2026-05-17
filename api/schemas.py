# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")


class StatusResponse(BaseModel):
    id: str = Field(..., description="任务ID")
    task: str = Field(..., description="任务内容")
    status: str = Field(..., description="任务状态")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class XMindFormats(BaseModel):
    xmind_8: str = Field(..., description="XMind 8 格式，base64 编码")
    xmind_2023: str = Field(..., description="XMind 2023 格式，base64 编码")
    xmind_8_filename: str = Field(..., description="XMind 8 文件名")
    xmind_2023_filename: str = Field(..., description="XMind 2023 文件名")


class MultiFormatResult(BaseModel):
    json_data: Union[Dict[str, Any], List[Any]] = Field(..., alias="json", description="JSON 格式测试用例（支持字典或列表）")
    markdown: str = Field(..., description="Markdown 格式")
    xmind: XMindFormats = Field(..., description="XMind 格式")

    class Config:
        populate_by_name = True


class ResultResponse(BaseModel):
    result: Optional[MultiFormatResult] = Field(None, description="多格式执行结果")
    files: Optional[Dict[str, Optional[str]]] = Field(None, description="结果文件路径")
    message: Optional[str] = Field(None, description="状态消息")
    status: Optional[str] = Field(None, description="任务状态")


class LogResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    logs: List[Dict[str, Any]] = Field(..., description="日志列表")
    total: int = Field(..., description="日志总数")