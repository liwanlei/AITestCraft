# -*- coding: utf-8 -*-
"""Utility functions and classes"""


def __getattr__(name):
    if name == "logger":
        from .logger import logger
        return logger
    if name == "safe_loads":
        from .json_utils import safe_loads
        return safe_loads
    if name == "validate_schema":
        from .json_utils import validate_schema
        return validate_schema
    raise AttributeError(f"module 'utils' has no attribute {name!r}")
