# -*- coding: utf-8 -*-
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from typing import Deque, Optional

from config.config import Config
from utils.exceptions import DatabaseError
from utils.logger import logger


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        self._write_lock = threading.Lock()
        self._pool_lock = threading.Lock()
        self._connection_pool: Deque[sqlite3.Connection] = deque()
        self._active_connections = 0
        self._max_connections = 10
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            self._init_schema(conn)

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        try:
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                task TEXT,
                status TEXT,
                result TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """)
            c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                node TEXT,
                message TEXT,
                created_at TEXT
            )
            """)
            c.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_task_id ON logs(task_id)
            """)
            c.execute("""
            CREATE TABLE IF NOT EXISTS node_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                token_usage TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(task_id, node_name)
            )
            """)
            c.execute("""
            CREATE INDEX IF NOT EXISTS idx_node_status_task_id ON node_status(task_id)
            """)
            # 兼容旧表：如果缺少 token_usage 列则添加
            try:
                c.execute("ALTER TABLE node_status ADD COLUMN token_usage TEXT")
            except Exception:
                pass
            conn.commit()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise DatabaseError(f"数据库初始化失败: {e}") from e

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = None
        return conn

    def _get_conn(self, timeout: float = 30.0) -> sqlite3.Connection:
        start_time = datetime.now(timezone.utc)
        wait_interval = 0.1

        while True:
            with self._pool_lock:
                if self._connection_pool:
                    conn = self._connection_pool.popleft()
                    try:
                        conn.execute("SELECT 1")
                        self._active_connections += 1
                        logger.debug(f"从连接池获取连接，当前池大小: {len(self._connection_pool)}, 活跃: {self._active_connections}")
                        return conn
                    except Exception:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        self._active_connections = max(0, self._active_connections - 1)
                        logger.debug("从池中取出的连接已失效，已关闭")

                if self._active_connections < self._max_connections:
                    conn = self._create_connection()
                    self._active_connections += 1
                    logger.debug(f"创建新连接，当前池大小: {len(self._connection_pool)}, 活跃: {self._active_connections}")
                    return conn

                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.error(f"获取数据库连接超时，已等待 {elapsed:.2f} 秒")
                    raise DatabaseError(f"获取数据库连接超时，已等待 {elapsed:.2f} 秒")

            time.sleep(wait_interval)
            wait_interval = min(wait_interval * 1.5, 2.0)

    def _release_conn(self, conn: sqlite3.Connection) -> None:
        with self._pool_lock:
            self._active_connections -= 1
            try:
                conn.execute("SELECT 1")
                if len(self._connection_pool) < self._max_connections:
                    self._connection_pool.append(conn)
                    logger.debug(f"连接已放回池，当前池大小: {len(self._connection_pool)}, 活跃: {self._active_connections}")
                else:
                    conn.close()
                    logger.debug(f"连接池已满，关闭多余连接，活跃: {self._active_connections}")
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                logger.debug(f"连接已失效并关闭，活跃: {self._active_connections}")

    def close_all_connections(self) -> None:
        with self._pool_lock:
            while self._connection_pool:
                conn = self._connection_pool.popleft()
                try:
                    conn.close()
                except Exception:
                    pass
            self._active_connections = 0
            logger.info("所有数据库连接已关闭")

    def health_check(self) -> int:
        removed = 0
        with self._pool_lock:
            healthy_pool: Deque[sqlite3.Connection] = deque()
            while self._connection_pool:
                conn = self._connection_pool.popleft()
                try:
                    conn.execute("SELECT 1")
                    healthy_pool.append(conn)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    removed += 1
                    self._active_connections = max(0, self._active_connections - 1)
            self._connection_pool = healthy_pool
        if removed > 0:
            logger.warning(f"连接池健康检查移除了 {removed} 个失效连接，当前池大小: {len(self._connection_pool)}")
        return removed

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


_db_instance: Optional[Database] = None
_db_lock = threading.Lock()


def get_db() -> Database:
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = Database()
    return _db_instance


def init_db() -> None:
    get_db()
