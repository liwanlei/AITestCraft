#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

from core.context import Context, TokenStats
from core.node import Node, NodeConfig
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


class TestNodeConfig(unittest.TestCase):
    """NodeConfig + Node 集成测试"""

    def test_node_created_with_config(self):
        """Node 可通过 NodeConfig 创建"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")

        config = NodeConfig("test-node", mock_agent, mock_input_fn, "output_key")
        node = Node(config)

        self.assertEqual(node.name, "test-node")
        self.assertIs(node.agent, mock_agent)
        self.assertIs(node.input_fn, mock_input_fn)
        self.assertEqual(node.output_key, "output_key")
        self.assertEqual(node.output_format, "json")

    def test_node_config_defaults(self):
        """NodeConfig 的默认值"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")

        config = NodeConfig("test-node", mock_agent, mock_input_fn, "output_key")
        self.assertIsNone(config.schema)
        self.assertIsNone(config.condition)
        self.assertIsNone(config.model_settings)
        self.assertEqual(config.output_format, "json")

    def test_node_config_custom_values(self):
        """NodeConfig 自定义值"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")
        mock_schema = {"type": "object"}
        mock_condition = Mock(return_value=True)

        config = NodeConfig(
            name="test-node",
            agent=mock_agent,
            input_fn=mock_input_fn,
            output_key="output_key",
            schema=mock_schema,
            condition=mock_condition,
            model_settings={"temperature": 0.7},
            output_format="md"
        )
        self.assertIs(config.schema, mock_schema)
        self.assertIs(config.condition, mock_condition)
        self.assertEqual(config.model_settings, {"temperature": 0.7})
        self.assertEqual(config.output_format, "md")

    def test_node_config_output_format_mixed(self):
        """output_format 支持 mixed 格式"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")
        config = NodeConfig("test", mock_agent, mock_input_fn, "output", output_format="mixed")
        node = Node(config)
        self.assertEqual(node.output_format, "mixed")

    def test_node_config_schema_propagation(self):
        """schema 从 NodeConfig 传递到 Node"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")
        schema = {"type": "array", "items": {"type": "string"}}
        config = NodeConfig("test", mock_agent, mock_input_fn, "output", schema=schema)
        node = Node(config)
        self.assertIs(node.schema, schema)

    def test_node_config_condition_propagation(self):
        """condition 从 NodeConfig 传递到 Node"""
        mock_agent = Mock()
        mock_input_fn = Mock(return_value="input")
        condition = Mock(return_value=True)
        config = NodeConfig("test", mock_agent, mock_input_fn, "output", condition=condition)
        node = Node(config)
        self.assertIs(node.condition, condition)

    def test_node_multiple_nodes_unique_instances(self):
        """多个 Node 应互不干扰"""
        mock_agent = Mock()
        input_fn1 = Mock(return_value="input1")
        input_fn2 = Mock(return_value="input2")

        config1 = NodeConfig("node1", mock_agent, input_fn1, "key1")
        config2 = NodeConfig("node2", mock_agent, input_fn2, "key2")

        node1 = Node(config1)
        node2 = Node(config2)

        self.assertEqual(node1.name, "node1")
        self.assertEqual(node2.name, "node2")
        self.assertEqual(node1.output_key, "key1")
        self.assertEqual(node2.output_key, "key2")


if __name__ == "__main__":
    unittest.main()