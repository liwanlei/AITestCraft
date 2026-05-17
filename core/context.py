# -*- coding: utf-8 -*-
import threading
from typing import Any, Dict, Optional


class Context(dict):
    def set(self, key: str, value: Any) -> "Context":
        self[key] = value
        return self


class TokenStats:
    def __init__(self):
        self._nodes: Dict[str, Dict[str, int]] = {}
        self._node_order: list = []
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self._lock = threading.Lock()

    def add(self, node_name: str, usage: Optional[Dict[str, int]] = None) -> None:
        input_tokens = usage.get("input_token_count", 0) if usage else 0
        output_tokens = usage.get("output_token_count", 0) if usage else 0
        total_tokens = (usage.get("total_token_count", input_tokens + output_tokens)
                        if usage else 0)

        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.total_tokens += total_tokens

            if node_name not in self._nodes:
                self._nodes[node_name] = {
                    "input": 0,
                    "output": 0,
                    "total": 0
                }
                self._node_order.append(node_name)

            self._nodes[node_name]["input"] += input_tokens
            self._nodes[node_name]["output"] += output_tokens
            self._nodes[node_name]["total"] += total_tokens

    def ensure_node(self, node_name: str) -> None:
        with self._lock:
            if node_name not in self._nodes:
                self._nodes[node_name] = {
                    "input": 0,
                    "output": 0,
                    "total": 0
                }
                self._node_order.append(node_name)

    def get_node_usage(self, node_name: str) -> Optional[Dict[str, int]]:
        with self._lock:
            return self._nodes.get(node_name)

    @classmethod
    def from_persisted(cls, node_statuses: Dict[str, Dict[str, Any]]) -> "TokenStats":
        """
        从数据库持久化的节点状态恢复 TokenStats
        
        Args:
            node_statuses: get_node_status() 返回的数据
            
        Returns:
            恢复后的 TokenStats 实例
        """
        stats = cls()
        for node_name, info in node_statuses.items():
            token_usage = info.get("token_usage")
            if token_usage:
                stats.add(node_name, {
                    "input_token_count": token_usage.get("input", 0),
                    "output_token_count": token_usage.get("output", 0),
                    "total_token_count": token_usage.get("total", 0)
                })
            else:
                stats.ensure_node(node_name)
        return stats

    def report(self) -> Dict[str, Any]:
        with self._lock:
            nodes_list = []
            for name in self._node_order:
                info = self._nodes[name]
                nodes_list.append({
                    "name": name,
                    "input": info["input"],
                    "output": info["output"],
                    "total": info["total"]
                })
            return {
                "workflow": {
                    "input_tokens": self.input_tokens,
                    "output_tokens": self.output_tokens,
                    "total_tokens": self.total_tokens
                },
                "nodes": nodes_list
            }