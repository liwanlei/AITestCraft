# -*- coding: utf-8 -*-
import json
import random
import string
from datetime import datetime
from typing import List, Dict, Any, Optional

from formatters.base import BaseFormatter


class KityMinderFormatter(BaseFormatter):
    @property
    def content_type(self) -> str:
        return "application/json"

    @property
    def file_extension(self) -> str:
        return "km"

    def format(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not testcases:
            return self._format_empty(metadata)

        meta = self._build_metadata(metadata)
        now_ms = int(datetime.now().timestamp() * 1000)

        root_text = meta.get("requirement") or "测试用例"
        root_node = {
            "data": {
                "id": self._gen_id(),
                "created": now_ms,
                "text": root_text
            },
            "children": []
        }

        module_groups = self._group_by_module(testcases)

        if module_groups and len(module_groups) > 1:
            for module_name, cases in module_groups.items():
                module_node = self._build_module_node(module_name, cases, now_ms)
                root_node["children"].append(module_node)
        else:
            for case in testcases:
                case_node = self._build_case_node(case, now_ms)
                root_node["children"].append(case_node)

        return {
            "root": root_node,
            "template": "default",
            "theme": "fresh-blue",
            "version": "1.4.43",
            "base": 10,
            "right": 1
        }

    def format_string(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, indent: Optional[int] = None) -> str:
        return json.dumps(self.format(testcases, metadata), ensure_ascii=False, indent=indent)

    def _build_module_node(self, module_name: str, cases: List[Dict[str, Any]], now_ms: int) -> Dict[str, Any]:
        return {
            "data": {
                "id": self._gen_id(),
                "created": now_ms,
                "text": f"{module_name} ({len(cases)}条)"
            },
            "children": [self._build_case_node(case, now_ms) for case in cases]
        }

    def _build_case_node(self, case: Dict[str, Any], now_ms: int) -> Dict[str, Any]:
        priority = case.get("priority", "")
        case_id = case.get("id", "")
        name = case.get("name", "")

        if priority:
            title = f"[{priority}] {case_id}: {name}"
        else:
            title = f"{case_id}: {name}" if case_id else name

        chain_nodes: List[tuple] = []

        precondition = case.get("precondition", "")
        if precondition:
            chain_nodes.append(("前置条件", precondition))

        steps = case.get("steps", [])
        if isinstance(steps, list):
            for i, step in enumerate(steps):
                chain_nodes.append(("测试步骤", f"{i + 1}. {step}"))

        assert_list = case.get("assert", [])
        if not isinstance(assert_list, list):
            assert_list = []

        assert_nodes = []
        for i, item in enumerate(assert_list):
            assert_nodes.append(self._build_resource_node(f"{i + 1}. {item}", "预期结果", now_ms))

        if not chain_nodes:
            return {
                "data": {
                    "id": self._gen_id(),
                    "created": now_ms,
                    "text": title
                },
                "children": assert_nodes
            }

        current_children = assert_nodes

        for resource_type, text in reversed(chain_nodes):
            node = self._build_resource_node(text, resource_type, now_ms)
            node["children"] = current_children
            current_children = [node]

        return {
            "data": {
                "id": self._gen_id(),
                "created": now_ms,
                "text": title
            },
            "children": current_children
        }

    def _build_resource_node(self, text: str, resource_type: str, now_ms: int) -> Dict[str, Any]:
        return {
            "data": {
                "id": self._gen_id(),
                "created": now_ms,
                "text": text,
                "resource": [resource_type]
            },
            "children": []
        }

    def _format_empty(self, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        meta = self._build_metadata(metadata)
        now_ms = int(datetime.now().timestamp() * 1000)
        root_text = meta.get("requirement") or "测试用例"

        return {
            "root": {
                "data": {
                    "id": self._gen_id(),
                    "created": now_ms,
                    "text": root_text
                },
                "children": []
            },
            "template": "default",
            "theme": "fresh-blue",
            "version": "1.4.43",
            "base": 10,
            "right": 1
        }

    def _gen_id(self) -> str:
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=12))
if __name__ == "__main__":
    formatter = KityMinderFormatter()
    testcases = [{"id": "TC001", "name": "手机号登录-已注册正确格式手机号-登录成功", "priority": "P0", "precondition": "用户未登录，已注册手机号13800138000，密码正确", "steps": ["打开登录页面", "输入手机号13800138000", "输入正确密码", "点击登录按钮"], "assert": ["登录成功", "页面跳转至首页"]}, {"id": "TC002", "name": "手机号登录-已注册手机号-登录失败异常", "priority": "P0", "precondition": "用户未登录，已注册手机号13800138000，密码错误", "steps": ["打开登录页面", "输入手机号13800138000", "输入错误密码Abc123456", "点击登录按钮"], "assert": ["登录失败", "页面提示密码错误"]}, {"id": "TC003", "name": "手机号登录-登录成功-跳转首页", "priority": "P0", "precondition": "用户未登录，已注册手机号13800138001，密码正确", "steps": ["打开登录页面", "输入手机号13800138001", "输入正确密码", "点击登录按钮"], "assert": ["页面跳转至首页", "首页显示用户昵称"]}, {"id": "TC004", "name": "手机号登录-登录成功-跳转失败异常", "priority": "P0", "precondition": "用户未登录，已注册手机号13800138001，密码正确，首页服务异常", "steps": ["打开登录页面", "输入手机号13800138001", "输入正确密码", "点击登录按钮"], "assert": ["登录成功", "页面提示首页加载失败"]}, {"id": "TC005", "name": "手机号登录-登录成功-保持登录状态", "priority": "P1", "precondition": "用户已登录，手机号13800138002", "steps": ["打开登录页面", "输入手机号13800138002", "输入正确密码", "点击登录按钮", "关闭APP", "重新打开APP"], "assert": ["登录成功", "重新打开后仍保持登录状态", "无需重新登录"]}, {"id": "TC006", "name": "手机号登录-11位手机号-登录成功", "priority": "P0", "precondition": "用户未登录，已注册手机号13800138003（刚好11位）", "steps": ["打开登录页面", "输入手机号13800138003", "输入正确密码", "点击登录按钮"], "assert": ["登录成功", "页面跳转至首页"]}, {"id": "TC007", "name": "手机号登录-11位手机号-非注册号码异常", "priority": "P0", "precondition": "用户未登录，手机号13900139000（刚好11位但未注册）", "steps": ["打开登录页面", "输入手机号13900139000", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示账号不存在"]}, {"id": "TC008", "name": "手机号登录-少于11位手机号-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号1380013800（10位）", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC009", "name": "手机号登录-多于11位手机号-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号138001380001（12位）", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC010", "name": "手机号登录-手机号为空-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "不输入手机号", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号不能为空"]}, {"id": "TC011", "name": "手机号登录-含非数字字符-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号1380013800a", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC012", "name": "手机号登录-不以1开头-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号23800138000", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC013", "name": "手机号登录-未注册手机号-账号不存在", "priority": "P1", "precondition": "用户未登录，手机号13999999999未注册", "steps": ["打开登录页面", "输入手机号13999999999", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示账号不存在"]}, {"id": "TC014", "name": "手机号登录-网络异常-登录失败", "priority": "P2", "precondition": "用户未登录，已注册手机号13800138004，网络断开", "steps": ["打开登录页面", "输入手机号13800138004", "输入正确密码", "断开网络连接", "点击登录按钮"], "assert": ["登录失败", "页面提示网络连接异常"]}, {"id": "TC015", "name": "手机号登录-SQL注入攻击-输入过滤", "priority": "P2", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号13800138000' OR '1'='1", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误", "数据库无异常查询"]}, {"id": "TC016", "name": "手机号登录-手机号前含空格-格式处理", "priority": "P1", "precondition": "用户未登录，已注册手机号13800138000", "steps": ["打开登录页面", "输入手机号 13800138000（前面含空格）", "输入正确密码", "点击登录按钮"], "assert": ["登录成功或提示格式错误", "系统自动去除空格或提示格式错误"]}, {"id": "TC017", "name": "手机号登录-手机号后含空格-格式处理", "priority": "P1", "precondition": "用户未登录，已注册手机号13800138000", "steps": ["打开登录页面", "输入手机号13800138000 （后面含空格）", "输入正确密码", "点击登录按钮"], "assert": ["登录成功或提示格式错误", "系统自动去除空格或提示格式错误"]}, {"id": "TC018", "name": "手机号登录-账号被禁用-登录失败", "priority": "P1", "precondition": "用户未登录，手机号13800138005已注册但账号被禁用", "steps": ["打开登录页面", "输入手机号13800138005", "输入正确密码", "点击登录按钮"], "assert": ["登录失败", "页面提示账号已被禁用"]}, {"id": "TC019", "name": "手机号登录-账号被锁定-登录失败", "priority": "P1", "precondition": "用户未登录，手机号13800138006已注册但账号被锁定", "steps": ["打开登录页面", "输入手机号13800138006", "输入正确密码", "点击登录按钮"], "assert": ["登录失败", "页面提示账号已被锁定"]}, {"id": "TC020", "name": "手机号登录-连续5次密码错误-账号锁定", "priority": "P1", "precondition": "用户未登录，已注册手机号13800138007", "steps": ["打开登录页面", "输入手机号13800138007", "连续5次输入错误密码", "第6次输入正确密码"], "assert": ["前5次登录失败", "第6次登录失败或提示账号已锁定", "页面提示账号已锁定请联系客服"]}, {"id": "TC021", "name": "手机号登录-非法号段10开头-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号10800138000（10开头非法号段）", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC022", "name": "手机号登录-非法号段12开头-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号12800138000（12开头非法号段）", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC023", "name": "手机号登录-登录会话超时-需重新登录", "priority": "P2", "precondition": "用户已登录，会话已超时30分钟", "steps": ["打开APP", "尝试访问需要登录的页面", "系统检测会话超时"], "assert": ["页面跳转至登录页", "提示会话已过期请重新登录"]}, {"id": "TC024", "name": "手机号登录-密码过于简单-复杂度校验", "priority": "P2", "precondition": "用户未登录，已注册手机号13800138008，密码为123456", "steps": ["打开登录页面", "输入手机号13800138008", "输入密码123456", "点击登录按钮"], "assert": ["登录失败或成功但有警告", "页面提示密码强度过低建议修改"]}, {"id": "TC025", "name": "手机号登录-并发登录-多设备同时登录", "priority": "P2", "precondition": "用户未登录，已注册手机号13800138009，两个设备", "steps": ["设备A打开登录页面输入手机号13800138009和正确密码", "设备B同时打开登录页面输入手机号13800138009和正确密码", "两设备同时点击登录按钮"], "assert": ["至少一台设备登录成功", "另一台设备登录成功或提示已在其他设备登录", "系统正确处理并发请求"]}, {"id": "TC026", "name": "手机号登录-手机号含特殊符号-格式错误", "priority": "P1", "precondition": "用户未登录", "steps": ["打开登录页面", "输入手机号138-0013-8000（含横杠）", "输入任意密码", "点击登录按钮"], "assert": ["登录失败", "页面提示手机号格式错误"]}, {"id": "TC027", "name": "手机号登录-登录频率限制-防暴力破解", "priority": "P2", "precondition": "用户未登录，已注册手机号13800138010", "steps": ["打开登录页面", "1分钟内连续10次输入手机号13800138010和任意密码点击登录"], "assert": ["前几次登录失败", "后续请求被限制", "页面提示操作过于频繁请稍后再试"]}]
    print(formatter.format_string(testcases))