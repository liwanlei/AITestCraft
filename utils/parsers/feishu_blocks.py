# -*- coding: utf-8 -*-
from utils.logger import logger

_BLOCK_TYPE_PAGE = 1
_BLOCK_TYPE_TEXT = 2
_BLOCK_TYPE_H1 = 3
_BLOCK_TYPE_H2 = 4
_BLOCK_TYPE_H3 = 5
_BLOCK_TYPE_H4 = 6
_BLOCK_TYPE_H5 = 7
_BLOCK_TYPE_H6 = 8
_BLOCK_TYPE_H7 = 9
_BLOCK_TYPE_H8 = 10
_BLOCK_TYPE_H9 = 11
_BLOCK_TYPE_BULLET = 12
_BLOCK_TYPE_ORDERED = 13
_BLOCK_TYPE_CODE = 14
_BLOCK_TYPE_QUOTE = 15
_BLOCK_TYPE_TODO = 16
_BLOCK_TYPE_DIVIDER = 23
_BLOCK_TYPE_TABLE = 24

_HEADING_BLOCK_MAP = {
    _BLOCK_TYPE_H1: ("heading1", "# "),
    _BLOCK_TYPE_H2: ("heading2", "## "),
    _BLOCK_TYPE_H3: ("heading3", "### "),
    _BLOCK_TYPE_H4: ("heading4", "#### "),
    _BLOCK_TYPE_H5: ("heading5", "##### "),
    _BLOCK_TYPE_H6: ("heading6", "###### "),
    _BLOCK_TYPE_H7: ("heading7", "####### "),
    _BLOCK_TYPE_H8: ("heading8", "######## "),
    _BLOCK_TYPE_H9: ("heading9", "######### "),
}


def _extract_text(elements: list) -> str:
    parts = []
    for el in elements:
        text_run = el.get("text_run") or el.get("text_element")
        if text_run:
            content = text_run.get("content", "")
            parts.append(content)
    return "".join(parts)


def block_to_markdown(block: dict) -> str:
    block_type = block.get("block_type")

    if block_type == _BLOCK_TYPE_PAGE:
        return ""
    if block_type == _BLOCK_TYPE_TEXT:
        text = _extract_text(block.get("paragraph", {}).get("elements", []))
        return text
    if block_type in _HEADING_BLOCK_MAP:
        key, prefix = _HEADING_BLOCK_MAP[block_type]
        text = _extract_text(block.get(key, {}).get("elements", []))
        return f"{prefix}{text}"
    if block_type == _BLOCK_TYPE_BULLET:
        text = _extract_text(block.get("bullet", {}).get("elements", []))
        return f"- {text}"
    if block_type == _BLOCK_TYPE_ORDERED:
        text = _extract_text(block.get("ordered", {}).get("elements", []))
        return f"1. {text}"
    if block_type == _BLOCK_TYPE_CODE:
        code_block = block.get("code", {})
        text = _extract_text(code_block.get("elements", []))
        lang = code_block.get("language", "")
        return f"```{lang}\n{text}\n```"
    if block_type == _BLOCK_TYPE_QUOTE:
        text = _extract_text(block.get("quote", {}).get("elements", []))
        return f"> {text}"
    if block_type == _BLOCK_TYPE_TODO:
        todo = block.get("todo", {})
        text = _extract_text(todo.get("elements", []))
        checked = "x" if todo.get("style", 0) == 1 else " "
        return f"- [{checked}] {text}"
    if block_type in (_BLOCK_TYPE_DIVIDER, _BLOCK_TYPE_TABLE):
        return ""

    logger.debug(f"未处理的飞书块类型: {block_type}")
    return ""
