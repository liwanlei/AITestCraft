# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, List


class CaseParseError(Exception):
    """用例解析异常"""
    pass


def parse_case_tree(raw_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    解析第三方用例服务的树形结构，扁平化为标准用例格式
    
    Args:
        raw_data: 第三方 API 返回的原始数据
        
    Returns:
        标准化用例列表
        
    Raises:
        CaseParseError: 解析失败时抛出
    """
    if raw_data.get("code") != 200:
        raise CaseParseError(f"API 返回错误: {raw_data.get('msg', 'unknown')}")
    
    case_content = raw_data.get("data", {}).get("caseContent", {})
    root = case_content.get("root", {})
    
    if not root:
        raise CaseParseError("缺少 root 节点")
    
    module_name = root.get("data", {}).get("text", "未知模块")
    case_nodes = root.get("children", [])
    
    if not case_nodes:
        return []
    
    results = []
    for case_node in case_nodes:
        try:
            case = _parse_single_case(case_node, module_name)
            results.append(case)
        except Exception as e:
            # 单个用例解析失败不影响其他用例
            continue
    
    return results


def _parse_single_case(case_node: Dict[str, Any], module_name: str) -> Dict[str, str]:
    """
    解析单个用例节点
    
    Args:
        case_node: 用例节点数据
        module_name: 所属模块名
        
    Returns:
        标准化用例字典
    """
    case_data = case_node.get("data", {})
    title = case_data.get("text", "")
    
    # 解析标题: [P0] TC001: 验证码登录-登录成功
    match = re.match(r"\[(P[012])\]\s*(TC\d+):\s*(.+)", title)
    if not match:
        # 格式不匹配，使用默认值
        priority = "P1"
        case_id = f"UNKNOWN_{case_data.get('id', 'unknown')}"
        name = title
    else:
        priority = match.group(1)
        case_id = match.group(2)
        name = match.group(3)
    
    # 解析前置条件、步骤、预期结果
    steps = []
    assert_list = []
    precondition = ""
    
    children = case_node.get("children", [])
    result = _extract_case_parts(children)
    precondition = result["precondition"]
    steps = result["steps"]
    assert_list = result["assert"]
    
    return {
        "case_id": case_id,
        "module": module_name,
        "priority": priority,
        "name": name,
        "precondition": precondition,
        "steps": steps,
        "assert": assert_list
    }


def _extract_case_parts(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    递归提取用例各部分内容
    
    Args:
        nodes: 子节点列表
        
    Returns:
        包含 precondition, steps, assert_list 的字典
    """
    result = {
        "precondition": "",
        "steps": [],
        "assert": []
    }
    
    for node in nodes:
        data = node.get("data", {})
        resource = data.get("resource", [])
        text = data.get("text", "")
        
        if "前置条件" in resource:
            result["precondition"] = text
        elif "执行步骤" in resource:
            # 去掉步骤序号前缀
            step_text = re.sub(r"^\d+\.\s*", "", text)
            result["steps"].append(step_text)
        elif "预期结果" in resource:
            result["assert"].append(text)
        
        # 递归处理 children（链式步骤结构）
        children = node.get("children", [])
        if children:
            child_result = _extract_case_parts(children)
            # 合并结果
            if child_result["precondition"] and not result["precondition"]:
                result["precondition"] = child_result["precondition"]
            result["steps"].extend(child_result["steps"])
            result["assert"].extend(child_result["assert"])
    
    return result
