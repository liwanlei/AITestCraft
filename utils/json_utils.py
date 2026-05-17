# -*- coding: utf-8 -*-
import json
import re
from typing import Any, Dict, List, Union

from jsonschema import validate, ValidationError

from utils.exceptions import JSONParseError, SchemaValidationError
from utils.logger import logger


def _find_json_boundary(text: str) -> str:
    stack = []
    start = None
    brace_map = {'{': '}', '[': ']'}
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue

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

    # 保存原始文本用于错误日志
    original_str = text_str

    # 去除代码块标记
    text_str = re.sub(r"^```json\s*", "", text_str)
    text_str = re.sub(r"\s*```$", "", text_str)
    text_str = text_str.strip()

    logger.debug(f"JSON解析: 去除代码块标记后长度 {len(text_str)}")

    # 查找 JSON 起始位置（跳过前缀文本）
    json_start = -1
    for i, char in enumerate(text_str):
        if char in ['[', '{']:
            json_start = i
            break
    
    if json_start == -1:
        logger.debug("JSON解析: 未找到 JSON 起始字符 [ 或 {")
        # 尝试直接解析整个文本
        try:
            logger.debug("JSON解析: 尝试直接解析")
            return json.loads(text_str, strict=False)
        except json.JSONDecodeError as e:
            preview = original_str[:200] + "..." if len(original_str) > 200 else original_str
            logger.warning(f"JSON解析失败: 未找到JSON边界, 错误: {e}, 前200字符: {preview}")
            raise JSONParseError(f"JSON解析失败: 未找到有效的JSON数据") from e
    
    logger.debug(f"JSON解析: 在位置 {json_start} 找到 JSON 起始")
    
    # 提取从起始位置到末尾的文本
    candidate = text_str[json_start:]
    logger.debug(f"JSON解析: 候选JSON长度 {len(candidate)}")
    
    # 尝试边界检测
    bounded_json = _find_json_boundary(candidate)
    
    if bounded_json:
        logger.debug(f"JSON解析: 边界检测成功，提取长度 {len(bounded_json)}")
        try:
            return json.loads(bounded_json, strict=False)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析: 边界检测后解析失败: {e}")
    else:
        logger.debug("JSON解析: 边界检测失败，尝试直接解析")
        bounded_json = candidate
    
    # 尝试修复常见问题
    for attempt, fix_name in enumerate(["原始", "修复单引号", "修复尾部逗号", "修复转义"]):
        try_json = bounded_json
        if attempt == 1:
            try_json = try_json.replace("'", '"')
        elif attempt == 2:
            try_json = re.sub(r",\s*([}\]])", r"\1", bounded_json)
        elif attempt == 3:
            try_json = bounded_json.replace("'", '"')
            try_json = re.sub(r",\s*([}\]])", r"\1", try_json)
        
        try:
            result = json.loads(try_json, strict=False)
            logger.debug(f"JSON解析: {fix_name} 成功")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析: {fix_name} 失败: {e}")
    
    # 如果所有方法都失败，记录更详细的信息
    preview = original_str[:200] + "..." if len(original_str) > 200 else original_str
    logger.warning(f"JSON解析失败: 所有尝试均失败, 前200字符: {preview}")
    logger.debug(f"JSON解析失败: 完整内容长度 {len(original_str)}")
    raise JSONParseError(f"JSON解析失败: 无法解析响应内容")


def parse_markdown_table(text: str) -> List[Dict[str, Any]]:
    """
    将 Markdown 表格解析为 JSON 数组
    
    Args:
        text: Markdown 格式的表格文本
        
    Returns:
        JSON 数组，每个元素是一个用例对象
    """
    if not text or not isinstance(text, str):
        return []
    
    lines = text.strip().split("\n")
    lines = [line.strip() for line in lines if line.strip()]
    
    if len(lines) < 2:
        return []
    
    header_line_idx = -1
    separator_line_idx = -1
    
    for i, line in enumerate(lines):
        if line.startswith("|") and "---" in line:
            separator_line_idx = i
            if header_line_idx >= 0:
                break
        elif line.startswith("|") and header_line_idx < 0:
            header_line_idx = i
    
    if header_line_idx < 0 or separator_line_idx < 0:
        return []
    
    header_line = lines[header_line_idx]
    headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
    
    result = []
    for i in range(separator_line_idx + 1, len(lines)):
        line = lines[i]
        if not line.startswith("|"):
            continue
        
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        
        if len(cells) != len(headers):
            continue
        
        row = {}
        for j, header in enumerate(headers):
            cell_value = cells[j].replace("<br>", "\n")
            row[header] = cell_value
        
        result.append(row)
    
    return result


def validate_schema(data: Any, schema: Dict) -> Any:
    """
    校验数据是否符合 schema
    
    Args:
        data: 待校验数据
        schema: JSON Schema
        
    Returns:
        校验后的数据（可能被转换）
        
    Raises:
        SchemaValidationError: 校验失败时抛出
    """
    try:
        validate(instance=data, schema=schema)
        return data
    except ValidationError as e:
        # 尝试修复：如果期望数组但收到单个对象，自动包装为数组
        if "is not of type 'array'" in str(e.message) and isinstance(data, dict):
            logger.info(f"自动将单个对象包装为数组")
            wrapped_data = [data]
            try:
                validate(instance=wrapped_data, schema=schema)
                return wrapped_data
            except ValidationError:
                logger.warning(f"Schema校验失败: {e.message}")
                raise SchemaValidationError(f"Schema校验失败: {e.message}") from e
        
        logger.warning(f"Schema校验失败: {e.message}")
        raise SchemaValidationError(f"Schema校验失败: {e.message}") from e
