#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from utils.exceptions import TaskNotFoundError, DatabaseError, JSONParseError, SchemaValidationError
from utils.json_utils import safe_loads, parse_markdown_table, validate_schema
from utils.logger import logger


class TestSafeLoads(unittest.TestCase):

    def test_valid_json_object(self):
        result = safe_loads('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_valid_json_array(self):
        result = safe_loads('[1, 2, 3]')
        self.assertEqual(result, [1, 2, 3])

    def test_json_with_markdown_fence(self):
        result = safe_loads('```json\n{"key": "value"}\n```')
        self.assertEqual(result, {"key": "value"})

    def test_json_with_prefix_text(self):
        result = safe_loads('Here is the JSON: {"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json_raises(self):
        with self.assertRaises(JSONParseError):
            safe_loads("not json at all {{{")

    def test_single_quotes_repair(self):
        result = safe_loads("{'key': 'value'}")
        self.assertEqual(result, {"key": "value"})

    def test_trailing_comma_repair(self):
        result = safe_loads('{"key": "value",}')
        self.assertEqual(result, {"key": "value"})


class TestParseMarkdownTable(unittest.TestCase):

    def test_basic_table(self):
        text = "| 用例名称 | 优先级 |\n| --- | --- |\n| 登录测试 | P0 |"
        result = parse_markdown_table(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["用例名称"], "登录测试")

    def test_empty_input(self):
        result = parse_markdown_table("")
        self.assertEqual(result, [])

    def test_none_input(self):
        result = parse_markdown_table(None)
        self.assertEqual(result, [])

    def test_table_with_module_header(self):
        text = "### 登录模块\n| 用例名称 | 优先级 |\n| --- | --- |\n| 登录测试 | P0 |"
        result = parse_markdown_table(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].get("module", ""), "登录模块")


class TestValidateSchema(unittest.TestCase):

    def test_valid_schema(self):
        data = {"name": "test", "age": 25}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        validate_schema(data, schema)

    def test_invalid_schema_raises(self):
        data = {"name": 123}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
        with self.assertRaises(SchemaValidationError):
            validate_schema(data, schema)


class TestExceptions(unittest.TestCase):

    def test_task_not_found_error(self):
        try:
            raise TaskNotFoundError("任务不存在")
        except TaskNotFoundError as e:
            self.assertEqual(str(e), "任务不存在")

    def test_database_error(self):
        try:
            raise DatabaseError("数据库错误")
        except DatabaseError as e:
            self.assertEqual(str(e), "数据库错误")

    def test_json_parse_error(self):
        try:
            raise JSONParseError("JSON 解析失败")
        except JSONParseError as e:
            self.assertEqual(str(e), "JSON 解析失败")


class TestLogger(unittest.TestCase):

    def test_logger_exists(self):
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "AITestCraft")

    def test_logger_methods(self):
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")


if __name__ == "__main__":
    unittest.main(verbosity=2)
