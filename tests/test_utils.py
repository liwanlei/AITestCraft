#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具模块单元测试"""
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

from utils.exceptions import TaskNotFoundError, DatabaseError, JSONParseError
from utils.logger import logger


class TestJsonUtils(unittest.TestCase):
    """JSON 工具函数测试"""

    def test_json_dumps_basic(self):
        """测试 JSON 序列化"""
        data = {"key": "value", "number": 123}
        result = json.dumps(data)
        self.assertIsInstance(result, str)
        self.assertIn('"key": "value"', result)

    def test_json_loads_basic(self):
        """测试 JSON 反序列化"""
        json_str = '{"key": "value", "number": 123}'
        result = json.loads(json_str)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["number"], 123)

    def test_json_loads_invalid(self):
        """测试无效 JSON"""
        try:
            json.loads("invalid json")
            self.fail("应该抛出异常")
        except json.JSONDecodeError:
            pass

    def test_json_dumps_with_special_chars(self):
        """测试特殊字符序列化"""
        data = {"content": 'test "quotes" and \n newlines'}
        result = json.dumps(data)
        loaded = json.loads(result)
        self.assertEqual(loaded["content"], data["content"])


class TestExceptions(unittest.TestCase):
    """异常类测试"""

    def test_task_not_found_error(self):
        """测试任务未找到异常"""
        try:
            raise TaskNotFoundError("任务不存在")
        except TaskNotFoundError as e:
            self.assertEqual(str(e), "任务不存在")

    def test_database_error(self):
        """测试数据库异常"""
        try:
            raise DatabaseError("数据库错误")
        except DatabaseError as e:
            self.assertEqual(str(e), "数据库错误")

    def test_json_parse_error(self):
        """测试 JSON 解析异常"""
        try:
            raise JSONParseError("JSON 解析失败")
        except JSONParseError as e:
            self.assertEqual(str(e), "JSON 解析失败")


class TestLogger(unittest.TestCase):
    """日志工具测试"""

    def test_logger_exists(self):
        """测试日志器存在"""
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "AITestCraft")

    def test_logger_methods(self):
        """测试日志方法调用"""
        # 这些方法应该正常执行不抛异常
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")


if __name__ == "__main__":
    unittest.main(verbosity=2)