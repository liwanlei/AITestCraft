#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存储模块单元测试"""
import json
import sqlite3
import unittest
import uuid
from unittest.mock import Mock, patch, MagicMock

from storage.db import get_db, init_db
from storage.repositories import (
    create_task, get_task, update_task,
    insert_log, get_logs, get_connection
)
from storage.knowledge_repositories import (
    create_knowledge_base, get_knowledge_base, find_kb_containing_cases
)
from utils.exceptions import TaskNotFoundError, DatabaseError
from utils.logger import logger


class TestDbConnection(unittest.TestCase):
    """数据库连接测试"""

    def test_get_db_connection(self):
        """测试获取数据库实例"""
        db = get_db()
        from storage.db import Database
        self.assertIsInstance(db, Database)

    def test_init_db(self):
        """测试初始化数据库"""
        init_db()  # 应正常执行，无异常


class TestTaskRepositories(unittest.TestCase):
    """任务仓库测试"""

    def setUp(self):
        init_db()
        self.test_task_id = f"test-task-id-{uuid.uuid4().hex[:8]}"
        self.test_task_content = "测试任务内容"

    def tearDown(self):
        # 清理测试数据
        db = get_db()
        conn = db._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id LIKE ?", ("test-task-id-%",))
            cursor.execute("DELETE FROM logs WHERE task_id LIKE ?", ("test-task-id-%",))
            conn.commit()
        finally:
            db._release_conn(conn)

    def test_create_task(self):
        """测试创建任务"""
        create_task(self.test_task_id, self.test_task_content)
        task = get_task(self.test_task_id)
        self.assertEqual(task["id"], self.test_task_id)
        self.assertEqual(task["task"], self.test_task_content)
        self.assertEqual(task["status"], "pending")

    def test_get_task_not_found(self):
        """测试获取不存在的任务"""
        with self.assertRaises(TaskNotFoundError):
            get_task("non-existent-id-" + uuid.uuid4().hex[:8])

    def test_update_task_status(self):
        """测试更新任务状态"""
        create_task(self.test_task_id, self.test_task_content)
        update_task(self.test_task_id, status="running")
        task = get_task(self.test_task_id)
        self.assertEqual(task["status"], "running")

    def test_update_task_result(self):
        """测试更新任务结果"""
        create_task(self.test_task_id, self.test_task_content)
        test_result = {"testcases": [], "coverage": 100}
        update_task(self.test_task_id, status="success", result=test_result)
        task = get_task(self.test_task_id)
        self.assertEqual(task["status"], "success")
        import json
        result_data = json.loads(task["result"])
        self.assertEqual(result_data["coverage"], 100)


class TestLogRepositories(unittest.TestCase):
    """日志仓库测试"""

    def setUp(self):
        init_db()
        self.test_task_id = f"test-task-id-logs-{uuid.uuid4().hex[:8]}"
        create_task(self.test_task_id, "测试任务")

    def tearDown(self):
        # 清理测试数据
        db = get_db()
        conn = db._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id LIKE ?", ("test-task-id-logs-%",))
            cursor.execute("DELETE FROM logs WHERE task_id LIKE ?", ("test-task-id-logs-%",))
            conn.commit()
        finally:
            db._release_conn(conn)

    def test_insert_log(self):
        """测试插入日志"""
        insert_log(self.test_task_id, "USER", "测试日志")
        logs = get_logs(self.test_task_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "测试日志")
        self.assertEqual(logs[0]["node"], "USER")

    def test_get_logs_empty(self):
        """测试获取空日志"""
        logs = get_logs(self.test_task_id)
        self.assertEqual(len(logs), 0)


class TestKnowledgeRepositories(unittest.TestCase):
    """知识库仓库集成测试"""

    def setUp(self):
        init_db()
        self.test_kb_id = f"test-kb-{uuid.uuid4().hex[:8]}"
        self.test_task_id = f"test-task-kb-{uuid.uuid4().hex[:8]}"
        self.test_case_ids = json.dumps(["TC001", "TC002", "TC005"], ensure_ascii=False)

    def tearDown(self):
        # 清理测试数据
        db = get_db()
        with get_connection() as conn:
            conn.execute("DELETE FROM knowledge_bases WHERE id LIKE ?", (f"test-kb-%",))
            conn.execute("DELETE FROM knowledge_items WHERE knowledge_base_id LIKE ?", (f"test-kb-%",))
            conn.commit()

    def test_create_and_get_knowledge_base(self):
        """创建并查询知识库"""
        create_knowledge_base(
            self.test_kb_id,
            task_id=self.test_task_id,
            title="手机号登录",
            modules_json='["手机号登录"]',
            source_case_ids=self.test_case_ids,
            case_content_hashes='{"TC001": "hash1", "TC002": "hash2"}'
        )
        kb = get_knowledge_base(self.test_kb_id)
        self.assertEqual(kb["id"], self.test_kb_id)
        self.assertEqual(kb["title"], "手机号登录")
        self.assertEqual(kb["status"], "active")

    def test_find_kb_containing_cases_match(self):
        """查找包含指定用例的知识库——匹配"""
        create_knowledge_base(
            self.test_kb_id,
            task_id=self.test_task_id,
            title="测试",
            source_case_ids=self.test_case_ids,
        )
        kb = find_kb_containing_cases(["TC002", "TC999"])
        self.assertIsNotNone(kb)
        self.assertEqual(kb["id"], self.test_kb_id)

    def test_find_kb_containing_cases_no_match(self):
        """查找包含指定用例的知识库——不匹配"""
        create_knowledge_base(
            self.test_kb_id,
            task_id=self.test_task_id,
            title="测试",
            source_case_ids=self.test_case_ids,
        )
        kb = find_kb_containing_cases(["TC999", "TC100"])
        self.assertIsNone(kb)

    def test_find_kb_containing_cases_empty_input(self):
        """空输入应返回 None"""
        self.assertIsNone(find_kb_containing_cases([]))

    def test_find_kb_containing_cases_multiple_kbs(self):
        """多个知识库，应返回第一个匹配的"""
        kb_id2 = f"test-kb-{uuid.uuid4().hex[:8]}"
        create_knowledge_base(
            self.test_kb_id,
            task_id=self.test_task_id,
            title="KB1",
            source_case_ids=json.dumps(["TC001", "TC002"]),
        )
        create_knowledge_base(
            kb_id2,
            task_id=self.test_task_id,
            title="KB2",
            source_case_ids=json.dumps(["TC003", "TC004"]),
        )
        # 查找 TC003，应返回 KB2
        kb = find_kb_containing_cases(["TC003"])
        self.assertIsNotNone(kb)
        self.assertEqual(kb["title"], "KB2")

    def test_get_knowledge_base_not_found(self):
        """查询不存在的知识库，应抛出 DatabaseError"""
        with self.assertRaises(DatabaseError):
            get_knowledge_base(f"non-existent-{uuid.uuid4().hex[:8]}")

    def test_update_knowledge_base(self):
        """更新知识库"""
        from storage.knowledge_repositories import update_knowledge_base
        create_knowledge_base(
            self.test_kb_id,
            task_id=self.test_task_id,
            title="原标题",
            source_case_ids=self.test_case_ids,
        )
        update_knowledge_base(self.test_kb_id, title="新标题")
        kb = get_knowledge_base(self.test_kb_id)
        self.assertEqual(kb["title"], "新标题")


if __name__ == "__main__":
    unittest.main(verbosity=2)