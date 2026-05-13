# -*- coding: utf-8 -*-
import sqlite3
import json
import threading
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Dict, Deque
from pathlib import Path
from collections import deque

from config.config import Config
from utils.exceptions import DatabaseError, TaskNotFoundError
from utils.logger import logger


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        self._write_lock = threading.Lock()  # 写操作锁
        self._pool_lock = threading.Lock()   # 连接池锁
        self._connection_pool: Deque[sqlite3.Connection] = deque()
        self._active_connections = 0
        self._max_connections = 10  # 最大连接数
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        # 使用临时连接初始化schema
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
            conn.commit()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise DatabaseError(f"数据库初始化失败: {e}") from e

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = None  # 默认返回元组
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        """从连接池获取数据库连接"""
        with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.popleft()
                self._active_connections += 1
                logger.debug(f"从连接池获取连接，当前池大小: {len(self._connection_pool)}, 活跃: {self._active_connections}")
                return conn
            
            if self._active_connections < self._max_connections:
                conn = self._create_connection()
                self._active_connections += 1
                logger.debug(f"创建新连接，当前池大小: {len(self._connection_pool)}, 活跃: {self._active_connections}")
                return conn
            
            logger.warning(f"数据库连接池已满，活跃: {self._active_connections}")
            raise DatabaseError("数据库连接池已满")

    def _release_conn(self, conn: sqlite3.Connection) -> None:
        """将连接放回连接池"""
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
        """关闭所有连接"""
        with self._pool_lock:
            while self._connection_pool:
                conn = self._connection_pool.popleft()
                conn.close()
            self._active_connections = 0
            logger.info("所有数据库连接已关闭")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_task(self, task_id: str, task: str) -> None:
        conn = None
        try:
            conn = self._get_conn()
            with self._write_lock:
                conn.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                    (task_id, task, "pending", None, self._now(), self._now())
                )
                conn.commit()
            logger.info(f"任务创建成功: {task_id[:8]}...")
        except Exception as e:
            logger.error(f"创建任务失败: {task_id[:8]}...: {e}")
            raise DatabaseError(f"创建任务失败: {e}") from e
        finally:
            if conn:
                self._release_conn(conn)

    def update_task(self, task_id: str, status: Optional[str] = None, result: Optional[Any] = None) -> None:
        conn = None
        try:
            conn = self._get_conn()
            with self._write_lock:
                if result is not None:
                    conn.execute(
                        "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
                        (status if status is not None else "success", json.dumps(result, ensure_ascii=False), self._now(), task_id)
                    )
                    logger.info(f"任务状态更新: {task_id[:8]}... -> {status}, 结果已保存")
                elif status is not None:
                    conn.execute(
                        "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                        (status, self._now(), task_id)
                    )
                    logger.info(f"任务状态更新: {task_id[:8]}... -> {status}")
                conn.commit()
        except Exception as e:
            logger.error(f"更新任务失败: {task_id[:8]}...: {e}")
            raise DatabaseError(f"更新任务失败: {e}") from e
        finally:
            if conn:
                self._release_conn(conn)

    def get_task(self, task_id: str) -> Tuple:
        conn = None
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            if not row:
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            logger.debug(f"获取任务成功: {task_id[:8]}...")
            return row
        except TaskNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取任务失败: {task_id[:8]}...: {e}")
            raise DatabaseError(f"获取任务失败: {e}") from e
        finally:
            if conn:
                self._release_conn(conn)

    def insert_log(self, task_id: str, node: str, message: str) -> None:
        conn = None
        try:
            conn = self._get_conn()
            with self._write_lock:
                conn.execute(
                    "INSERT INTO logs (task_id, node, message, created_at) VALUES (?, ?, ?, ?)",
                    (task_id, node, message, self._now())
                )
                conn.commit()
            logger.debug(f"日志插入成功: [{node}] {task_id[:8]}...")
        except Exception as e:
            logger.error(f"插入日志失败: [{node}] {task_id[:8]}...: {e}")
            raise DatabaseError(f"插入日志失败: {e}") from e
        finally:
            if conn:
                self._release_conn(conn)

    def get_logs(self, task_id: str) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT node, message, created_at FROM logs WHERE task_id=? ORDER BY id ASC",
                (task_id,)
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            raise DatabaseError(f"获取日志失败: {e}") from e
        finally:
            if conn:
                conn.row_factory = None
                self._release_conn(conn)


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


def create_task(task_id: str, task: str) -> None:
    get_db().create_task(task_id, task)


def update_task(task_id: str, status: Optional[str] = None, result: Optional[Any] = None) -> None:
    get_db().update_task(task_id, status, result)


def get_task(task_id: str) -> Tuple:
    return get_db().get_task(task_id)


def insert_log(task_id: str, node: str, message: str) -> None:
    get_db().insert_log(task_id, node, message)


def get_logs(task_id: str) -> List[Dict[str, Any]]:
    return get_db().get_logs(task_id)
