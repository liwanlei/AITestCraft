# -*- coding: utf-8 -*-
import re
import time
from typing import Optional

from utils.logger import logger
from utils.parsers import register
from utils.parsers._http import async_get, async_post

_SHIMO_DOC_PATTERN = re.compile(r"shimo\.im/docs/([A-Za-z0-9]+)")
_SHIMO_API_BASE = "https://open.shimo.im"

_cached_token: Optional[str] = None
_token_expires_at: float = 0.0


def _check_support() -> None:
    from config.config import Config
    if not Config.SHIMO_CLIENT_ID or not Config.SHIMO_CLIENT_SECRET:
        raise RuntimeError("石墨解析功能未配置，请在 .env 中设置 SHIMO_CLIENT_ID 和 SHIMO_CLIENT_SECRET")


async def _get_access_token() -> str:
    global _cached_token, _token_expires_at

    from config.config import Config
    if Config.SHIMO_API_TOKEN:
        return Config.SHIMO_API_TOKEN

    now = time.time()
    if _cached_token and now < _token_expires_at:
        return _cached_token

    resp = await async_post(
        f"{_SHIMO_API_BASE}/oauth2/token",
        json={
            "grant_type": "client_credentials",
            "client_id": Config.SHIMO_CLIENT_ID,
            "client_secret": Config.SHIMO_CLIENT_SECRET,
            "scope": "read",
        },
    )
    if resp.status_code != 200:
        raise PermissionError(f"石墨认证失败: HTTP {resp.status_code}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise PermissionError("石墨认证失败: 未获取到 access_token")

    _cached_token = token
    expires_in = max(data.get("expires_in", 7200), 60)  # 确保至少 60 秒有效期
    _token_expires_at = now + expires_in - 60

    return token


def _match_shimo_url(url: str) -> Optional[str]:
    m = _SHIMO_DOC_PATTERN.search(url)
    if m:
        return m.group(1)
    return None


@register("shimo.im")
async def parse_shimo_url(url: str) -> str:
    _check_support()

    doc_id = _match_shimo_url(url)
    if not doc_id:
        raise ValueError(f"不支持的石墨链接格式: {url}，需要格式: shimo.im/docs/{id}")

    logger.info(f"解析石墨文档: {doc_id}")
    token = await _get_access_token()

    resp = await async_get(
        f"{_SHIMO_API_BASE}/api/v2/files/{doc_id}/content",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 401:
        raise PermissionError("石墨 token 无效或已过期")
    if resp.status_code == 404:
        raise FileNotFoundError("石墨文档不存在或无访问权限")
    if resp.status_code != 200:
        raise RuntimeError(f"石墨 API 调用失败: HTTP {resp.status_code}")

    data = resp.json()
    content = data.get("content", "")
    if not content:
        logger.warning(f"石墨文档 {doc_id} 无内容")
        return ""

    if isinstance(content, dict):
        text = content.get("text", str(content))
    else:
        text = str(content)

    logger.info(f"石墨文档解析完成: {doc_id}, {len(text)} 字符")
    return text


parse_shimo_url._check_support = _check_support
