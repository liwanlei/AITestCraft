# -*- coding: utf-8 -*-
import re
from typing import Optional

from utils.logger import logger
from utils.parsers import register
from utils.parsers._http import async_get

_TAPD_STORY_PATTERN = re.compile(r"tapd\.cn/.*?/stories?/view/(\d+)")
_TAPD_API_BASE = "https://api.tapd.cn"


def _check_support() -> None:
    from config.config import Config
    if not Config.TAPD_API_USER or not Config.TAPD_API_PASSWORD:
        raise RuntimeError("TAPD 解析功能未配置，请在 .env 中设置 TAPD_API_USER 和 TAPD_API_PASSWORD")


def _get_auth() -> tuple:
    from config.config import Config
    return (Config.TAPD_API_USER, Config.TAPD_API_PASSWORD)


def _match_tapd_url(url: str) -> Optional[str]:
    m = _TAPD_STORY_PATTERN.search(url)
    if m:
        return m.group(1)
    return None


async def _tapd_get(path: str, params: Optional[dict] = None) -> dict:
    resp = await async_get(
        f"{_TAPD_API_BASE}{path}",
        auth=_get_auth(),
        params=params,
    )
    if resp.status_code == 401:
        raise PermissionError("TAPD 认证失败，请检查 TAPD_API_USER 和 TAPD_API_PASSWORD")
    if resp.status_code == 404:
        raise FileNotFoundError("TAPD 需求不存在或无访问权限")
    if resp.status_code != 200:
        raise RuntimeError(f"TAPD API 调用失败: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("status") != 1:
        raise RuntimeError(f"TAPD API 错误: {data.get('info', 'unknown')}")
    return data


def _story_to_markdown(story: dict) -> str:
    lines = []
    name = story.get("name", "")
    if name:
        lines.append(f"# {name}")

    category = story.get("category", "")
    if category:
        lines.append(f"**分类**: {category}")

    priority = story.get("priority", "")
    priority_map = {"1": "高", "2": "中", "3": "低", "4": "低"}
    if priority:
        lines.append(f"**优先级**: {priority_map.get(priority, priority)}")

    status = story.get("status", "")
    if status:
        lines.append(f"**状态**: {status}")

    owner = story.get("owner", "")
    if owner:
        lines.append(f"**负责人**: {owner}")

    description = story.get("description", "")
    if description:
        lines.append("")
        lines.append(description.strip())

    return "\n\n".join(lines)


@register("tapd.cn")
async def parse_tapd_url(url: str) -> str:
    _check_support()

    story_id = _match_tapd_url(url)
    if not story_id:
        raise ValueError(f"不支持的 TAPD 链接格式: {url}，需要包含 /stories/view/{id}")

    logger.info(f"解析 TAPD 需求: {story_id}")
    data = await _tapd_get(f"/stories/{story_id}")
    story = data.get("data", {})
    if not story:
        raise FileNotFoundError(f"TAPD 需求 {story_id} 不存在或无访问权限")

    text = _story_to_markdown(story)
    logger.info(f"TAPD 需求解析完成: {story_id}, {len(text)} 字符")
    return text


parse_tapd_url._check_support = _check_support
