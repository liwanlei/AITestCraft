# -*- coding: utf-8 -*-
import json
import re
from typing import Any, Dict, List, Union

from jsonschema import validate, ValidationError

from utils.exceptions import JSONParseError, SchemaValidationError
from utils.logger import logger


def _find_json_boundary(text: str) -> str:
    """查找文本中的完整JSON边界"""
    stack = []
    start = None
    brace_map = {'{': '}', '[': ']'}
    
    for i, char in enumerate(text):
        if char in brace_map:
            if not stack:
                start = i
            stack.append(char)
        elif char in brace_map.values():
            if stack:
                opening = stack.pop()
                if brace_map[opening] == char and not stack and start is not None:
                    logger.debug(f"JSON边界检测成功: 起始位置 {start}, 结束位置 {i}")
                    return text[start:i+1]
    logger.debug("JSON边界检测未找到完整边界")
    return ""


def safe_loads(text: Union[str, Dict, List]) -> Any:
    if not text:
        logger.warning("JSON解析失败: 空响应")
        raise JSONParseError("空响应")

    if isinstance(text, (dict, list)):
        logger.debug("JSON解析: 输入已是字典或列表")
        return text

    text_str = str(text)
    text_str = text_str.strip()
    
    logger.debug(f"JSON解析: 原始文本长度 {len(text_str)}")

    text_str = re.sub(r"^```json\s*", "", text_str)
    text_str = re.sub(r"\s*```$", "", text_str)
    text_str = text_str.strip()
    
    logger.debug(f"JSON解析: 去除代码块标记后长度 {len(text_str)}")

    candidate = _find_json_boundary(text_str)
    if candidate:
        logger.debug(f"JSON解析: 找到候选JSON, 长度 {len(candidate)}")
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析: 首次尝试失败: {e}")

        fixed = candidate.replace("'", '"')
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
        try:
            logger.debug("JSON解析: 尝试修复单引号和尾部逗号")
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析: 修复尝试后仍然失败: {e}")

    try:
        logger.debug("JSON解析: 尝试直接解析")
        return json.loads(text_str, strict=False)
    except json.JSONDecodeError as e:
        logger.debug(f"JSON解析: 直接解析失败: {e}")

    fixed = text_str.replace("'", '"')
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    try:
        logger.debug("JSON解析: 尝试修复后解析")
        return json.loads(fixed, strict=False)
    except Exception as e:
        preview = text_str[:100] + "..." if len(text_str) > 100 else text_str
        logger.warning(f"JSON解析失败: {e}, 原始内容: {preview}")
        raise JSONParseError(f"JSON解析失败: {e}") from e


def validate_schema(data: Any, schema: Dict) -> bool:
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        logger.warning(f"Schema校验失败: {e.message}")
        raise SchemaValidationError(f"Schema校验失败: {e.message}") from e
