# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.rate_limiter import RateLimiter
from utils.logger import logger

router = APIRouter()

rate_limiter = RateLimiter.get_instance()


@router.get("/rate-limit/settings")
async def get_rate_limit_settings() -> dict:
    """获取当前限流设置"""
    return rate_limiter.get_settings()


@router.put("/rate-limit/settings")
async def update_rate_limit_settings(max_requests: int, window_seconds: int) -> dict:
    """更新限流设置
    
    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口大小（秒）
    """
    try:
        rate_limiter.update_settings(max_requests, window_seconds)
        return {
            "message": "限流设置更新成功",
            "settings": rate_limiter.get_settings()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rate-limit/reset")
async def reset_rate_limit(ip: Optional[str] = None) -> dict:
    """重置限流计数
    
    Args:
        ip: 可选，指定要重置的 IP 地址，不指定则重置所有
    """
    if ip:
        rate_limiter.reset(ip)
        return {"message": f"IP {ip} 的限流计数已重置"}
    else:
        rate_limiter.reset_all()
        return {"message": "所有限流计数已重置"}
