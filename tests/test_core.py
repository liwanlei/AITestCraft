#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

from core.context import Context, TokenStats
from core.workflow_builders import _to_text, _gap_condition, WORKFLOW_NODE_ORDER


class TestContext(unittest.TestCase):

    def test_init_empty(self):
        ctx = Context()
        self.assertEqual(len(ctx), 0)

    def test_init_with_data(self):
        ctx = Context({"a": 1, "b": 2})
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx["a"], 1)

    def test_set_and_get(self):
        ctx = Context()
        result = ctx.set("key", "value")
        self.assertIs(result, ctx)
        self.assertEqual(ctx.get("key"), "value")

    def test_get_with_default(self):
        ctx = Context()
        self.assertIsNone(ctx.get("missing"))
        self.assertEqual(ctx.get("missing", "default"), "default")

    def test_setitem_getitem(self):
        ctx = Context()
        ctx["key"] = "value"
        self.assertEqual(ctx["key"], "value")

    def test_contains(self):
        ctx = Context({"exists": 1})
        self.assertIn("exists", ctx)
        self.assertNotIn("missing", ctx)

    def test_delitem(self):
        ctx = Context({"key": "value"})
        del ctx["key"]
        self.assertNotIn("key", ctx)

    def test_iter(self):
        ctx = Context({"a": 1, "b": 2})
        keys = list(ctx)
        self.assertCountEqual(keys, ["a", "b"])

    def test_len(self):
        ctx = Context({"a": 1, "b": 2, "c": 3})
        self.assertEqual(len(ctx), 3)

    def test_repr(self):
        ctx = Context({"a": 1})
        self.assertIn("Context", repr(ctx))

    def test_dict_unmodified(self):
        ctx = Context({"test": "original"})
        self.assertEqual(ctx["test"], "original")
        ctx["test"] = "modified"
        self.assertEqual(ctx["test"], "modified")

    def test_nested_set_get(self):
        ctx = Context()
        ctx.set("nested", {"inner": "value"})
        self.assertEqual(ctx["nested"]["inner"], "value")


class TestTokenStats(unittest.TestCase):

    def test_add_single(self):
        stats = TokenStats()
        stats.add("node1", {"input_token_count": 100, "output_token_count": 50})
        self.assertEqual(stats.input_tokens, 100)
        self.assertEqual(stats.output_tokens, 50)
        self.assertEqual(stats.total_tokens, 150)

    def test_add_uses_total_from_dict(self):
        stats = TokenStats()
        stats.add("node1", {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 200
        })
        self.assertEqual(stats.total_tokens, 200)

    def test_add_multiple_nodes(self):
        stats = TokenStats()
        stats.add("node1", {"input_token_count": 10, "output_token_count": 5})
        stats.add("node2", {"input_token_count": 20, "output_token_count": 10})
        self.assertEqual(stats.input_tokens, 30)
        self.assertEqual(stats.output_tokens, 15)

    def test_add_none_usage(self):
        stats = TokenStats()
        stats.add("node1", None)
        self.assertEqual(stats.input_tokens, 0)

    def test_ensure_node(self):
        stats = TokenStats()
        stats.ensure_node("node1")
        usage = stats.get_node_usage("node1")
        self.assertEqual(usage, {"input": 0, "output": 0, "total": 0})

    def test_get_node_usage_missing(self):
        stats = TokenStats()
        self.assertIsNone(stats.get_node_usage("nonexistent"))

    def test_from_persisted(self):
        node_statuses = {
            "node1": {
                "token_usage": {"input": 100, "output": 50, "total": 150}
            },
            "node2": {
                "token_usage": {"input": 30, "output": 20, "total": 50}
            }
        }
        stats = TokenStats.from_persisted(node_statuses)
        self.assertEqual(stats.input_tokens, 130)
        self.assertEqual(stats.total_tokens, 200)

    def test_from_persisted_without_token_usage(self):
        node_statuses = {
            "node1": {"status": "completed"}
        }
        stats = TokenStats.from_persisted(node_statuses)
        usage = stats.get_node_usage("node1")
        self.assertEqual(usage, {"input": 0, "output": 0, "total": 0})

    def test_report(self):
        stats = TokenStats()
        stats.add("node1", {"input_token_count": 10, "output_token_count": 5})
        report = stats.report()
        self.assertEqual(report["workflow"]["input_tokens"], 10)
        self.assertEqual(len(report["nodes"]), 1)
        self.assertEqual(report["nodes"][0]["name"], "node1")

    def test_report_order_preserved(self):
        stats = TokenStats()
        stats.ensure_node("c")
        stats.ensure_node("a")
        stats.ensure_node("b")
        report = stats.report()
        self.assertEqual(report["nodes"][0]["name"], "c")
        self.assertEqual(report["nodes"][1]["name"], "a")
        self.assertEqual(report["nodes"][2]["name"], "b")

    def test_thread_safety(self):
        import threading
        stats = TokenStats()
        def add_tokens():
            for _ in range(100):
                stats.add("node1", {"input_token_count": 1, "output_token_count": 1})
        threads = [threading.Thread(target=add_tokens) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(stats.input_tokens, 1000)
        self.assertEqual(stats.output_tokens, 1000)


class TestToText(unittest.TestCase):

    def test_string_value(self):
        self.assertEqual(_to_text("hello"), "hello")

    def test_none_value_with_default(self):
        self.assertEqual(_to_text(None, "DEFAULT"), "DEFAULT")

    def test_none_value_no_default(self):
        self.assertEqual(_to_text(None), "")

    def test_dict_value(self):
        result = _to_text({"key": "value"})
        parsed = json.loads(result)
        self.assertEqual(parsed["key"], "value")

    def test_list_value(self):
        result = _to_text([1, 2, 3])
        parsed = json.loads(result)
        self.assertEqual(parsed, [1, 2, 3])

    def test_unserializable_value(self):
        import threading
        result = _to_text(threading.Lock())
        self.assertEqual(result, "")


class TestWorkflowNodeOrder(unittest.TestCase):

    def test_order_contains_all_nodes(self):
        expected_nodes = {"requirement", "testpoint", "aggregator", "testcase", "review", "coverage", "gap"}
        self.assertEqual(set(WORKFLOW_NODE_ORDER), expected_nodes)

    def test_requirement_is_first(self):
        self.assertEqual(WORKFLOW_NODE_ORDER[0], "requirement")

    def test_gap_is_last(self):
        self.assertEqual(WORKFLOW_NODE_ORDER[-1], "gap")


class TestGapCondition(unittest.TestCase):

    def test_high_risk_triggers(self):
        ctx = Context({"review": "", "coverage": "风险等级: high"})
        self.assertTrue(_gap_condition(ctx))

    def test_medium_risk_triggers(self):
        ctx = Context({"review": "", "coverage": "风险等级: medium"})
        self.assertTrue(_gap_condition(ctx))

    def test_low_risk_no_triggers(self):
        ctx = Context({"review": "", "coverage": "风险等级: low"})
        self.assertFalse(_gap_condition(ctx))

    def test_has_issues_triggers(self):
        ctx = Context({
            "review": "问题列表\n- 问题1\n- 问题2",
            "coverage": ""
        })
        self.assertTrue(_gap_condition(ctx))

    def test_has_missing_triggers(self):
        ctx = Context({
            "review": "",
            "coverage": "未覆盖场景\n- 场景1\n- 场景2"
        })
        self.assertTrue(_gap_condition(ctx))

    def test_non_string_values(self):
        ctx = Context()
        ctx["review"] = ["not a string"]
        ctx["coverage"] = 123
        self.assertFalse(_gap_condition(ctx))


if __name__ == "__main__":
    unittest.main()