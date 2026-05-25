# -*- coding: utf-8 -*-
import re
from typing import Optional

from utils.logger import logger
from utils.parsers import register
from utils.parsers._http import async_get
from utils.parsers.feishu_blocks import block_to_markdown

_FEISHU_DOC_PATTERN = re.compile(r"feishu\.cn/docx/([A-Za-z0-9]+)")
_FEISHU_WIKI_PATTERN = re.compile(r"feishu\.cn/wiki/([A-Za-z0-9]+)")
_FEISHU_BITABLE_PATTERN = re.compile(r"feishu\.cn/base/([A-Za-z0-9]+)")

_FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


def _mask_token(token: str, show_chars: int = 6) -> str:
    """脱敏 token，只显示前几个字符"""
    if not token or len(token) <= show_chars:
        return "***"
    return f"{token[:show_chars]}..."


def _check_support() -> None:
    from config.config import Config
    if not Config.FEISHU_USER_ACCESS_TOKEN:
        raise RuntimeError("飞书解析功能未配置，请在 .env 中设置 FEISHU_USER_ACCESS_TOKEN")


def _match_feishu_url(url: str) -> tuple:
    m = _FEISHU_DOC_PATTERN.search(url)
    if m:
        return ("doc", m.group(1))
    m = _FEISHU_WIKI_PATTERN.search(url)
    if m:
        return ("wiki", m.group(1))
    m = _FEISHU_BITABLE_PATTERN.search(url)
    if m:
        return ("bitable", m.group(1))
    return (None, None)


def _get_headers() -> dict:
    from config.config import Config
    return {
        "Authorization": f"Bearer {Config.FEISHU_USER_ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }


async def _feishu_get(path: str, params: Optional[dict] = None) -> dict:
    resp = await async_get(
        f"{_FEISHU_API_BASE}{path}",
        headers=_get_headers(),
        params=params,
    )
    data = resp.json()
    if data.get("code", -1) != 0:
        msg = data.get("msg", "unknown error")
        logger.error(f"飞书 API 错误: {resp.status_code} code={data.get('code')} msg={msg}")
        if resp.status_code == 401 or data.get("code") == 99991663:
            raise PermissionError(f"飞书 token 无效或已过期: {msg}")
        if resp.status_code == 404 or data.get("code") == 99991668:
            raise FileNotFoundError(f"飞书文档不存在或无访问权限: {msg}")
        raise RuntimeError(f"飞书 API 调用失败: {msg}")
    return data


async def _parse_feishu_doc(token: str) -> str:
    logger.info(f"解析飞书文档: {_mask_token(token)}")
    
    all_items = []
    page_token = None
    page_count = 0
    max_pages = 100  # 防止无限循环
    
    while page_count < max_pages:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        data = await _feishu_get(f"/docx/v1/documents/{token}/blocks", params=params)
        items = data.get("data", {}).get("items", [])
        all_items.extend(items)
        
        has_more = data.get("data", {}).get("has_more", False)
        page_token = data.get("data", {}).get("page_token")
        
        page_count += 1
        
        if not has_more or not page_token:
            break

    if not all_items:
        logger.warning(f"飞书文档 {token} 无内容块")
        return ""

    lines = []
    for block in all_items:
        md = block_to_markdown(block)
        if md:
            lines.append(md)

    text = "\n\n".join(lines)
    logger.info(f"飞书文档解析完成: {_mask_token(token)}, {len(text)} 字符, 共 {page_count} 页")
    return text


async def _parse_feishu_wiki(token: str) -> str:
    logger.info(f"解析飞书知识库文档: {_mask_token(token)}")
    data = await _feishu_get("/wiki/v2/spaces/get_node", params={"token": token})
    node = data.get("data", {}).get("node", {})
    obj_type = node.get("obj_type", "")
    obj_token = node.get("obj_token", "")

    if obj_type == "docx" and obj_token:
        return await _parse_feishu_doc(obj_token)

    if obj_type == "doc" and obj_token:
        doc_data = await _feishu_get(f"/doc/v2/{obj_token}", params={"lang": "zh"})
        content = doc_data.get("data", {}).get("content", "")
        if content:
            logger.info(f"飞书旧版文档解析完成: {_mask_token(token)}, {len(content)} 字符")
            return content
        logger.warning(f"飞书旧版文档 {token} 无内容")
        return ""

    logger.warning(f"不支持的知识库文档类型: {obj_type}")
    return ""


async def _parse_feishu_bitable(token: str) -> str:
    logger.info(f"解析飞书多维表格: {_mask_token(token)}")
    tables_data = await _feishu_get(f"/bitable/v1/apps/{token}/tables")
    tables = tables_data.get("data", {}).get("items", [])
    if not tables:
        logger.warning(f"飞书多维表格 {token} 无表")
        return ""

    parts = []
    for table in tables:
        table_id = table.get("table_id", "")
        table_name = table.get("name", "未命名表")
        parts.append(f"## {table_name}")

        records_data = await _feishu_get(
            f"/bitable/v1/apps/{token}/tables/{table_id}/records",
            params={"page_size": 100},
        )
        records = records_data.get("data", {}).get("items", [])
        if not records:
            parts.append("（无记录）\n")
            continue

        fields = list(records[0].get("fields", {}).keys())
        header = "| " + " | ".join(fields) + " |"
        separator = "| " + " | ".join(["---"] * len(fields)) + " |"
        parts.append(header)
        parts.append(separator)

        for record in records:
            row_values = []
            for field in fields:
                cell = record.get("fields", {}).get(field, "")
                cell_text = str(cell) if not isinstance(cell, list) else "; ".join(
                    str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in cell
                )
                row_values.append(cell_text)
            parts.append("| " + " | ".join(row_values) + " |")

        parts.append("")

    text = "\n".join(parts)
    logger.info(f"飞书多维表格解析完成: {_mask_token(token)}, {len(text)} 字符")
    return text


@register("feishu.cn")
async def parse_feishu_url(url: str) -> str:
    _check_support()

    link_type, token = _match_feishu_url(url)
    if not link_type:
        raise ValueError(f"不支持的飞书链接格式: {url}")

    logger.info(f"飞书链接类型: {link_type}, token: {_mask_token(token)}")

    if link_type == "doc":
        return await _parse_feishu_doc(token)
    elif link_type == "wiki":
        return await _parse_feishu_wiki(token)
    elif link_type == "bitable":
        return await _parse_feishu_bitable(token)
    else:
        raise ValueError(f"不支持的飞书链接类型: {link_type}")


parse_feishu_url._check_support = _check_support
