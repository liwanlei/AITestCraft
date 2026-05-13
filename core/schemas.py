# -*- coding: utf-8 -*-
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
            }
        },
        "additionalProperties": False
    }
}
REVIEW_SCHEMA = {
    "type": "object",
    "required": ["score", "issues", "duplicates", "invalid", "suggestions"],
    "properties": {
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"}
        },
        "duplicates": {
            "type": "array",
            "items": {"type": "string"}
        },
        "invalid": {
            "type": "array",
            "items": {"type": "string"}
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "additionalProperties": False
}
COVERAGE_SCHEMA = {
    "type": "object",
    "required": ["coverage_rate", "missing", "risk_level"],
    "properties": {
        "coverage_rate": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
        },
        "missing": {
            "type": "array",
            "items": {"type": "string"}
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high"]
        }
    },
    "additionalProperties": False
}
GAP_SCHEMA = {
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
            }
        },
        "additionalProperties": False
    }
}
