# -*- coding: utf-8 -*-
import re
from html.parser import HTMLParser
from typing import Optional

from utils.logger import logger
from utils.parsers import register
from utils.parsers._http import async_get

_CONFLUENCE_PAGE_ID_PATTERN = re.compile(r"pageId=(\d+)")
_CONFLUENCE_PAGES_PATTERN = re.compile(r"/pages/(\d+)")


class _HtmlToMarkdownConverter(HTMLParser):
    def __init__(self):
        super().__init__()
        self._result: list[str] = []
        self._tag_stack: list[str] = []
        self._list_counter: list[int] = []
        self._current_href: str = ""
        self._in_table: bool = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._in_cell: bool = False

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._result.append(f"\n{'#' * level} ")
        elif tag == "li":
            if self._list_counter:
                idx = self._list_counter[-1]
                self._result.append(f"\n{idx}. ")
                self._list_counter[-1] = idx + 1
            else:
                self._result.append("\n- ")
        elif tag == "strong" or tag == "b":
            self._result.append("**")
        elif tag == "em" or tag == "i":
            self._result.append("*")
        elif tag == "code":
            self._result.append("`")
        elif tag == "pre":
            self._result.append("\n```\n")
        elif tag == "blockquote":
            self._result.append("\n> ")
        elif tag == "br":
            self._result.append("\n")
        elif tag == "ul":
            self._list_counter.append(0)
        elif tag == "ol":
            self._list_counter.append(1)
        elif tag == "a":
            self._current_href = dict(attrs).get("href", "")
            self._result.append("[")
        elif tag == "table":
            self._in_table = True
            self._table_rows = []
        elif tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._current_row.append("")
        elif tag == "img":
            src = dict(attrs).get("src", "")
            alt = dict(attrs).get("alt", "")
            if alt:
                self._result.append(f"![{alt}]({src})")
            else:
                self._result.append(f"![]({src})")
        elif tag in ("video", "iframe", "embed"):
            src = dict(attrs).get("src", "")
            self._result.append(f"[媒体内容]({src})")
        else:
            logger.debug(f"Confluence HTMLParser: 未处理的开始标签 <{tag}>")

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag == "strong" or tag == "b":
            self._result.append("**")
        elif tag == "em" or tag == "i":
            self._result.append("*")
        elif tag == "code":
            self._result.append("`")
        elif tag == "pre":
            self._result.append("\n```")
        elif tag == "a":
            self._result.append("]")
            if self._current_href:
                self._result.append(f"({self._current_href})")
                self._current_href = ""
        elif tag in ("ul", "ol"):
            if self._list_counter:
                self._list_counter.pop()
        elif tag == "p":
            self._result.append("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.append("\n")
        elif tag in ("td", "th"):
            self._in_cell = False
        elif tag == "tr":
            if self._current_row:
                self._table_rows.append(self._current_row)
            self._current_row = []
        elif tag == "table":
            self._in_table = False
            if self._table_rows:
                self._result.append("\n")
                for i, row in enumerate(self._table_rows):
                    self._result.append("| " + " | ".join(v.strip() for v in row) + " |\n")
                    if i == 0:
                        self._result.append("| " + " | ".join(["---"] * len(row)) + " |\n")
            self._table_rows = []
            self._current_row = []

    def handle_data(self, data):
        if self._in_cell:
            if self._current_row:
                self._current_row[-1] += data
            else:
                self._current_row.append(data)
        else:
            self._result.append(data)

    def get_markdown(self) -> str:
        text = "".join(self._result)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _check_support() -> None:
    from config.config import Config
    if not Config.CONFLUENCE_BASE_URL or not Config.CONFLUENCE_EMAIL or not Config.CONFLUENCE_API_TOKEN:
        raise RuntimeError("Confluence 解析功能未配置，请在 .env 中设置 CONFLUENCE_BASE_URL、CONFLUENCE_EMAIL 和 CONFLUENCE_API_TOKEN")


def _get_auth() -> tuple:
    from config.config import Config
    return (Config.CONFLUENCE_EMAIL, Config.CONFLUENCE_API_TOKEN)


def _get_base_url() -> str:
    from config.config import Config
    return Config.CONFLUENCE_BASE_URL.rstrip("/")


def _match_confluence_url(url: str) -> Optional[str]:
    m = _CONFLUENCE_PAGE_ID_PATTERN.search(url)
    if m:
        return m.group(1)
    m = _CONFLUENCE_PAGES_PATTERN.search(url)
    if m:
        return m.group(1)
    return None


def _html_to_markdown(html: str) -> str:
    converter = _HtmlToMarkdownConverter()
    converter.feed(html)
    return converter.get_markdown()


@register(["confluence", "atlassian.net"])
async def parse_confluence_url(url: str) -> str:
    _check_support()

    page_id = _match_confluence_url(url)
    if not page_id:
        raise ValueError(
            f"不支持的 Confluence 链接格式: {url}，"
            "需要包含 pageId=xxx 或 /pages/xxx"
        )

    base_url = _get_base_url()
    logger.info(f"解析 Confluence 页面: {page_id}")

    resp = await async_get(
        f"{base_url}/rest/api/content/{page_id}",
        auth=_get_auth(),
        params={"expand": "body.storage"},
    )
    if resp.status_code == 401:
        raise PermissionError("Confluence 认证失败，请检查 CONFLUENCE_EMAIL 和 CONFLUENCE_API_TOKEN")
    if resp.status_code == 404:
        raise FileNotFoundError(f"Confluence 页面 {page_id} 不存在或无访问权限")
    if resp.status_code != 200:
        raise RuntimeError(f"Confluence API 调用失败: HTTP {resp.status_code}")

    data = resp.json()
    title = data.get("title", "")
    html_body = data.get("body", {}).get("storage", {}).get("value", "")

    if not html_body:
        logger.warning(f"Confluence 页面 {page_id} 无内容")
        return title

    md_body = _html_to_markdown(html_body)
    text = f"# {title}\n\n{md_body}" if title else md_body

    logger.info(f"Confluence 页面解析完成: {page_id}, {len(text)} 字符")
    return text


parse_confluence_url._check_support = _check_support
