#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.case_parser import parse_case_tree, CaseParseError


class TestParseCaseTree(unittest.TestCase):

    def test_parse_single_case_success(self):
        """测试正常解析单个用例"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {
                    "root": {
                        "data": {"text": "手机号登录"},
                        "children": [
                            {
                                "data": {
                                    "text": "[P0] TC001: 验证码登录-登录成功",
                                    "created": 1780753285449
                                },
                                "children": [
                                    {
                                        "data": {
                                            "resource": ["前置条件"],
                                            "text": "用户未登录"
                                        }
                                    },
                                    {
                                        "data": {
                                            "resource": ["执行步骤"],
                                            "text": "1. 打开登录页面"
                                        },
                                        "children": [
                                            {
                                                "data": {
                                                    "resource": ["执行步骤"],
                                                    "text": "2. 输入手机号"
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        "data": {
                                            "resource": ["预期结果"],
                                            "text": "登录成功"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        result = parse_case_tree(raw_data)
        self.assertEqual(len(result), 1)
        case = result[0]
        self.assertEqual(case["case_id"], "TC001")
        self.assertEqual(case["module"], "手机号登录")
        self.assertEqual(case["priority"], "P0")
        self.assertEqual(case["name"], "验证码登录-登录成功")
        self.assertEqual(case["precondition"], "用户未登录")
        self.assertEqual(case["steps"], ["打开登录页面", "输入手机号"])
        self.assertEqual(case["assert"], ["登录成功"])

    def test_parse_case_without_resource(self):
        """测试无 resource 字段的节点被忽略"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {
                    "root": {
                        "data": {"text": "登录模块"},
                        "children": [
                            {
                                "data": {"text": "[P1] TC002: 测试用例"},
                                "children": [
                                    {"data": {"text": "无类型节点"}}
                                ]
                            }
                        ]
                    }
                }
            }
        }
        result = parse_case_tree(raw_data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["steps"], [])
        self.assertEqual(result[0]["assert"], [])

    def test_parse_invalid_format_raises_error(self):
        """测试无效格式抛出异常"""
        raw_data = {"code": 500, "msg": "服务异常"}
        with self.assertRaises(CaseParseError):
            parse_case_tree(raw_data)

    def test_parse_empty_children(self):
        """测试空 children 的情况"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {
                    "root": {
                        "data": {"text": "模块"},
                        "children": []
                    }
                }
            }
        }
        result = parse_case_tree(raw_data)
        self.assertEqual(result, [])

    def test_parse_chained_steps(self):
        """测试链式步骤嵌套"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {
                    "root": {
                        "data": {"text": "登录模块"},
                        "children": [
                            {
                                "data": {"text": "[P0] TC003: 完整登录流程"},
                                "children": [
                                    {
                                        "data": {
                                            "resource": ["执行步骤"],
                                            "text": "1. 打开登录页面"
                                        },
                                        "children": [
                                            {
                                                "data": {
                                                    "resource": ["执行步骤"],
                                                    "text": "2. 输入手机号13800000001"
                                                },
                                                "children": [
                                                    {
                                                        "data": {
                                                            "resource": ["执行步骤"],
                                                            "text": "3. 点击获取验证码"
                                                        },
                                                        "children": [
                                                            {
                                                                "data": {
                                                                    "resource": ["执行步骤"],
                                                                    "text": "4. 输入验证码123456"
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "data": {
                                            "resource": ["预期结果"],
                                            "text": "登录成功，跳转首页"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        result = parse_case_tree(raw_data)
        self.assertEqual(len(result), 1)
        case = result[0]
        self.assertEqual(len(case["steps"]), 4)
        self.assertEqual(case["steps"][0], "打开登录页面")
        self.assertEqual(case["steps"][3], "输入验证码123456")


if __name__ == "__main__":
    unittest.main(verbosity=2)
