# -*- coding: utf-8 -*-
import time
from collections import defaultdict
from typing import Dict, List, Optional

from config.config import Config


class RateLimiter:
    """可配置的 IP 限流器
    
    使用滑动窗口算法实现限流，支持按 IP 地址限制请求频率。
    配置项支持通过环境变量动态调整。
    """
    
    _instance: Optional["RateLimiter"] = None
    
    def __init__(self, max_requests: Optional[int] = None, window_seconds: Optional[int] = None):
        """
        Args:
            max_requests: 时间窗口内最大请求数，默认为配置文件中的值
            window_seconds: 时间窗口大小（秒），默认为配置文件中的值
        """
        self._max_requests = max_requests if max_requests is not None and max_requests > 0 else Config.API_RATE_LIMIT_PER_MINUTE
        self._window = window_seconds if window_seconds is not None and window_seconds > 0 else Config.API_RATE_LIMIT_WINDOW_SECONDS
        self._store: Dict[str, List[float]] = defaultdict(list)
    
    @classmethod
    def get_instance(cls) -> "RateLimiter":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = RateLimiter()
        return cls._instance
    
    def check(self, ip: str) -> bool:
        """检查是否允许请求
        
        Args:
            ip: 客户端 IP 地址
        
        Returns:
            True: 允许请求
            False: 请求被限流
        """
        now = time.time()
        requests = self._store[ip]
        
        requests = [t for t in requests if now - t < self._window]
        
        if len(requests) >= self._max_requests:
            self._store[ip] = requests
            return False
        
        requests.append(now)
        self._store[ip] = requests

        self._cleanup_expired(now)
        return True

    def _cleanup_expired(self, now: float) -> None:
        """清理所有过期 IP 的请求记录"""
        expired_ips = [
            ip for ip, reqs in self._store.items()
            if not reqs or all(now - t >= self._window for t in reqs)
        ]
        for ip in expired_ips:
            del self._store[ip]
    
    def get_remaining(self, ip: str) -> int:
        """获取剩余请求次数
        
        Args:
            ip: 客户端 IP 地址
        
        Returns:
            剩余可用请求次数
        """
        now = time.time()
        requests = [t for t in self._store[ip] if now - t < self._window]
        return max(0, self._max_requests - len(requests))
    
    def reset(self, ip: str) -> None:
        """重置指定 IP 的限流计数
        
        Args:
            ip: 客户端 IP 地址
        """
        if ip in self._store:
            del self._store[ip]
    
    def reset_all(self) -> None:
        """重置所有 IP 的限流计数"""
        self._store.clear()
    
    def update_settings(self, max_requests: int, window_seconds: int) -> None:
        """动态更新限流设置
        
        Args:
            max_requests: 新的最大请求数
            window_seconds: 新的时间窗口（秒）
        """
        if max_requests <= 0:
            raise ValueError("max_requests 必须大于 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds 必须大于 0")
        
        self._max_requests = max_requests
        self._window = window_seconds
        self._store.clear()
    
    def get_settings(self) -> Dict[str, int]:
        """获取当前限流设置"""
        return {
            "max_requests": self._max_requests,
            "window_seconds": self._window
        }
