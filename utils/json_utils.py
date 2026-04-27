import json
import re

from jsonschema import validate, ValidationError

from utils.logger import logger


def safe_loads(text: str):
    if not text:
        logger.info("json loads failed")
        logger.error(text)
        raise ValueError("empty response")
    if isinstance(text, (dict, list)):
        return text

    if not isinstance(text, str):
        logger.info("json loads failed")
        logger.error(text)
        raise TypeError(f"unsupported type: {type(text)}")
    text = text.strip()

    # ✅ 去 markdown 包裹
    text = re.sub(r"^```json|```$", "", text).strip()

    # ✅ 提取第一个 JSON 块
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if match:
        text = match.group(1)

    # ✅ 修复单引号
    text = text.replace("'", '"')

    # ✅ 去尾逗号
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return json.loads(text, strict=False)

def validate_schema(data, schema):
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        logger.warning(f"schema校验失败: {e.message}")
        return False


