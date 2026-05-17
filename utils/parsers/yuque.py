# -*- coding: utf-8 -*-
import re
from typing import Optional

from utils.logger import logger
from utils.parsers import register
from utils.parsers._http import async_get

_YUQUE_DOC_PATTERN = re.compile(r"yuque\.com/([\w-]+)/([\w-]+)/([\w-]+)")
_YUQUE_API_BASE = "https://www.yuque.com/api/v2"


def _check_support() -> None:
    from config.config import Config
    if not Config.YUQUE_API_TOKEN:
        raise RuntimeError("语雀解析功能未配置，请在 .env 中设置 YUQUE_API_TOKEN")


def _get_headers() -> dict:
    from config.config import Config
    return {
        "X-Auth-Token": Config.YUQUE_API_TOKEN,
        "Content-Type": "application/json",
    }


def _match_yuque_url(url: str) -> Optional[tuple]:
    m = _YUQUE_DOC_PATTERN.search(url)
    if m:
        return (m.group(1), m.group(2), m.group(3))
    return None


async def _yuque_get(path: str, params: Optional[dict] = None) -> dict:
    resp = await async_get(
        f"{_YUQUE_API_BASE}{path}",
        headers=_get_headers(),
        params=params,
    )
    if resp.status_code == 401:
        raise PermissionError("语雀 token 无效或已过期")
    if resp.status_code == 404:
        raise FileNotFoundError("语雀文档不存在或无访问权限")
    if resp.status_code != 200:
        raise RuntimeError(f"语雀 API 调用失败: HTTP {resp.status_code}")
    return resp.json()


@register("yuque.com")
async def parse_yuque_url(url: str) -> str:
    _check_support()

    match = _match_yuque_url(url)
    if not match:
        raise ValueError(f"不支持的语雀链接格式: {url}，需要格式: yuque.com/{group}/{repo}/{slug}")

    group, repo, slug = match
    logger.info(f"解析语雀文档: {group}/{repo}/{slug}")

    data = await _yuque_get(f"/repos/{group}/{repo}/docs/{slug}")
    doc = data.get("data", {})
    if not doc:
        raise FileNotFoundError(f"语雀文档 {group}/{repo}/{slug} 不存在或无访问权限")

    title = doc.get("title", "")
    body = doc.get("body", "") or doc.get("body_html", "")

    if not body:
        logger.warning(f"语雀文档 {slug} 无内容")
        return title

    text = f"# {title}\n\n{body}" if title else body
    logger.info(f"语雀文档解析完成: {slug}, {len(text)} 字符")
    return text


parse_yuque_url._check_support = _check_support
