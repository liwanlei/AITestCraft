import sqlite3
import json
from datetime import datetime


DB_PATH = "workflow.db"


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
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

    conn.commit()
    conn.close()


def create_task(task_id, task):
    conn = get_conn()
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, task, "pending", None, now(), now())
    )
    conn.commit()
    conn.close()


def update_task(task_id, status=None, result=None):
    conn = get_conn()

    if status and result is None:
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, now(), task_id)
        )
    elif result is not None:
        conn.execute(
            "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
            ("success", json.dumps(result, ensure_ascii=False), now(), task_id)
        )

    conn.commit()
    conn.close()


def get_task(task_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = cur.fetchone()
    conn.close()
    return row


def insert_log(task_id, node, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (task_id, node, message, created_at) VALUES (?, ?, ?, ?)",
        (task_id, node, message, now())
    )
    conn.commit()
    conn.close()


def now():
    return datetime.utcnow().isoformat()