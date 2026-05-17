# -*- coding: utf-8 -*-
from typing import Callable, Dict, List

from utils.logger import logger

_PARSERS: Dict[str, Callable] = {}


def register(domain_pattern):
    def decorator(func: Callable):
        if isinstance(domain_pattern, (list, tuple)):
            for p in domain_pattern:
                _PARSERS[p] = func
        else:
            _PARSERS[domain_pattern] = func
        return func
    return decorator


from utils.parsers import feishu  # noqa: E402, F401
from utils.parsers import tapd  # noqa: E402, F401
from utils.parsers import yuque  # noqa: E402, F401
from utils.parsers import shimo  # noqa: E402, F401
from utils.parsers import confluence  # noqa: E402, F401


def _match_parser(url: str):
    for pattern, parser in _PARSERS.items():
        if pattern in url:
            return parser
    return None


async def parse_doc_url(url: str) -> str:
    parser = _match_parser(url)
    if parser:
        logger.info(f"文档链接匹配平台: {url}")
        return await parser(url)
    raise ValueError(f"不支持的文档链接: {url}")


def check_doc_support(url: str) -> None:
    parser = _match_parser(url)
    if parser:
        check_fn = getattr(parser, "_check_support", None)
        if check_fn:
            check_fn()
        return
    raise ValueError(f"不支持的文档链接: {url}")


def get_supported_platforms() -> list:
    return list(_PARSERS.keys())
