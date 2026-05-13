# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional


class Context(dict):
    def set(self, key: str, value: Any) -> "Context":
        self[key] = value
        return self


class TokenStats:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, int]] = {}
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0

    def add(self, node_name: str, usage: Optional[Dict[str, int]] = None) -> None:
        if not usage:
            return

        input_tokens = usage.get("input_token_count", 0)
        output_tokens = usage.get("output_token_count", 0)
        total_tokens = usage.get("total_token_count", input_tokens + output_tokens)

        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens

        if node_name not in self.nodes:
            self.nodes[node_name] = {
                "input": 0,
                "output": 0,
                "total": 0
            }

        self.nodes[node_name]["input"] += input_tokens
        self.nodes[node_name]["output"] += output_tokens
        self.nodes[node_name]["total"] += total_tokens

    def report(self) -> Dict[str, Any]:
        return {
            "workflow": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens
            },
            "nodes": self.nodes
        }