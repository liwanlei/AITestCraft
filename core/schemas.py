# -*- coding: utf-8 -*-
import copy

TESTCASE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "name", "priority", "precondition", "steps", "assert"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "priority": {"enum": ["P0", "P1", "P2"]},
            "precondition": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {"type": "string"}
            },
            "assert": {
                "type": "array",
                "items": {"type": "string"}
            },
            "module": {"type": "string"},
            "coverage": {"type": "string"}
        },
        "additionalProperties": True
    }
}

GAP_SCHEMA = copy.deepcopy(TESTCASE_SCHEMA)
