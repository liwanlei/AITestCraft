# -*- coding: utf-8 -*-
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterator, List, Optional

from storage.db import get_db
from utils.exceptions import DatabaseError, TaskNotFoundError
from utils.logger import logger


@contextmanager
def _get_connection() -> Iterator[Any]:
    db = get_db()
    conn = None
    try:
        conn = db._get_conn()
        yield conn
    except (TaskNotFoundError, DatabaseError):
        raise
    except Exception as e:
        raise DatabaseError(str(e)) from e
    finally:
        if conn:
            db._release_conn(conn)


def create_task(task_id: str, task: str) -> None:
    db = get_db()
    with _get_connection() as conn:
        with db._write_lock:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, task, "pending", None, db._now(), db._now())
            )
            conn.commit()
        logger.info(f"任务创建成功: {task_id}...")


def update_task(task_id: str, status: Optional[str] = None, result: Optional[Any] = None) -> None:
    db = get_db()
    with _get_connection() as conn:
        with db._write_lock:
            if result is not None:
                conn.execute(
                    "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
                    (status if status is not None else "success", json.dumps(result, ensure_ascii=False), db._now(), task_id)
                )
                logger.info(f"任务状态更新: {task_id}... -> {status}, 结果已保存")
            elif status is not None:
                conn.execute(
                    "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                    (status, db._now(), task_id)
                )
                logger.info(f"任务状态更新: {task_id}... -> {status}")
            conn.commit()


def get_task(task_id: str) -> Dict[str, Any]:
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, task, status, result, created_at, updated_at FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        if not row:
            raise TaskNotFoundError(f"任务 {task_id} 不存在")
        columns = [desc[0] for desc in cur.description]
        logger.debug(f"获取任务成功: {task_id}...")
        return dict(zip(columns, row))


def insert_log(task_id: str, node: str, message: str) -> None:
    db = get_db()
    with _get_connection() as conn:
        with db._write_lock:
            conn.execute(
                "INSERT INTO logs (task_id, node, message, created_at) VALUES (?, ?, ?, ?)",
                (task_id, node, message, db._now())
            )
            conn.commit()
        logger.debug(f"日志插入成功: [{node}] {task_id}")


def get_tasks_by_status(statuses: List[str]) -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        cur = conn.cursor()
        placeholders = ",".join("?" * len(statuses))
        cur.execute(
            f"SELECT id, task, status, result, created_at, updated_at FROM tasks WHERE status IN ({placeholders})",
            tuple(statuses)
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _format_datetime(iso_datetime: str) -> str:
    """
    将 ISO 8601 格式的时间转换为本地时间 "YYYY-MM-DD HH:MM:SS" 格式
    
    Args:
        iso_datetime: ISO 8601 格式的时间字符串，如 "2026-05-17T08:43:44.135007+00:00"
        
    Returns:
        格式化后的本地时间字符串，如 "2026-05-17 16:43:44"（东八区）
    """
    if not iso_datetime:
        return ""
    
    try:
        # 解析 ISO 8601 格式时间
        # 处理带时区的时间字符串
        if iso_datetime.endswith("+00:00"):
            # 移除时区后缀，解析为 UTC 时间
            iso_datetime = iso_datetime[:-6]
            dt = datetime.fromisoformat(iso_datetime)
            dt = dt.replace(tzinfo=timezone.utc)
        elif "+" in iso_datetime or (iso_datetime.count("-") > 2 and "T" in iso_datetime):
            # 已经包含时区信息
            dt = datetime.fromisoformat(iso_datetime)
        else:
            # 无时区信息，假设为 UTC
            dt = datetime.fromisoformat(iso_datetime)
            dt = dt.replace(tzinfo=timezone.utc)
        
        # 转换为本地时间（东八区 UTC+8）
        local_tz = timezone(timedelta(hours=8))
        local_dt = dt.astimezone(local_tz)
        
        # 格式化为 "YYYY-MM-DD HH:MM:SS"
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        logger.warning(f"时间格式转换失败: {e}, 原始值: {iso_datetime}")
        # 降级处理：直接返回原始字符串
        try:
            if "." in iso_datetime:
                iso_datetime = iso_datetime.split(".")[0]
            formatted = iso_datetime.replace("T", " ")
            if "+" in formatted:
                formatted = formatted.split("+")[0]
            return formatted[:19]
        except:
            return iso_datetime


def get_logs(task_id: str) -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT node, message, created_at FROM logs WHERE task_id=? ORDER BY id ASC",
            (task_id,)
        )
        columns = [desc[0] for desc in cur.description]
        logs = []
        for row in cur.fetchall():
            log_dict = dict(zip(columns, row))
            created_at = log_dict.get("created_at", "")
            if created_at:
                log_dict["created_at"] = _format_datetime(created_at)
            message = log_dict.get("message", "")
            if message:
                try:
                    log_dict["message"] = json.loads(message)
                except (json.JSONDecodeError, ValueError):
                    pass
            logs.append(log_dict)
        return logs


def update_node_status(task_id: str, node_name: str, status: str, result: Optional[Any] = None, token_usage: Optional[Dict[str, int]] = None) -> None:
    db = get_db()
    with _get_connection() as conn:
        with db._write_lock:
            result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
            token_usage_json = json.dumps(token_usage, ensure_ascii=False) if token_usage is not None else None
            conn.execute(
                """INSERT INTO node_status (task_id, node_name, status, result, token_usage, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id, node_name) DO UPDATE SET
                   status=?, result=?, token_usage=?, updated_at=?""",
                (task_id, node_name, status, result_json, token_usage_json, db._now(), db._now(),
                 status, result_json, token_usage_json, db._now())
            )
            conn.commit()
        logger.debug(f"节点状态更新: [{node_name}] {task_id}... -> {status}")


def get_node_status(task_id: str) -> Dict[str, Dict[str, Any]]:
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT node_name, status, result, token_usage, created_at, updated_at FROM node_status WHERE task_id=?",
            (task_id,)
        )
        result = {}
        for row in cur.fetchall():
            node_name, status, result_json, token_usage_json, created_at, updated_at = row
            result[node_name] = {
                "status": status,
                "result": json.loads(result_json) if result_json else None,
                "token_usage": json.loads(token_usage_json) if token_usage_json else None,
                "created_at": created_at,
                "updated_at": updated_at
            }
        return result


def get_last_completed_node(task_id: str) -> Optional[str]:
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT node_name FROM node_status 
               WHERE task_id=? AND status='completed'
               ORDER BY updated_at DESC LIMIT 1""",
            (task_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def clear_node_status(task_id: str) -> None:
    db = get_db()
    with _get_connection() as conn:
        with db._write_lock:
            conn.execute("DELETE FROM node_status WHERE task_id=?", (task_id,))
            conn.commit()
        logger.debug(f"节点状态已清除: {task_id}...")
