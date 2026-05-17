#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存储模块单元测试"""
import sqlite3
import unittest
import uuid
from unittest.mock import Mock, patch, MagicMock

from storage.db import get_db, init_db
from storage.repositories import (
    create_task, get_task, update_task,
    insert_log, get_logs
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


if __name__ == "__main__":
    unittest.main(verbosity=2)