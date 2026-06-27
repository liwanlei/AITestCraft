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


def _repair_truncated_json(text: str) -> Any:
    """
    尝试修复被截断的 JSON（LLM 输出超 max_tokens 时常见）
    
    策略：
    1. 对于 JSON 数组：逐个提取完整的对象，丢弃最后一个不完整的对象
    2. 补全缺失的闭合括号
    
    Args:
        text: 可能被截断的 JSON 文本
        
    Returns:
        解析后的 Python 对象，如果无法修复则返回 None
    """
    if not text or not text.strip():
        return None
    
    text = text.strip()
    
    # 策略1：对于 JSON 数组，逐个提取完整对象
    if text.startswith('['):
        items = []
        # 找到所有完整的 {...} 对象
        depth = 0
        obj_start = None
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
            
            if char == '{':
                if depth == 0:
                    obj_start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and obj_start is not None:
                    obj_str = text[obj_start:i+1]
                    try:
                        obj = json.loads(obj_str, strict=False)
                        items.append(obj)
                    except json.JSONDecodeError:
                        # 单个对象解析失败，跳过
                        pass
                    obj_start = None
        
        if items:
            logger.debug(f"截断修复: 从数组中提取了 {len(items)} 个完整对象")
            return items
    
    # 策略2：补全缺失的闭合括号
    open_brackets = []
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
        
        if char in ('{', '['):
            open_brackets.append(char)
        elif char == '}' and open_brackets and open_brackets[-1] == '{':
            open_brackets.pop()
        elif char == ']' and open_brackets and open_brackets[-1] == '[':
            open_brackets.pop()
    
    # 如果有未闭合的字符串，先关闭字符串
    if in_string:
        text += '"'
    
    # 移除末尾可能的不完整内容（如逗号后没有后续元素）
    text = re.sub(r',\s*$', '', text)
    
    # 补全闭合括号
    close_map = {'{': '}', '[': ']'}
    for bracket in reversed(open_brackets):
        text += close_map[bracket]
    
    try:
        result = json.loads(text, strict=False)
        logger.debug(f"截断修复: 补全括号后解析成功")
        return result
    except json.JSONDecodeError:
        return None


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

    # 优先尝试直接解析（最常见情况：LLM 返回了有效 JSON）
    try:
        return json.loads(text_str, strict=False)
    except (json.JSONDecodeError, ValueError):
        pass

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
        skip_original = True
    else:
        logger.debug("JSON解析: 边界检测失败，尝试直接解析")
        bounded_json = candidate
        skip_original = False
    
    for attempt, fix_name in enumerate(["原始", "修复单引号", "修复尾部逗号", "修复转义"]):
        if attempt == 0 and skip_original:
            continue
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
    
    # 尝试修复截断的 JSON（LLM 输出超 max_tokens 导致 JSON 不完整）
    try:
        repaired = _repair_truncated_json(bounded_json)
        if repaired is not None:
            logger.info(f"JSON解析: 截断修复成功，提取 {len(repaired)} 条数据")
            return repaired
    except Exception as e:
        logger.debug(f"JSON解析: 截断修复失败: {e}")
    
    # 如果所有方法都失败，记录更详细的信息
    preview = original_str[:200] + "..." if len(original_str) > 200 else original_str
    logger.warning(f"JSON解析失败: 所有尝试均失败, 前200字符: {preview}")
    logger.debug(f"JSON解析失败: 完整内容长度 {len(original_str)}")
    raise JSONParseError(f"JSON解析失败: 无法解析响应内容")


def parse_markdown_table(text: str) -> List[Dict[str, Any]]:
    """
    将 Markdown 表格解析为 JSON 数组，支持多模块表格（### 标题分隔）
    
    Args:
        text: Markdown 格式的表格文本
        
    Returns:
        JSON 数组，每个元素是一个用例对象，包含 module 字段
    """
    if not text or not isinstance(text, str):
        return []
    
    sections = re.split(r'\n(?=###\s)', text.strip())
    
    all_results = []
    current_module = ""
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
        
        module_match = re.match(r'^###\s+(.+?)(?:\s*[（(].+[）)])?\s*$', section, re.MULTILINE)
        if module_match:
            current_module = module_match.group(1).strip()
        
        lines = section.strip().split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        
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
            continue
        
        header_line = lines[header_line_idx]
        headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
        
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
            
            if current_module and "模块" not in row:
                row["module"] = current_module
            elif current_module and "模块" in row and not row["模块"]:
                row["模块"] = current_module
            
            all_results.append(row)
    
    return all_results


def parse_structured_markdown(text: str) -> List[Dict[str, Any]]:
    """
    将结构化 Markdown（标题+列表格式）解析为 JSON 数组
    
    支持格式：
    - ### 模块名
    - - **字段**：值
    - 或 ### TC001 格式的用例标题
    
    Returns:
        JSON 数组
    """
    if not text or not isinstance(text, str):
        return []
    
    # 去除代码块标记
    text = re.sub(r"^```(?:markdown)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    
    results = []
    current_item = {}
    current_module = ""
    
    # 按标题分割
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 一级标题 - 整体描述，跳过
        if line.startswith("# ") and not line.startswith("## "):
            continue
        
        # 二级标题 - 可能是用例标题或模块标题
        h2_match = re.match(r'^##\s+(.+)$', line)
        if h2_match:
            # 保存前一个 item
            if current_item and current_item.get("content"):
                if current_module and "module" not in current_item:
                    current_item["module"] = current_module
                results.append(current_item)
                current_item = {}
            
            title = h2_match.group(1).strip()
            # 判断是否是模块标题（如 "登录模块"）还是用例标题
            if "模块" in title or "Module" in title.lower():
                current_module = title.replace("模块", "").strip()
            else:
                # 用例标题，提取模块和内容
                current_item["content"] = title
            continue
        
        # 三级标题 - 用例标题
        h3_match = re.match(r'^###\s+(.+)$', line)
        if h3_match:
            if current_item and current_item.get("content"):
                if current_module and "module" not in current_item:
                    current_item["module"] = current_module
                results.append(current_item)
                current_item = {}
            current_item["content"] = h3_match.group(1).strip()
            continue
        
        # 列表项 - 字段解析
        bullet_match = re.match(r'^[-*]\s+\*\*(.+?)\*\*[：:]\s*(.+)$', line)
        if bullet_match:
            key = bullet_match.group(1).strip()
            value = bullet_match.group(2).strip()
            
            # 字段名映射
            key_map = {
                "模块": "module",
                "优先级": "priority",
                "用例名称": "content",
                "名称": "content",
                "测试点": "content",
                "类型": "item_type",
                "状态": "status",
                "来源用例": "source_case_ids",
                "来源": "source_case_ids",
                "描述": "content",
                "验证点": "content",
                "关键验证": "content",
                "前置条件": "precondition",
                "步骤": "steps",
                "预期结果": "expected",
                "变更原因": "change_reason",
                "旧内容": "old_content",
            }
            
            mapped_key = key_map.get(key, key)
            
            # 特殊处理 source_case_ids
            if mapped_key == "source_case_ids":
                ids = re.findall(r'TC\d+', value)
                if not ids:
                    ids = [v.strip() for v in value.split(",")]
                current_item[mapped_key] = ids
            elif mapped_key == "module":
                current_module = value
                current_item[mapped_key] = value
            elif mapped_key in ("content",) and current_item.get("content"):
                # content 已有值，追加
                current_item[mapped_key] = current_item[mapped_key] + " - " + value
            else:
                current_item[mapped_key] = value
            continue
        
        # 普通列表项（无加粗字段名）
        plain_bullet = re.match(r'^[-*]\s+(.+)$', line)
        if plain_bullet:
            value = plain_bullet.group(1).strip()
            if current_item.get("content"):
                current_item["content"] = current_item["content"] + "；" + value
            else:
                current_item["content"] = value
            continue
    
    # 保存最后一个 item
    if current_item and current_item.get("content"):
        if current_module and "module" not in current_item:
            current_item["module"] = current_module
        results.append(current_item)
    
    return results


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
