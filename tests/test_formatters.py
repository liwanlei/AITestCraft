#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""格式化器模块单元测试"""
import base64
import json
import unittest
from unittest.mock import Mock, patch

from formatters import MarkdownFormatter, XMindFormatter


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


if __name__ == "__main__":
    unittest.main(verbosity=2)