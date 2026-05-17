# -*- coding: utf-8 -*-
from typing import List

from markdown_it import MarkdownIt

from utils.logger import logger

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


def _inline_text(token) -> str:
    if not token.children:
        return token.content
    parts = []
    for child in token.children:
        if child.type == "text":
            parts.append(child.content)
        elif child.type == "code_inline":
            parts.append(child.content)
        elif child.type == "softbreak":
            parts.append(" ")
        elif child.type == "hardbreak":
            parts.append("\n")
        else:
            parts.append(child.content)
    return "".join(parts)


def _build_heading_path(heading_stack: List[str]) -> str:
    if not heading_stack:
        return ""
    return " > ".join(heading_stack)


def parse_markdown(text: str) -> str:
    try:
        return _parse_markdown_impl(text)
    except Exception as e:
        logger.warning(f"Markdown 结构化解析失败，回退到纯文本: {e}")
        return text


def _parse_heading(tokens, i, heading_stack, lines):
    level = _HEADING_TAGS.get(tokens[i].tag, 1)
    i += 1
    if i < len(tokens) and tokens[i].type == "inline":
        title = _inline_text(tokens[i])
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        lines.append(f"[H{level}] {title}")
        i += 1
    if i < len(tokens) and tokens[i].type == "heading_close":
        i += 1
    return i, heading_stack


def _parse_list_item(tokens, i, heading_stack, in_bullet_list, ordered_counter, lines):
    i += 1
    if i < len(tokens) and tokens[i].type == "paragraph_open":
        i += 1
    if i < len(tokens) and tokens[i].type == "inline":
        item_text = _inline_text(tokens[i])
        path = _build_heading_path(heading_stack)
        if in_bullet_list:
            prefix = f"{path} > •" if path else "•"
        elif ordered_counter is not None:
            prefix = f"{path} > {ordered_counter}." if path else f"{ordered_counter}."
        else:
            prefix = path if path else ""
        if prefix:
            lines.append(f"[{prefix}] {item_text}")
        else:
            lines.append(item_text)
        i += 1
    if i < len(tokens) and tokens[i].type == "paragraph_close":
        i += 1
    if i < len(tokens) and tokens[i].type == "list_item_close":
        i += 1
    return i


def _parse_paragraph(tokens, i, in_blockquote, lines):
    i += 1
    if i < len(tokens) and tokens[i].type == "inline":
        content = _inline_text(tokens[i])
        if in_blockquote:
            lines.append(f"[QUOTE] {content}")
        else:
            lines.append(content)
        i += 1
    if i < len(tokens) and tokens[i].type == "paragraph_close":
        i += 1
    return i


def _parse_table_cell(tokens, i, current_row):
    i += 1
    cell_text = ""
    if i < len(tokens) and tokens[i].type == "inline":
        cell_text = _inline_text(tokens[i])
        i += 1
    current_row.append(cell_text)
    i += 1
    return i


def _parse_markdown_impl(text: str) -> str:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    tokens = md.parse(text)

    lines = []
    heading_stack: List[str] = []
    in_bullet_list = False
    in_ordered_list = False
    ordered_counter = 0
    in_blockquote = False
    in_table = False
    table_rows: List[List[str]] = []
    current_row: List[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            i, heading_stack = _parse_heading(tokens, i, heading_stack, lines)
            continue

        elif token.type == "bullet_list_open":
            in_bullet_list = True
            i += 1
            continue

        elif token.type == "bullet_list_close":
            in_bullet_list = False
            i += 1
            continue

        elif token.type == "ordered_list_open":
            in_ordered_list = True
            ordered_counter = 1
            i += 1
            continue

        elif token.type == "ordered_list_close":
            in_ordered_list = False
            i += 1
            continue

        elif token.type == "list_item_open":
            counter = ordered_counter if in_ordered_list else None
            i = _parse_list_item(tokens, i, heading_stack, in_bullet_list, counter, lines)
            if in_ordered_list:
                ordered_counter += 1
            continue

        elif token.type == "blockquote_open":
            in_blockquote = True
            i += 1
            continue

        elif token.type == "blockquote_close":
            in_blockquote = False
            i += 1
            continue

        elif token.type == "paragraph_open":
            i = _parse_paragraph(tokens, i, in_blockquote, lines)
            continue

        elif token.type == "fence":
            lang = token.info.strip() if token.info else ""
            code = token.content.rstrip("\n")
            lang_label = f":{lang}" if lang else ""
            lines.append(f"[CODE{lang_label}]")
            lines.append(code)
            lines.append("[/CODE]")
            i += 1
            continue

        elif token.type == "code_block":
            code = token.content.rstrip("\n")
            lines.append("[CODE]")
            lines.append(code)
            lines.append("[/CODE]")
            i += 1
            continue

        elif token.type == "hr":
            lines.append("---")
            i += 1
            continue

        elif token.type == "table_open":
            in_table = True
            table_rows = []
            current_row = []
            i += 1
            continue

        elif token.type == "table_close":
            in_table = False
            if table_rows:
                lines.append("[TABLE]")
                for row in table_rows:
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("[/TABLE]")
            i += 1
            continue

        elif token.type in ("thead_open", "thead_close", "tbody_open", "tbody_close"):
            i += 1
            continue

        elif token.type == "tr_open":
            current_row = []
            i += 1
            continue

        elif token.type == "tr_close":
            if current_row:
                table_rows.append(current_row)
            i += 1
            continue

        elif token.type in ("th_open", "td_open"):
            i = _parse_table_cell(tokens, i, current_row)
            continue

        else:
            i += 1
            continue

    result = "\n".join(lines)
    logger.info(f"Markdown 结构化解析完成: {len(text)} -> {len(result)} 字符")
    return result
