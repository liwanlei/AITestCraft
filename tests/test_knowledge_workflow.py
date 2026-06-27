#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.case_parser import parse_case_tree, CaseParseError
from storage.knowledge_repositories import (
    create_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
    create_knowledge_item,
    get_knowledge_items,
    get_active_items,
    get_changed_items
)
from storage.db import get_db


class TestKnowledgeRepositories(unittest.TestCase):
    """知识库数据访问层测试"""
    
    @classmethod
    def setUpClass(cls):
        """初始化测试数据库"""
        db = get_db()
        # 确保表结构存在
        conn = db._get_conn()
        try:
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_bases (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                markdown_content TEXT,
                modules_json TEXT,
                source_case_ids TEXT,
                item_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
            """)
            c.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id TEXT PRIMARY KEY,
                knowledge_base_id TEXT NOT NULL,
                module TEXT NOT NULL,
                item_type TEXT NOT NULL,
                content TEXT NOT NULL,
                priority TEXT,
                source_case_ids TEXT,
                status TEXT DEFAULT 'active',
                old_content TEXT,
                change_reason TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
            )
            """)
            conn.commit()
        finally:
            db._release_conn(conn)
    
    def setUp(self):
        """每个测试前清理测试数据"""
        db = get_db()
        conn = db._get_conn()
        try:
            conn.execute("DELETE FROM knowledge_items WHERE knowledge_base_id LIKE 'test_%'")
            conn.execute("DELETE FROM knowledge_bases WHERE id LIKE 'test_%'")
            conn.commit()
        finally:
            db._release_conn(conn)
    
    def test_create_and_get_knowledge_base(self):
        """测试创建和查询知识库"""
        kb_id = "test_kb_001"
        task_id = "test_task_001"
        
        create_knowledge_base(
            kb_id=kb_id,
            task_id=task_id,
            title="测试知识库",
            markdown_content="# 测试内容",
            modules_json='["模块1", "模块2"]',
            source_case_ids='["case_001", "case_002"]',
            description="测试描述"
        )
        
        kb = get_knowledge_base(kb_id)
        self.assertEqual(kb["id"], kb_id)
        self.assertEqual(kb["title"], "测试知识库")
        self.assertEqual(json.loads(kb["modules_json"]), ["模块1", "模块2"])
        self.assertEqual(json.loads(kb["source_case_ids"]), ["case_001", "case_002"])
    
    def test_list_knowledge_bases(self):
        """测试查询知识库列表"""
        kb_id_1 = "test_kb_list_001"
        kb_id_2 = "test_kb_list_002"
        
        create_knowledge_base(kb_id_1, "test_task_001", "知识库1")
        create_knowledge_base(kb_id_2, "test_task_002", "知识库2")
        
        bases = list_knowledge_bases()
        test_bases = [b for b in bases if b["id"].startswith("test_kb_list")]
        self.assertEqual(len(test_bases), 2)
    
    def test_create_and_get_knowledge_items(self):
        """测试创建和查询知识点"""
        kb_id = "test_kb_items"
        create_knowledge_base(kb_id, "test_task_items", "知识库")
        
        item_id_1 = "test_item_001"
        item_id_2 = "test_item_002"
        
        create_knowledge_item(
            item_id=item_id_1,
            kb_id=kb_id,
            module="登录模块",
            item_type="功能需求",
            content="支持手机号登录",
            priority="P0",
            source_case_ids='["case_001"]',
            status="active"
        )
        
        create_knowledge_item(
            item_id=item_id_2,
            kb_id=kb_id,
            module="登录模块",
            item_type="功能需求",
            content="支持邮箱登录",
            priority="P1",
            source_case_ids='["case_002"]',
            status="changed",
            old_content="支持邮箱登录（已废弃）",
            change_reason="需求变更"
        )
        
        items = get_knowledge_items(kb_id)
        self.assertEqual(len(items), 2)
        
        active_items = get_active_items(kb_id)
        self.assertEqual(len(active_items), 1)
        self.assertEqual(active_items[0]["id"], item_id_1)
        
        changed_items = get_changed_items(kb_id)
        self.assertEqual(len(changed_items), 1)
        self.assertEqual(changed_items[0]["id"], item_id_2)


class TestCaseParser(unittest.TestCase):
    """树形用例解析器测试"""
    
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
        
        cases = parse_case_tree(raw_data)
        self.assertEqual(len(cases), 1)
        
        case = cases[0]
        self.assertEqual(case["module"], "手机号登录")
        self.assertEqual(case["case_id"], "TC001")
        self.assertEqual(case["priority"], "P0")
        self.assertEqual(case["precondition"], "用户未登录")
        self.assertIn("打开登录页面", case["steps"])
        self.assertIn("输入手机号", case["steps"])
        self.assertEqual(case["assert"], ["登录成功"])
    
    def test_parse_multiple_cases(self):
        """测试解析多个用例"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {
                    "root": {
                        "data": {"text": "用户管理"},
                        "children": [
                            {
                                "data": {
                                    "text": "[P0] TC001: 新建用户",
                                    "created": 1780753285449
                                },
                                "children": [
                                    {
                                        "data": {
                                            "resource": ["前置条件"],
                                            "text": "管理员已登录"
                                        }
                                    },
                                    {
                                        "data": {
                                            "resource": ["执行步骤"],
                                            "text": "1. 进入用户管理页面"
                                        }
                                    },
                                    {
                                        "data": {
                                            "resource": ["预期结果"],
                                            "text": "页面加载成功"
                                        }
                                    }
                                ]
                            },
                            {
                                "data": {
                                    "text": "[P1] TC002: 删除用户",
                                    "created": 1780753285450
                                },
                                "children": [
                                    {
                                        "data": {
                                            "resource": ["前置条件"],
                                            "text": "管理员已登录"
                                        }
                                    },
                                    {
                                        "data": {
                                            "resource": ["执行步骤"],
                                            "text": "1. 选择用户"
                                        }
                                    },
                                    {
                                        "data": {
                                            "resource": ["预期结果"],
                                            "text": "删除成功"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        
        cases = parse_case_tree(raw_data)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["case_id"], "TC001")
        self.assertEqual(cases[1]["case_id"], "TC002")
    
    def test_parse_invalid_code(self):
        """测试解析错误响应"""
        raw_data = {"code": 400, "msg": "参数错误"}
        with self.assertRaises(CaseParseError) as ctx:
            parse_case_tree(raw_data)
        self.assertIn("API 返回错误", str(ctx.exception))
    
    def test_parse_missing_root(self):
        """测试解析缺少 root 节点"""
        raw_data = {
            "code": 200,
            "data": {
                "caseContent": {}
            }
        }
        with self.assertRaises(CaseParseError) as ctx:
            parse_case_tree(raw_data)
        self.assertIn("缺少 root 节点", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
