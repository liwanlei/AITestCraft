#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""格式化器模块单元测试"""
import base64
import json
import unittest
from unittest.mock import Mock, patch

from formatters import MarkdownFormatter, XMindFormatter, KityMinderFormatter


class TestMarkdownFormatter(unittest.TestCase):
    """Markdown 格式化器测试"""

    def setUp(self):
        self.formatter = MarkdownFormatter()
        self.test_cases = [
            {
                "id": "TC001",
                "name": "正常登录测试",
                "priority": "P0",
                "module": "用户模块",
                "precondition": "用户已注册",
                "steps": ["输入用户名", "输入密码", "点击登录"],
                "assert": ["登录成功", "跳转到首页"],
                "coverage": "功能覆盖"
            },
            {
                "id": "TC002",
                "name": "密码错误登录",
                "priority": "P1",
                "module": "用户模块",
                "precondition": "用户已注册",
                "steps": ["输入用户名", "输入错误密码", "点击登录"],
                "assert": ["提示密码错误"],
                "coverage": "异常覆盖"
            }
        ]
        self.metadata = {
            "title": "测试用例文档",
            "requirement": "用户登录功能需求",
            "generated_at": "2024-01-01",
            "total_count": 2,
            "coverage": 95
        }

    def test_format_basic(self):
        """测试基本格式化功能"""
        result = self.formatter.format(self.test_cases, self.metadata)
        self.assertIsInstance(result, str)
        self.assertIn("# 测试用例文档", result)
        self.assertIn("## 项目概述", result)
        self.assertIn("用户登录功能需求", result)
        self.assertIn("TC001", result)
        self.assertIn("TC002", result)

    def test_format_empty_testcases(self):
        """测试空测试用例列表"""
        result = self.formatter.format([], self.metadata)
        self.assertIsInstance(result, str)
        self.assertIn("总计用例**: 0", result)

    def test_format_without_metadata(self):
        """测试无元数据情况"""
        result = self.formatter.format(self.test_cases, {})
        self.assertIsInstance(result, str)

    def test_group_by_priority(self):
        """测试按优先级分组"""
        result = self.formatter._group_by_priority(self.test_cases)
        self.assertIn("P0", result)
        self.assertIn("P1", result)
        self.assertEqual(len(result["P0"]), 1)
        self.assertEqual(len(result["P1"]), 1)


class TestXMindFormatter(unittest.TestCase):
    """XMind 格式化器测试"""

    def setUp(self):
        self.formatter = XMindFormatter()
        self.test_cases = [
            {
                "id": "TC001",
                "name": "正常登录测试",
                "priority": "P0",
                "module": "用户模块",
                "precondition": "用户已注册",
                "steps": ["输入用户名", "输入密码", "点击登录"],
                "assert": ["登录成功"],
                "coverage": "功能覆盖"
            }
        ]
        self.metadata = {
            "title": "测试用例文档",
            "requirement": "用户登录功能需求",
            "generated_at": "2024-01-01",
            "total_count": 1,
            "coverage": 95
        }

    def test_format_8_basic(self):
        """测试 XMind 8 格式生成"""
        result = self.formatter.format_8(self.test_cases, self.metadata)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_format_2023_basic(self):
        """测试 XMind 2023 格式生成"""
        result = self.formatter.format_2023(self.test_cases, self.metadata)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_encode_base64(self):
        """测试 Base64 编码功能"""
        test_bytes = b"test data"
        encoded = self.formatter.encode_base64(test_bytes)
        self.assertIsInstance(encoded, str)
        decoded = base64.b64decode(encoded)
        self.assertEqual(decoded, test_bytes)

    def test_format_empty_testcases(self):
        """测试空测试用例"""
        result = self.formatter.format_8([], self.metadata)
        self.assertIsInstance(result, bytes)


class TestKityMinderFormatter(unittest.TestCase):
    """KityMinder（百度脑图）格式化器测试"""

    def setUp(self):
        self.formatter = KityMinderFormatter()
        self.test_cases = [
            {
                "id": "TC001",
                "name": "正常登录测试",
                "priority": "P0",
                "module": "用户模块",
                "precondition": "用户已注册",
                "steps": ["输入用户名", "输入密码", "点击登录"],
                "assert": ["登录成功", "跳转到首页"],
            },
            {
                "id": "TC002",
                "name": "密码错误登录",
                "priority": "P1",
                "module": "用户模块",
                "precondition": "用户已注册",
                "steps": ["输入用户名", "输入错误密码", "点击登录"],
                "assert": ["提示密码错误"],
            },
            {
                "id": "TC003",
                "name": "商品列表加载",
                "priority": "P0",
                "module": "商品模块",
                "precondition": "用户已登录",
                "steps": ["进入商品列表", "等待加载"],
                "assert": ["显示商品列表"],
            },
        ]
        self.metadata = {
            "title": "测试用例文档",
            "requirement": "用户登录功能需求",
            "generated_at": "2024-01-01",
            "total_count": 3,
            "coverage": 95
        }

    def test_format_basic(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        self.assertIsInstance(result, dict)
        self.assertIn("root", result)
        self.assertIn("template", result)
        self.assertIn("theme", result)
        self.assertEqual(result["template"], "default")
        self.assertEqual(result["theme"], "fresh-blue")
        self.assertEqual(result["version"], "1.4.43")
        self.assertEqual(result["base"], 10)
        self.assertEqual(result["right"], 1)

    def test_root_node(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        root = result["root"]
        self.assertIn("data", root)
        self.assertIn("children", root)
        self.assertEqual(root["data"]["text"], "用户登录功能需求")

    def test_module_grouping(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        children = result["root"]["children"]
        self.assertEqual(len(children), 2)
        module_texts = [child["data"]["text"] for child in children]
        self.assertIn("用户模块 (2条)", module_texts)
        self.assertIn("商品模块 (1条)", module_texts)

    def test_case_node_structure(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        user_module = result["root"]["children"][0]
        case_node = user_module["children"][0]
        self.assertIn("data", case_node)
        self.assertIn("children", case_node)
        self.assertIn("[P0] TC001: 正常登录测试", case_node["data"]["text"])

    def test_case_detail_nodes(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        user_module = result["root"]["children"][0]
        case_node = user_module["children"][0]
        self.assertEqual(len(case_node["children"]), 1)
        chain_head = case_node["children"][0]
        self.assertEqual(chain_head["data"]["text"], "用户已注册")
        self.assertIn("resource", chain_head["data"])
        self.assertEqual(chain_head["data"]["resource"], ["前置条件"])

    def test_chain_structure(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        user_module = result["root"]["children"][0]
        case_node = user_module["children"][0]

        precondition = case_node["children"][0]
        self.assertEqual(precondition["data"]["text"], "用户已注册")
        self.assertEqual(precondition["data"]["resource"], ["前置条件"])

        step1 = precondition["children"][0]
        self.assertEqual(step1["data"]["text"], "1. 输入用户名")
        self.assertEqual(step1["data"]["resource"], ["执行步骤"])

        step2 = step1["children"][0]
        self.assertEqual(step2["data"]["text"], "2. 输入密码")

        step3 = step2["children"][0]
        self.assertEqual(step3["data"]["text"], "3. 点击登录")

    def test_asserts_on_last_step(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        user_module = result["root"]["children"][0]
        case_node = user_module["children"][0]

        step3 = case_node["children"][0]["children"][0]["children"][0]["children"][0]
        self.assertEqual(step3["data"]["text"], "3. 点击登录")

        assert_nodes = step3["children"]
        self.assertEqual(len(assert_nodes), 2)
        self.assertEqual(assert_nodes[0]["data"]["text"], "1. 登录成功")
        self.assertEqual(assert_nodes[0]["data"]["resource"], ["预期结果"])
        self.assertEqual(assert_nodes[1]["data"]["text"], "2. 跳转到首页")

    def test_format_string(self):
        result_str = self.formatter.format_string(self.test_cases, self.metadata)
        self.assertIsInstance(result_str, str)
        parsed = json.loads(result_str)
        self.assertIn("root", parsed)

    def test_format_empty(self):
        result = self.formatter.format([], self.metadata)
        self.assertIsInstance(result, dict)
        self.assertIn("root", result)
        self.assertEqual(len(result["root"]["children"]), 0)

    def test_format_single_module_no_grouping(self):
        single_module_cases = self.test_cases[:2]
        result = self.formatter.format(single_module_cases, self.metadata)
        self.assertEqual(len(result["root"]["children"]), 2)
        self.assertIn("TC001", result["root"]["children"][0]["data"]["text"])

    def test_asserts_on_last_node_when_no_steps(self):
        cases = [{
            "id": "TC001",
            "name": "无步骤用例",
            "module": "模块A",
            "precondition": "用户已登录",
            "steps": [],
            "assert": ["断言A", "断言B"],
        }]
        result = self.formatter.format(cases, self.metadata)
        case_node = result["root"]["children"][0]
        precondition_node = case_node["children"][0]
        self.assertEqual(precondition_node["data"]["text"], "用户已登录")
        self.assertEqual(precondition_node["data"]["resource"], ["前置条件"])
        self.assertEqual(len(precondition_node["children"]), 2)
        self.assertEqual(precondition_node["children"][0]["data"]["text"], "1. 断言A")
        self.assertEqual(precondition_node["children"][1]["data"]["text"], "2. 断言B")

    def test_only_asserts(self):
        cases = [{
            "id": "TC001",
            "name": "仅有断言",
            "module": "模块A",
            "precondition": "",
            "steps": [],
            "assert": ["断言A", "断言B"],
        }]
        result = self.formatter.format(cases, self.metadata)
        case_node = result["root"]["children"][0]
        self.assertEqual(len(case_node["children"]), 2)
        self.assertEqual(case_node["children"][0]["data"]["text"], "1. 断言A")
        self.assertEqual(case_node["children"][1]["data"]["text"], "2. 断言B")

    def test_every_node_has_valid_id(self):
        result = self.formatter.format(self.test_cases, self.metadata)

        def check_ids(node):
            self.assertIn("id", node["data"])
            self.assertEqual(len(node["data"]["id"]), 12)
            self.assertIn("created", node["data"])
            self.assertIsInstance(node["data"]["created"], int)
            for child in node.get("children", []):
                check_ids(child)

        check_ids(result["root"])

    def test_no_priority_case(self):
        cases = [{
            "id": "TC001",
            "name": "无优先级用例",
            "module": "模块A",
            "precondition": "",
            "steps": [],
            "assert": [],
        }]
        result = self.formatter.format(cases, self.metadata)
        case_text = result["root"]["children"][0]["data"]["text"]
        self.assertEqual(case_text, "TC001: 无优先级用例")

    def test_empty_metadata(self):
        result = self.formatter.format(self.test_cases, {})
        self.assertEqual(result["root"]["data"]["text"], "测试用例")

    def test_resource_field_on_detail_nodes(self):
        result = self.formatter.format(self.test_cases, self.metadata)
        user_module = result["root"]["children"][0]
        case_node = user_module["children"][0]

        precondition = case_node["children"][0]
        self.assertEqual(precondition["data"]["resource"], ["前置条件"])

        step1 = precondition["children"][0]
        self.assertEqual(step1["data"]["resource"], ["执行步骤"])

        step3 = case_node["children"][0]["children"][0]["children"][0]["children"][0]
        for assert_node in step3["children"]:
            self.assertEqual(assert_node["data"]["resource"], ["预期结果"])


if __name__ == "__main__":
    unittest.main(verbosity=2)