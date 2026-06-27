# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

import httpx

from config.config import Config
from core.taskexecution import knowledgeexecution
from storage.repositories import create_task, update_task, get_task
from storage.knowledge_repositories import (
    create_knowledge_base, get_knowledge_base, get_knowledge_items,
    update_knowledge_base, create_knowledge_item, create_knowledge_items_batch,
    delete_knowledge_items_by_kb, find_knowledge_base_by_cases, find_knowledge_base_by_title
)
from utils.logger import logger


def detect_changed_cases(kb: dict, case_ids: List[str]) -> List[str]:
    """
    检测变更的用例（基于用例内容哈希对比）
    
    Args:
        kb: 知识库信息
        case_ids: 用例 ID 列表
        
    Returns:
        变更的用例 ID 列表
    """
    changed_cases = []
    
    try:
        # 获取知识库中存储的用例内容哈希映射
        stored_hashes = _parse_stored_hashes(kb.get("case_content_hashes", "{}"))
        
        # 调用用例服务获取最新用例内容哈希
        for case_id in case_ids:
            case_info = _fetch_case_info(case_id)
            current_hash = case_info.get("content_hash", "")
            stored_hash = stored_hashes.get(case_id, "")
            
            # 对比内容哈希判断是否变更
            if current_hash != stored_hash:
                changed_cases.append(case_id)
                
    except Exception as e:
        logger.warning(f"检测用例变更失败: {e}")
    
    return changed_cases


def _parse_stored_hashes(hashes_str: str) -> Dict[str, str]:
    """
    解析存储的用例内容哈希映射
    
    Args:
        hashes_str: JSON 字符串格式的哈希映射
        
    Returns:
        用例ID到哈希的字典
    """
    try:
        return json.loads(hashes_str)
    except Exception:
        return {}


def _fetch_category_name(case_id: str) -> str:
    """
    调用外部用例服务获取 categoryName
    
    Args:
        case_id: 用例 ID
        
    Returns:
        categoryName 字符串
    """
    base_url = Config.CASE_SERVICE_BASE_URL
    api_path = Config.CASE_SERVICE_GET_CASE_API
    
    if not base_url:
        return ""
    
    try:
        url = f"{base_url.rstrip('/')}{api_path}"
        resp = httpx.get(url, params={"caseId": case_id}, timeout=Config.KNOWLEDGE_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 200:
            return data.get("data", {}).get("categoryName", "")
    except Exception as e:
        logger.warning(f"获取 categoryName 失败: case_id={case_id}, 错误: {e}")
    return ""


def _fetch_case_info(case_id: str) -> Dict[str, Any]:
    """
    调用外部用例服务获取用例信息（包含内容哈希）
    
    API 返回格式:
    {
        "code": 200,
        "msg": "服务运行成功",
        "data": {
            "caseContent": { ... },
            "updated_at": "2026-06-13T13:49:18.000+0000",
            "isClickable": 1,
            "id": 2223,
            "title": "测试"
        }
    }
    
    Args:
        case_id: 用例 ID
        
    Returns:
        用例信息（包含 content_hash、title、case_content）
    """
    base_url = Config.CASE_SERVICE_BASE_URL
    api_path = Config.CASE_SERVICE_GET_CASE_API
    
    if not base_url:
        # 未配置外部服务，使用模拟数据
        case_content = _mock_fetch_case_content(case_id)
        content_hash = hashlib.md5(case_content.encode('utf-8')).hexdigest()
        return {
            "case_id": case_id,
            "content_hash": content_hash,
            "title": f"用例 {case_id}",
            "status": "active"
        }
    
    try:
        url = f"{base_url.rstrip('/')}{api_path}"
        resp = httpx.get(url, params={"caseId": case_id}, timeout=Config.KNOWLEDGE_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != 200:
            logger.warning(f"用例服务返回错误: case_id={case_id}, msg={data.get('msg')}")
            return {"case_id": case_id, "content_hash": "", "title": "", "status": "error"}
        
        case_data = data.get("data", {})
        case_content = case_data.get("caseContent", {})
        title = case_data.get("title", "")
        
        # 对 caseContent 计算内容哈希
        content_str = json.dumps(case_content, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.md5(content_str.encode('utf-8')).hexdigest()
        
        return {
            "case_id": case_id,
            "content_hash": content_hash,
            "title": title,
            "status": "active",
            "case_content": case_content
        }
    except Exception as e:
        logger.warning(f"获取用例信息失败: case_id={case_id}, 错误: {e}")
        return {"case_id": case_id, "content_hash": "", "title": "", "status": "error"}


def _fetch_case_content(case_id: str) -> Dict[str, Any]:
    """
    调用外部用例服务获取用例完整内容（caseContent）
    
    Args:
        case_id: 用例 ID
        
    Returns:
        caseContent 字典，获取失败返回空字典
    """
    base_url = Config.CASE_SERVICE_BASE_URL
    api_path = Config.CASE_SERVICE_GET_CASE_API
    
    if not base_url:
        return {}
    
    try:
        url = f"{base_url.rstrip('/')}{api_path}"
        resp = httpx.get(url, params={"caseId": case_id}, timeout=Config.KNOWLEDGE_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != 200:
            logger.warning(f"用例服务返回错误: case_id={case_id}, msg={data.get('msg')}")
            return {}
        
        return data.get("data", {}).get("caseContent", {})
    except Exception as e:
        logger.warning(f"获取用例内容失败: case_id={case_id}, 错误: {e}")
        return {}


def _mock_fetch_case_content(case_id: str) -> str:
    """
    模拟获取用例完整内容（未配置外部用例服务时的降级方案）
    
    Args:
        case_id: 用例 ID
        
    Returns:
        用例完整内容字符串
    """
    mock_cases = {
        "TC001": """前置条件：用户未登录
执行步骤：
1. 打开登录页面
2. 输入用户名
3. 输入密码
4. 点击登录按钮
预期结果：登录成功，跳转首页""",
        "TC002": """前置条件：用户已登录
执行步骤：
1. 进入个人中心
2. 点击退出按钮
预期结果：退出成功，返回登录页""",
        "TC003": """前置条件：用户已登录
执行步骤：
1. 进入购物车
2. 选择商品
3. 点击结算
预期结果：进入订单确认页面"""
    }
    return mock_cases.get(case_id, f"用例 {case_id} 的完整内容")


async def refresh_knowledge_base(kb_id: str, case_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    增量更新知识库
    
    Args:
        kb_id: 知识库 ID
        case_ids: 可选，指定要更新的用例ID列表；不指定则检查所有源用例
    
    Returns:
        更新结果
    """
    try:
        # 获取知识库信息
        kb = get_knowledge_base(kb_id)
        
        # 确定要检查的用例列表
        if case_ids is None:
            source_case_ids = json.loads(kb.get("source_case_ids", "[]"))
        else:
            source_case_ids = case_ids
        
        # 检测变更的用例
        changed_cases = detect_changed_cases(kb, source_case_ids)
        
        if not changed_cases:
            return {
                "success": True,
                "message": "未检测到变更的用例",
                "updated_count": 0,
                "changed_cases": []
            }
        
        # 执行增量更新
        await _incremental_update_knowledge(kb_id, kb, changed_cases)
        
        return {
            "success": True,
            "message": f"知识库已更新",
            "updated_count": len(changed_cases),
            "changed_cases": changed_cases
        }
        
    except Exception as e:
        logger.error(f"刷新知识库失败: {kb_id}, 错误: {e}")
        return {
            "success": False,
            "message": f"刷新失败: {str(e)}",
            "updated_count": 0,
            "changed_cases": []
        }


async def _incremental_update_knowledge(kb_id: str, kb: dict, changed_case_ids: List[str]) -> None:
    """
    执行增量更新
    
    Args:
        kb_id: 知识库 ID
        kb: 知识库信息
        changed_case_ids: 变更的用例 ID 列表
    """
    logger.info(f"开始增量更新知识库: {kb_id}, 变更用例数: {len(changed_case_ids)}")
    
    # 获取当前知识库的知识点
    existing_items = get_knowledge_items(kb_id)
    
    # 提取变更用例的新知识
    new_items = await _extract_new_knowledge(changed_case_ids)
    
    # 执行冲突解决和合并
    merged_items = _merge_knowledge_items(existing_items, new_items, changed_case_ids)
    
    # 更新知识库
    _apply_knowledge_changes(kb_id, merged_items, changed_case_ids)
    
    logger.info(f"增量更新完成: {kb_id}")


async def _extract_new_knowledge(case_ids: List[str]) -> List[Dict[str, Any]]:
    """
    从变更用例中提取新知识
    
    Args:
        case_ids: 用例 ID 列表
        
    Returns:
        新知识点列表
    """
    # 模拟提取过程，实际应调用知识提取工作流
    new_items = []
    for case_id in case_ids:
        new_items.append({
            "case_id": case_id,
            "module": "通用模块",
            "item_type": "功能需求",
            "content": f"从用例 {case_id} 提取的需求知识点（已更新）",
            "priority": "P0",
            "source_case_ids": [case_id]
        })
    return new_items


def _merge_knowledge_items(
    existing_items: List[Dict[str, Any]],
    new_items: List[Dict[str, Any]],
    changed_case_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    合并新旧知识点，执行冲突解决
    
    Args:
        existing_items: 现有知识点
        new_items: 新知识点
        changed_case_ids: 变更的用例 ID 列表
        
    Returns:
        合并后的知识点列表
    """
    merged_items = []
    
    # 使用完整内容哈希作为匹配 key，避免截断碰撞
    def _item_key(item):
        content = item.get("content", "")
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        return f"{item['module']}_{content_hash}"
    
    # 按模块和内容哈希建立索引
    existing_index = {}
    for item in existing_items:
        key = _item_key(item)
        existing_index[key] = item
    
    # 记录已被新知识点匹配的旧知识点 key
    matched_existing_keys = set()
    
    # 处理新知识点
    for new_item in new_items:
        key = _item_key(new_item)
        
        if key in existing_index:
            matched_existing_keys.add(key)
            # 冲突处理：根据用例ID判断版本
            existing_item = existing_index[key]
            existing_case_ids = existing_item.get("source_case_ids", [])
            
            # 获取最大用例ID
            max_existing_id = max([int(cid.replace("TC", "")) for cid in existing_case_ids if cid.startswith("TC")], default=0)
            new_case_ids = new_item.get("source_case_ids", [])
            max_new_id = max([int(cid.replace("TC", "")) for cid in new_case_ids if cid.startswith("TC")], default=0)
            
            if max_new_id > max_existing_id:
                # 新用例ID更大，标记旧知识为变更
                existing_item["status"] = "changed"
                existing_item["old_content"] = existing_item["content"]
                existing_item["change_reason"] = f"用例 {', '.join(new_case_ids)} 更新"
                merged_items.append(existing_item)
                
                # 添加新知识
                merged_items.append(new_item)
            else:
                # 旧用例ID更大，保留旧知识
                merged_items.append(existing_item)
        else:
            # 新知识，直接添加
            merged_items.append(new_item)
    
    # 保留未被新知识点匹配的旧知识点
    for key, item in existing_index.items():
        if key not in matched_existing_keys:
            merged_items.append(item)
    
    return merged_items


def _apply_knowledge_changes(kb_id: str, items: List[Dict[str, Any]], changed_case_ids: List[str] = None) -> None:
    """
    应用知识变更到数据库（先删除旧知识点再批量插入，避免重复记录）
    
    Args:
        kb_id: 知识库 ID
        items: 知识点列表
        changed_case_ids: 变更的用例 ID 列表，用于更新内容哈希
    """
    # 先删除该知识库下所有旧知识点
    delete_knowledge_items_by_kb(kb_id)
    
    # 计算最新的用例内容哈希并更新
    if changed_case_ids:
        new_hashes = _calculate_case_hashes(changed_case_ids)
        # 合并已有哈希：读取旧的，用新的覆盖
        kb = get_knowledge_base(kb_id)
        stored_hashes = _parse_stored_hashes(kb.get("case_content_hashes", "{}"))
        stored_hashes.update(new_hashes)
        update_knowledge_base(
            kb_id,
            case_content_hashes=json.dumps(stored_hashes, ensure_ascii=False),
            updated_at=get_db()._now()
        )
    else:
        update_knowledge_base(kb_id, updated_at=get_db()._now())
    
    # 批量创建知识点
    batch_items = []
    for item in items:
        batch_items.append({
            "item_id": f"{kb_id}_{item['module'][:10]}_{hash(item['content'])}",
            "kb_id": kb_id,
            "module": item.get("module", ""),
            "item_type": item.get("item_type", ""),
            "content": item.get("content", ""),
            "priority": item.get("priority", ""),
            "source_case_ids": json.dumps(item.get("source_case_ids", []), ensure_ascii=False),
            "status": item.get("status", "active"),
            "old_content": item.get("old_content", ""),
            "change_reason": item.get("change_reason", "")
        })
    
    create_knowledge_items_batch(batch_items)


def get_db():
    """获取数据库实例"""
    from storage.db import get_db as _get_db
    return _get_db()


async def submit_knowledge_task(task_id: str, case_ids: list) -> Dict[str, Any]:
    """
    提交知识提取任务
    
    如果用例已经提取过且没有变更，跳过提取流程，直接返回已有知识库。
    如果部分用例有变更，只对变更用例走提取流程，再增量合并。
    相同 categoryName 的用例归纳到同一个知识库。
    
    Args:
        task_id: 任务 ID
        case_ids: 用例 ID 列表
        
    Returns:
        任务信息（包含是否跳过、已有知识库 ID 等）
    """
    import asyncio
    
    # 先获取 categoryName（取第一个用例的即可，同批用例 categoryName 相同）
    category_name = _fetch_category_name(case_ids[0]) if case_ids else ""
    
    # 优先按 categoryName 查找已有知识库
    existing_kb = None
    if category_name:
        existing_kb = find_knowledge_base_by_title(category_name)
    
    # 回退到按用例 ID 查找
    if not existing_kb:
        existing_kb = find_knowledge_base_by_cases(case_ids)
    
    if existing_kb:
        # 检测变更的用例
        changed_cases = detect_changed_cases(existing_kb, case_ids)
        
        if not changed_cases:
            # 所有用例都没有变更，直接返回已有知识库
            logger.info(f"用例 {case_ids} 已提取且无变更，跳过提取流程，复用知识库 {existing_kb['id']}")
            create_task(task_id, json.dumps({"case_ids": case_ids}, ensure_ascii=False), task_type="knowledge")
            update_task(task_id, status="success", result=json.dumps({
                "knowledge_base_id": existing_kb["id"],
                "skipped": True,
                "reason": "用例无变更，复用已有知识库"
            }, ensure_ascii=False))
            return {
                "task_id": task_id,
                "skipped": True,
                "knowledge_base_id": existing_kb["id"],
                "reason": "用例无变更，复用已有知识库"
            }
        
        # 有变更用例，走增量更新流程
        logger.info(f"用例 {case_ids} 中有 {len(changed_cases)} 个变更，走增量更新: {changed_cases}")
        create_task(task_id, json.dumps({"case_ids": case_ids, "changed_cases": changed_cases}, ensure_ascii=False), task_type="knowledge")
        update_task(task_id, status="running")
        asyncio.create_task(_run_incremental_task(task_id, case_ids, existing_kb["id"], changed_cases))
        return {
            "task_id": task_id,
            "skipped": False,
            "mode": "incremental",
            "changed_cases": changed_cases,
            "knowledge_base_id": existing_kb["id"]
        }
    
    # 全新用例，走完整提取流程
    task_content = json.dumps({"case_ids": case_ids}, ensure_ascii=False)
    create_task(task_id, task_content, task_type="knowledge")
    update_task(task_id, status="running")
    
    # 异步执行任务
    asyncio.create_task(_run_knowledge_task(task_id, case_ids))
    logger.info(f"知识提取任务已提交: {task_id}")
    return {
        "task_id": task_id,
        "skipped": False,
        "mode": "full"
    }


async def _run_knowledge_task(task_id: str, case_ids: list) -> None:
    """
    执行知识提取任务（全量）
    
    Args:
        task_id: 任务 ID
        case_ids: 用例 ID 列表
    """
    try:
        exec_result = await knowledgeexecution(task_id, case_ids, isapi=True)
        
        # 解析结果并持久化到知识库
        kb_id = f"kb_{task_id[:8]}"
        if isinstance(exec_result, dict):
            result = exec_result.get("result", "")
            category_name = exec_result.get("category_name", "")
        else:
            result = exec_result
            category_name = ""
        _persist_knowledge_result(kb_id, task_id, result, case_ids, category_name=category_name)
        
        update_task(task_id, status="success", result=json.dumps({"knowledge_base_id": kb_id}, ensure_ascii=False))
        logger.info(f"知识提取任务完成: {task_id}")
        
    except Exception as e:
        update_task(task_id, status="failed")
        logger.error(f"知识提取任务失败: {task_id}, 错误: {e}")


async def _run_incremental_task(task_id: str, case_ids: list, kb_id: str, changed_case_ids: List[str]) -> None:
    """
    执行增量更新任务（只对变更用例走提取流程）
    
    Args:
        task_id: 任务 ID
        case_ids: 全部用例 ID 列表
        kb_id: 已有知识库 ID
        changed_case_ids: 变更的用例 ID 列表
    """
    try:
        # 只对变更用例执行知识提取
        exec_result = await knowledgeexecution(task_id, changed_case_ids, isapi=True)
        if isinstance(exec_result, dict):
            result = exec_result.get("result", "")
        else:
            result = exec_result
        
        # 增量合并到已有知识库
        kb = get_knowledge_base(kb_id)
        existing_items = get_knowledge_items(kb_id)
        
        # 从提取结果中获取新知识点
        new_items = _extract_items_from_result(result)
        
        if new_items:
            # 合并新旧知识点
            merged_items = _merge_knowledge_items(existing_items, new_items, changed_case_ids)
            # 应用变更
            _apply_knowledge_changes(kb_id, merged_items, changed_case_ids)
        
        # 更新 source_case_ids（加入新增的用例）
        stored_ids = json.loads(kb.get("source_case_ids", "[]"))
        updated_ids = list(set(stored_ids) | set(case_ids))
        update_knowledge_base(kb_id, source_case_ids=json.dumps(updated_ids, ensure_ascii=False))
        
        update_task(task_id, status="success", result=json.dumps({
            "knowledge_base_id": kb_id,
            "mode": "incremental",
            "changed_cases": changed_case_ids
        }, ensure_ascii=False))
        logger.info(f"增量更新任务完成: {task_id}, 变更用例: {changed_case_ids}")
        
    except Exception as e:
        update_task(task_id, status="failed")
        logger.error(f"增量更新任务失败: {task_id}, 错误: {e}")


def _extract_items_from_result(result: Any) -> List[Dict[str, Any]]:
    """
    从知识提取结果中提取知识点列表
    
    Args:
        result: 提取结果
        
    Returns:
        知识点列表
    """
    if isinstance(result, dict):
        items = result.get("items", [])
        if items:
            return items
        # 如果 result 本身就是列表格式
        for key in ("module_knowledge", "deduped_items", "resolved_items"):
            data = result.get(key, [])
            if isinstance(data, list) and data:
                return data
    elif isinstance(result, list):
        return result
    elif isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed.get("items", [])
            elif isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


def _persist_knowledge_result(kb_id: str, task_id: str, result: Any, case_ids: list, category_name: str = "") -> None:
    """
    持久化知识提取结果
    
    Args:
        kb_id: 知识库 ID
        task_id: 任务 ID
        result: 提取结果（mixed 格式节点输出 dict 或字符串）
        case_ids: 用例 ID 列表
        category_name: 分类名称（来自 getCaseJson 的 categoryName 字段）
    """
    modules = []
    items = []
    markdown_content = ""
    
    # 结果可能是 dict（mixed 格式节点输出 dict 或字符串）
    if isinstance(result, dict):
        # mixed 格式节点已经解析为 dict
        modules = result.get("modules", [])
        items = result.get("items", [])
        changes = result.get("changes", [])
        # 尝试从 context 获取 markdown 部分
        markdown_content = str(result)
        logger.info(f"知识库持久化: result 是 dict, items 数量: {len(items)}, items 前2条: {items[:2] if items else '空'}")
    else:
        # 字符串格式，尝试解析
        result_str = str(result) if result else ""
        markdown_content = result_str
        
        try:
            if "---" in result_str:
                parts = result_str.split("---")
                for part in parts:
                    part = part.strip()
                    if part.startswith("{") or part.startswith("["):
                        data = json.loads(part)
                        if isinstance(data, dict) and "modules" in data:
                            modules = data.get("modules", [])
                        if isinstance(data, dict) and "items" in data:
                            items = data.get("items", [])
        except Exception as e:
            logger.warning(f"解析结果 JSON 失败: {e}")
    
    # 计算并存储用例内容哈希（用于后续变更检测）
    case_content_hashes = _calculate_case_hashes(case_ids)
    
    # 使用 categoryName 作为标题
    kb_title = category_name if category_name else f"需求知识点 ({len(case_ids)}个用例)"
    
    # 创建知识库主记录
    create_knowledge_base(
        kb_id,
        task_id=task_id,
        title=kb_title,
        markdown_content=markdown_content,
        modules_json=json.dumps(modules, ensure_ascii=False),
        source_case_ids=json.dumps(case_ids, ensure_ascii=False),
        case_content_hashes=json.dumps(case_content_hashes, ensure_ascii=False)
    )
    
    # 写入知识点明细到 knowledge_items 表
    if items:
        # 中文→英文字段映射（LLM 可能返回中文 key）
        key_map = {
            "模块编号": "module_id",
            "模块名称": "module",
            "子模块说明": "content",
            "用例数": "case_count",
            "优先级": "priority",
            "测试点": "content",
            "名称": "content",
            "用例名称": "content",
            "描述": "content",
            "关键验证": "content",
            "验证点": "content",
            "类型": "item_type",
            "状态": "status",
            "来源用例": "source_case_ids",
            "来源": "source_case_ids",
            "变更原因": "change_reason",
            "旧内容": "old_content",
            "前置条件": "precondition",
            "步骤": "steps",
            "预期结果": "expected",
        }
        
        def _get_field(item: dict, field: str, default: str = "") -> str:
            """优先取英文 key，回退到中文 key 映射"""
            if field in item:
                return item[field]
            for cn_key, en_key in key_map.items():
                if en_key == field and cn_key in item:
                    return item[cn_key]
            return default
        
        batch_items = []
        for idx, item in enumerate(items):
            content = _get_field(item, "content")
            module = _get_field(item, "module")
            if idx == 0:
                logger.info(f"知识库持久化: 第1条 item 原始 keys={list(item.keys())}, module={module}, content={content[:50] if content else '空'}")
            # 使用 uuid 保证唯一性
            item_id = f"{kb_id}_{uuid.uuid4().hex[:12]}"
            batch_items.append({
                "item_id": item_id,
                "kb_id": kb_id,
                "module": module,
                "item_type": _get_field(item, "item_type"),
                "content": content,
                "priority": _get_field(item, "priority"),
                "source_case_ids": json.dumps(item.get("source_case_ids", item.get("来源用例", [])), ensure_ascii=False),
                "status": _get_field(item, "status", "active"),
                "old_content": _get_field(item, "old_content"),
                "change_reason": _get_field(item, "change_reason")
            })
        create_knowledge_items_batch(batch_items)
        # 更新知识点数量
        update_knowledge_base(kb_id, item_count=len(batch_items))
        logger.info(f"知识库持久化完成: {kb_id}, 知识点数量: {len(batch_items)}")
    else:
        logger.warning(f"知识库持久化完成: {kb_id}, 但未提取到知识点明细")


def _calculate_case_hashes(case_ids: list) -> Dict[str, str]:
    """
    计算用例内容哈希映射
    
    Args:
        case_ids: 用例 ID 列表
        
    Returns:
        用例ID到内容哈希的字典
    """
    hashes = {}
    for case_id in case_ids:
        case_info = _fetch_case_info(case_id)
        hashes[case_id] = case_info.get("content_hash", "")
    return hashes


async def get_knowledge_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    查询知识提取任务状态
    
    Args:
        task_id: 任务 ID
        
    Returns:
        任务状态信息
    """
    try:
        task = get_task(task_id)
        return task
    except Exception:
        return None


async def get_knowledge_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """
    获取知识提取任务结果
    
    Args:
        task_id: 任务 ID
        
    Returns:
        提取结果
    """
    try:
        task = get_task(task_id)
        if task.get("status") != "success":
            return None
        result_str = task.get("result", "{}")
        try:
            return json.loads(result_str)
        except Exception:
            return {"knowledge_base_id": result_str}
    except Exception:
        return None
