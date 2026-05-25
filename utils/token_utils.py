# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional, Tuple


def extract_usage_info(result: Any) -> Optional[Dict]:
    usage = None
    for attr_name in ["usage_details", "usage", "model_usage", "token_usage", "usage_info"]:
        usage = getattr(result, attr_name, None)
        if usage:
            break
    if not usage:
        return None
    if hasattr(usage, '__dict__'):
        return vars(usage)
    elif isinstance(usage, dict):
        return usage
    return {}


def extract_token_counts(usage_info: Optional[Dict]) -> Tuple[int, int]:
    if not usage_info:
        return 0, 0
    input_tokens = usage_info.get("input_token_count", 0) or usage_info.get("prompt_tokens", 0) or usage_info.get("input_tokens", 0)
    output_tokens = usage_info.get("output_token_count", 0) or usage_info.get("completion_tokens", 0) or usage_info.get("output_tokens", 0)
    return input_tokens, output_tokens
