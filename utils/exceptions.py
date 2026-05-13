# -*- coding: utf-8 -*-
"""自定义异常模块"""


class AITestCraftError(Exception):
    """基础异常类"""
    pass


class WorkflowError(AITestCraftError):
    """工作流相关错误"""
    pass


class NodeExecutionError(WorkflowError):
    """节点执行错误"""
    pass


class SchemaValidationError(AITestCraftError):
    """Schema 验证错误"""
    pass


class JSONParseError(AITestCraftError):
    """JSON 解析错误"""
    pass


class DatabaseError(AITestCraftError):
    """数据库相关错误"""
    pass


class TaskNotFoundError(AITestCraftError):
    """任务未找到错误"""
    pass
