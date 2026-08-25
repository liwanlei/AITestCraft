# -*- coding: utf-8 -*-
import json
from typing import Any, Dict, List, Optional

from storage.db import get_db
from storage.repositories import get_connection
from utils.logger import logger


def create_knowledge_base(
    kb_id: str,
    task_id: str,
    title: str,
    markdown_content: str = "",
    modules_json: str = "[]",
    source_case_ids: str = "[]",
    description: str = "",
    case_content_hashes: str = "{}"
) -> None:
    """创建知识库主记录"""
    db = get_db()
    with get_connection() as conn:
        with db._write_lock:
            conn.execute(
                """INSERT INTO knowledge_bases 
                   (id, task_id, title, description, markdown_content, modules_json, source_case_ids, case_content_hashes, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                (kb_id, task_id, title, description, markdown_content, modules_json, source_case_ids, case_content_hashes, db._now(), db._now())
            )
            conn.commit()
        logger.info(f"知识库创建成功: {kb_id}")


def get_knowledge_base(kb_id: str) -> Dict[str, Any]:
    """查询知识库详情"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, task_id, title, description, markdown_content, modules_json, source_case_ids, case_content_hashes, status, created_at, updated_at FROM knowledge_bases WHERE id=?",
            (kb_id,)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"知识库 {kb_id} 不存在")
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


def find_kb_containing_cases(case_ids: List[str]) -> Optional[Dict[str, Any]]:
    """
    查找包含指定用例的知识库（按 source_case_ids 匹配）
    
    Args:
        case_ids: 用例 ID 列表
        
    Returns:
        匹配的知识库信息，未找到返回 None
    """
    if not case_ids:
        return None
    
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, task_id, title, source_case_ids, case_content_hashes, status, item_count FROM knowledge_bases WHERE status='active'"
        )
        columns = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            kb = dict(zip(columns, row))
            try:
                stored_ids = json.loads(kb.get("source_case_ids", "[]"))
            except Exception:
                stored_ids = []
            # 检查是否有交集
            if set(case_ids) & set(stored_ids):
                return kb
        return None
    finally:
        db._release_conn(conn)


def find_knowledge_base_by_title(title: str) -> Optional[Dict[str, Any]]:
    """
    根据 title（categoryName）查找知识库
    
    Args:
        title: 知识库标题（即 categoryName）
        
    Returns:
        匹配的知识库信息，未找到返回 None
    """
    if not title:
        return None
    
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, task_id, title, source_case_ids, case_content_hashes, status, item_count FROM knowledge_bases WHERE title=? AND status='active'",
            (title,)
        )
        columns = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        if row:
            return dict(zip(columns, row))
        return None
    finally:
        db._release_conn(conn)


def list_knowledge_bases(status: str = "active") -> List[Dict[str, Any]]:
    """查询知识库列表"""
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT kb.id, kb.title, kb.modules_json, kb.item_count, kb.created_at,
                      (SELECT COUNT(*) FROM knowledge_items ki WHERE ki.knowledge_base_id = kb.id) AS actual_item_count
               FROM knowledge_bases kb WHERE kb.status=? ORDER BY kb.created_at DESC""",
            (status,)
        )
        columns = [desc[0] for desc in cur.description]
        result = []
        for row in cur.fetchall():
            item = dict(zip(columns, row))
            # 使用实际统计数量覆盖存储的 item_count
            item["item_count"] = item.get("actual_item_count", item.get("item_count", 0))
            # 解析 modules_json
            if item.get("modules_json"):
                try:
                    item["modules"] = json.loads(item["modules_json"])
                except Exception:
                    item["modules"] = []
            result.append(item)
        return result
    finally:
        db._release_conn(conn)


def update_knowledge_base(kb_id: str, **kwargs) -> None:
    """更新知识库记录"""
    # 白名单校验，防止 SQL 注入
    allowed_keys = {
        "title", "description", "markdown_content", "modules_json",
        "source_case_ids", "case_content_hashes", "item_count", "status", "updated_at"
    }
    invalid_keys = set(kwargs.keys()) - allowed_keys
    if invalid_keys:
        raise ValueError(f"不允许更新的字段: {invalid_keys}")
    
    db = get_db()
    conn = db._get_conn()
    try:
        # 构建更新语句
        set_clauses = []
        values = []
        for key, value in kwargs.items():
            set_clauses.append(f"{key}=?")
            values.append(value)
        set_clauses.append("updated_at=?")
        values.append(db._now())
        values.append(kb_id)
        
        sql = f"UPDATE knowledge_bases SET {', '.join(set_clauses)} WHERE id=?"
        conn.execute(sql, values)
        conn.commit()
        logger.debug(f"知识库更新成功: {kb_id}")
    finally:
        db._release_conn(conn)


def create_knowledge_item(
    item_id: str,
    kb_id: str,
    module: str,
    item_type: str,
    content: str,
    priority: str = "",
    source_case_ids: str = "[]",
    status: str = "active",
    old_content: str = "",
    change_reason: str = ""
) -> None:
    """创建知识点明细"""
    db = get_db()
    conn = db._get_conn()
    try:
        conn.execute(
            """INSERT INTO knowledge_items 
               (id, knowledge_base_id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, kb_id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, db._now(), db._now())
        )
        conn.commit()
        logger.debug(f"知识点创建成功: {item_id}")
    finally:
        db._release_conn(conn)


def create_knowledge_items_batch(items: List[Dict[str, Any]]) -> None:
    """批量创建知识点（优化性能）"""
    if not items:
        return
    
    db = get_db()
    conn = db._get_conn()
    try:
        conn.execute("BEGIN TRANSACTION")
        for item in items:
            conn.execute(
                """INSERT INTO knowledge_items 
                   (id, knowledge_base_id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["item_id"], item["kb_id"], item["module"], item["item_type"], 
                 item["content"], item["priority"], item["source_case_ids"], 
                 item["status"], item.get("old_content", ""), item.get("change_reason", ""), 
                 db._now(), db._now())
            )
        conn.commit()
        logger.debug(f"批量创建知识点成功: {len(items)} 个")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        db._release_conn(conn)


def get_knowledge_items(kb_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询知识库的所有知识点"""
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, created_at FROM knowledge_items WHERE knowledge_base_id=? AND status=?",
                (kb_id, status)
            )
        else:
            cur.execute(
                "SELECT id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, created_at FROM knowledge_items WHERE knowledge_base_id=?",
                (kb_id,)
            )
        columns = [desc[0] for desc in cur.description]
        result = []
        for row in cur.fetchall():
            item = dict(zip(columns, row))
            # 解析 source_case_ids
            if item.get("source_case_ids"):
                try:
                    item["source_case_ids"] = json.loads(item["source_case_ids"])
                except Exception:
                    item["source_case_ids"] = []
            result.append(item)
        return result
    finally:
        db._release_conn(conn)


def get_changed_items(kb_id: str) -> List[Dict[str, Any]]:
    """查询知识库中所有变更的知识点"""
    return get_knowledge_items(kb_id, status="changed")


def get_active_items(kb_id: str) -> List[Dict[str, Any]]:
    """查询知识库中所有活跃的知识点"""
    return get_knowledge_items(kb_id, status="active")


def delete_knowledge_items_by_kb(kb_id: str) -> int:
    """删除知识库下所有知识点（用于增量更新前清理）"""
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM knowledge_items WHERE knowledge_base_id=?",
            (kb_id,)
        )
        conn.commit()
        deleted_count = cur.rowcount
        logger.debug(f"删除知识库 {kb_id} 下的知识点: {deleted_count} 个")
        return deleted_count
    finally:
        db._release_conn(conn)


def get_knowledge_base_with_items(kb_id: str) -> Dict[str, Any]:
    """获取知识库详情及所有知识点（单次查询，优化性能）"""
    db = get_db()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        
        # 获取知识库
        cur.execute(
            "SELECT id, task_id, title, description, markdown_content, modules_json, source_case_ids, case_content_hashes, status, created_at, updated_at FROM knowledge_bases WHERE id=?",
            (kb_id,)
        )
        kb_row = cur.fetchone()
        if not kb_row:
            raise ValueError(f"知识库 {kb_id} 不存在")
        
        kb_columns = [desc[0] for desc in cur.description]
        kb = dict(zip(kb_columns, kb_row))
        
        # 获取所有知识点（一次查询）
        cur.execute(
            "SELECT id, module, item_type, content, priority, source_case_ids, status, old_content, change_reason, created_at FROM knowledge_items WHERE knowledge_base_id=?",
            (kb_id,)
        )
        
        item_columns = [desc[0] for desc in cur.description]
        all_items = []
        for row in cur.fetchall():
            item = dict(zip(item_columns, row))
            if item.get("source_case_ids"):
                try:
                    item["source_case_ids"] = json.loads(item["source_case_ids"])
                except Exception:
                    item["source_case_ids"] = []
            all_items.append(item)
        
        # 按状态分组
        kb["items"] = [item for item in all_items if item["status"] == "active"]
        kb["changes"] = [item for item in all_items if item["status"] == "changed"]
        
        return kb
    finally:
        db._release_conn(conn)
