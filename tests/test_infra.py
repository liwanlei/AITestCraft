#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock

from storage.db import Database, get_db
from config.config import Config


class TestDatabaseHealthCheck(unittest.TestCase):

    @patch("sqlite3.connect")
    def test_health_check_removes_dead_connections(self, mock_connect):
        db = Database(db_path=":memory:")
        db._max_connections = 5

        dead_conn = MagicMock()
        dead_conn.execute.side_effect = Exception("connection lost")
        db._connection_pool.append(dead_conn)
        db._active_connections = 1

        alive_conn = MagicMock()
        alive_conn.execute.return_value = None
        db._connection_pool.append(alive_conn)
        db._active_connections = 2

        removed = db.health_check()

        self.assertEqual(removed, 1)
        self.assertEqual(len(db._connection_pool), 1)
        self.assertEqual(db._active_connections, 1)

    @patch("sqlite3.connect")
    def test_health_check_no_dead_connections(self, mock_connect):
        db = Database(db_path=":memory:")
        db._max_connections = 5

        alive_conn = MagicMock()
        alive_conn.execute.return_value = None
        db._connection_pool.append(alive_conn)
        db._active_connections = 1

        removed = db.health_check()

        self.assertEqual(removed, 0)
        self.assertEqual(len(db._connection_pool), 1)

    @patch("sqlite3.connect")
    def test_health_check_empty_pool(self, mock_connect):
        db = Database(db_path=":memory:")
        removed = db.health_check()
        self.assertEqual(removed, 0)


class TestConfigSingleton(unittest.TestCase):

    def test_config_is_singleton(self):
        c1 = Config()
        c2 = Config()
        self.assertIs(c1, c2)

    def test_config_class_attributes(self):
        self.assertTrue(hasattr(Config, "BASE_DIR"))
        self.assertTrue(hasattr(Config, "DB_PATH"))

    def test_config_validate(self):
        Config.validate()

    def test_config_safe_repr(self):
        result = Config.safe_repr()
        self.assertIsInstance(result, dict)
        # 敏感信息应被脱敏
        self.assertIn("FEISHU_USER_ACCESS_TOKEN", result)
        sensitive_value = result["FEISHU_USER_ACCESS_TOKEN"]
        if sensitive_value:
            self.assertEqual(sensitive_value, "***")


if __name__ == "__main__":
    unittest.main()