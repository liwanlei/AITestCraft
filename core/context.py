# =========================
# 1. Context（全局状态）
# =========================
class Context(dict):
    def set(self, key, value):
        self[key] = value
        return self

    def getv(self, key, default=None):
        return self.get(key, default)


class TokenStats:

    def __init__(self):
        self.nodes = {}
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def add(self, node_name, usage):

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

    def report(self):
        return {
            "workflow": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens
            },
            "nodes": self.nodes
        }

