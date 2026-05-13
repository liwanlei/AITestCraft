# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Dict, List, Tuple

# 避免循环导入，在文件末尾导入 logger


def _get_env_list(name: str, default: str, delimiter: str = ",") -> List[str]:
    """从环境变量获取列表"""
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(delimiter) if item.strip()]


def _get_env_bool(name: str, default: bool) -> bool:
    """从环境变量获取布尔值"""
    value = os.getenv(name, str(default)).strip().lower()
    return value in ("true", "1", "yes")


def _get_env_int(name: str, default: int) -> int:
    """从环境变量获取整数"""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        from utils.logger import logger
        logger.warning(f"环境变量 {name} 不是有效整数，使用默认值 {default}")
        return default


def _get_env_str(name: str, default: str) -> str:
    """从环境变量获取字符串"""
    return os.getenv(name, default)


class Config:
    # 路径配置
    BASE_DIR: Path = Path(__file__).parent.parent
    SKILLS_DIR: Path = BASE_DIR / "skills"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DB_PATH: str = str(BASE_DIR / "workflow.db")

    # 服务配置
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = _get_env_int("SERVER_PORT", 8001)

    # 重试配置
    NODE_MAX_RETRY: int = 3
    RETRY_MAX_RETRIES: int = 3
    MODEL_SETTINGS: Dict = {"seed": 40, "top": 1, "temperature": 0}

    # Agent 超时配置（秒）
    AGENT_TIMEOUT_SECONDS: int = _get_env_int("AGENT_TIMEOUT_SECONDS", 120)

    # 过滤配置
    REQUIREMENT_FILTER_KEYS: Tuple[str, ...] = ("rules", "edge_cases", "exceptions", "inputs", "actions", "outputs", "actors")
    TESTPOINT_FILTER_KEYS: Tuple[str, ...] = ("test_point", "priority")

    # 日志配置（支持环境变量）
    LOG_TASK_MAX_LENGTH: int = 200
    LOG_RESULT_MAX_LENGTH: int = _get_env_int("LOG_RESULT_MAX_LENGTH", 5000)
    LOG_DEBUG_MAX_LENGTH: int = _get_env_int("LOG_DEBUG_MAX_LENGTH", 200)
    LOG_ERROR_MAX_LENGTH: int = _get_env_int("LOG_ERROR_MAX_LENGTH", 500)
    LOG_TASK_ID_LENGTH: int = _get_env_int("LOG_TASK_ID_LENGTH", 8)
    LOG_FILE_NAME: str = _get_env_str("LOG_FILE_NAME", "AITestCraft.log")
    LOG_LEVEL: str = _get_env_str("LOG_LEVEL", "INFO").upper()
    LOG_CONSOLE_LEVEL: str = _get_env_str("LOG_CONSOLE_LEVEL", "INFO").upper()
    LOG_FILE_LEVEL: str = _get_env_str("LOG_FILE_LEVEL", "DEBUG").upper()

    # 技能配置
    SKILL_NAMES: Dict[str, str] = {
        "requirement": "requirement-parser",
        "testpoint": "testpoint-extractor",
        "dedup": "testpoint-deduplicator",
        "testcase": "testcase-generator",
        "review": "testcase-reviewer",
        "coverage": "testcase-coverage",
        "gap": "gap-filler",
    }

    # CORS 配置（支持环境变量）
    CORS_ORIGINS: List[str] = _get_env_list("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")
    CORS_ALLOW_CREDENTIALS: bool = _get_env_bool("CORS_ALLOW_CREDENTIALS", True)
    CORS_ALLOW_METHODS: List[str] = _get_env_list("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS")
    CORS_ALLOW_HEADERS: List[str] = _get_env_list("CORS_ALLOW_HEADERS", "Content-Type,Authorization")

    # API 限流配置（支持环境变量）
    API_MAX_TASK_LENGTH: int = 10000
    API_RATE_LIMIT_PER_MINUTE: int = _get_env_int("API_RATE_LIMIT_PER_MINUTE", 5)
    API_RATE_LIMIT_WINDOW_SECONDS: int = _get_env_int("API_RATE_LIMIT_WINDOW_SECONDS", 60)

    # 文件上传配置（支持环境变量）
    MAX_FILE_SIZE: int = _get_env_int("MAX_FILE_SIZE", 10 * 1024 * 1024)  # 10MB
    ALLOWED_FILE_TYPES: List[str] = ["md", "markdown", "txt"]

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> None:
        """验证配置有效性"""
        from utils.logger import logger
        
        errors = []

        # 端口验证
        if cls.SERVER_PORT < 1 or cls.SERVER_PORT > 65535:
            errors.append(f"SERVER_PORT 必须在 1-65535 范围内，当前值: {cls.SERVER_PORT}")

        # 限流配置验证
        if cls.API_RATE_LIMIT_PER_MINUTE <= 0:
            errors.append(f"API_RATE_LIMIT_PER_MINUTE 必须大于 0，当前值: {cls.API_RATE_LIMIT_PER_MINUTE}")

        if cls.API_RATE_LIMIT_WINDOW_SECONDS <= 0:
            errors.append(f"API_RATE_LIMIT_WINDOW_SECONDS 必须大于 0，当前值: {cls.API_RATE_LIMIT_WINDOW_SECONDS}")

        # 任务长度验证
        if cls.API_MAX_TASK_LENGTH <= 0:
            errors.append(f"API_MAX_TASK_LENGTH 必须大于 0，当前值: {cls.API_MAX_TASK_LENGTH}")

        # 重试配置验证
        if cls.NODE_MAX_RETRY < 0:
            errors.append(f"NODE_MAX_RETRY 不能为负数，当前值: {cls.NODE_MAX_RETRY}")

        if cls.RETRY_MAX_RETRIES < 0:
            errors.append(f"RETRY_MAX_RETRIES 不能为负数，当前值: {cls.RETRY_MAX_RETRIES}")

        if cls.AGENT_TIMEOUT_SECONDS <= 0:
            errors.append(f"AGENT_TIMEOUT_SECONDS 必须大于 0，当前值: {cls.AGENT_TIMEOUT_SECONDS}")

        # CORS 配置验证
        if not cls.CORS_ORIGINS:
            errors.append("CORS_ORIGINS 不能为空")

        # 日志级别验证
        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR")
        if cls.LOG_LEVEL not in valid_log_levels:
            errors.append(f"LOG_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_LEVEL}")
        if cls.LOG_CONSOLE_LEVEL not in valid_log_levels:
            errors.append(f"LOG_CONSOLE_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_CONSOLE_LEVEL}")
        if cls.LOG_FILE_LEVEL not in valid_log_levels:
            errors.append(f"LOG_FILE_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_FILE_LEVEL}")

        # 日志长度验证
        if cls.LOG_RESULT_MAX_LENGTH <= 0:
            errors.append(f"LOG_RESULT_MAX_LENGTH 必须大于 0，当前值: {cls.LOG_RESULT_MAX_LENGTH}")
        if cls.LOG_DEBUG_MAX_LENGTH <= 0:
            errors.append(f"LOG_DEBUG_MAX_LENGTH 必须大于 0，当前值: {cls.LOG_DEBUG_MAX_LENGTH}")
        if cls.LOG_ERROR_MAX_LENGTH <= 0:
            errors.append(f"LOG_ERROR_MAX_LENGTH 必须大于 0，当前值: {cls.LOG_ERROR_MAX_LENGTH}")

        # 输出验证结果
        if errors:
            logger.error("配置验证失败:")
            for error in errors:
                logger.error(f"  - {error}")
            raise ValueError("配置验证失败，请检查环境变量和配置文件")

        logger.info("配置验证通过")


# 初始化目录并验证配置
Config.ensure_dirs()

# 导入 logger 并验证配置（放在最后避免循环导入）
from utils.logger import logger
Config.validate()
