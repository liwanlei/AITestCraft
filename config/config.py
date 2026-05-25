# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Dict, List

from utils.logger import logger


def _get_env_list(name: str, default: str, delimiter: str = ",") -> List[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(delimiter) if item.strip()]


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in ("true", "1", "yes")


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning(f"环境变量 {name} 不是有效整数，使用默认值 {default}")
        return default


def _get_env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.ensure_dirs()

    BASE_DIR: Path = Path(__file__).parent.parent
    SKILLS_DIR: Path = BASE_DIR / "skills"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DB_PATH: str = str(BASE_DIR / "workflow.db")

    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = _get_env_int("SERVER_PORT", 8001)

    RETRY_MAX_RETRIES: int = _get_env_int("RETRY_MAX_RETRIES", 3)
    NODE_MAX_RETRY = RETRY_MAX_RETRIES

    MODEL_SETTINGS: Dict = {"seed": 40, "top_p": 1, "temperature": 0}

    NODE_MODEL_SETTINGS: Dict[str, Dict] = {
        "review": {
            "model_id": _get_env_str("REVIEW_MODEL_ID", "gpt-4o"),
            "settings": {"seed": 40, "top_p": 1, "temperature": 0.1}
        },
        "coverage": {
            "model_id": _get_env_str("COVERAGE_MODEL_ID", "gpt-4o-mini"),
            "settings": {"seed": 40, "top_p": 1, "temperature": 0.2}
        }
    }

    AGENT_TIMEOUT_SECONDS: int = _get_env_int("AGENT_TIMEOUT_SECONDS", 1000)

    MODULE_SPLIT_THRESHOLD: int = _get_env_int("MODULE_SPLIT_THRESHOLD", 3)

    LOG_TASK_ID_LENGTH: int = _get_env_int("LOG_TASK_ID_LENGTH", 8)
    LOG_LEVEL: str = _get_env_str("LOG_LEVEL", "INFO").upper()
    LOG_CONSOLE_LEVEL: str = _get_env_str("LOG_CONSOLE_LEVEL", "INFO").upper()
    LOG_FILE_LEVEL: str = _get_env_str("LOG_FILE_LEVEL", "DEBUG").upper()

    SKILL_NAMES: Dict[str, str] = {
        "requirement": "requirement-parser",
        "testpoint": "testpoint-extractor",
        "testcase": "testcase-generator",
        "review": "testcase-reviewer",
        "coverage": "testcase-coverage",
        "gap": "gap-filler",
        "aggregator": "module-aggregator",
    }

    CORS_ORIGINS: List[str] = _get_env_list("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")
    CORS_ALLOW_CREDENTIALS: bool = _get_env_bool("CORS_ALLOW_CREDENTIALS", True)
    CORS_ALLOW_METHODS: List[str] = _get_env_list("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS")
    CORS_ALLOW_HEADERS: List[str] = _get_env_list("CORS_ALLOW_HEADERS", "Content-Type,Authorization")

    MAX_FILE_SIZE: int = _get_env_int("MAX_FILE_SIZE", 10 * 1024 * 1024)
    ALLOWED_FILE_TYPES: List[str] = ["md", "markdown", "txt", "pdf"]

    # 任务恢复配置
    TASK_RECOVERY_ENABLED: bool = _get_env_bool("TASK_RECOVERY_ENABLED", True)
    TASK_RECOVERY_INTERVAL: float = _get_env_int("TASK_RECOVERY_INTERVAL", 500) / 1000  # 转换为秒
    TASK_RECOVERY_MAX_COUNT: int = _get_env_int("TASK_RECOVERY_MAX_COUNT", 10)

    PDF_TEXT_THRESHOLD: int = 50
    PDF_VISION_MODEL_ID: str = _get_env_str("PDF_VISION_MODEL_ID", "gpt-4o")
    PDF_MAX_PAGES: int = _get_env_int("PDF_MAX_PAGES", 50)

    FEISHU_USER_ACCESS_TOKEN: str = _get_env_str("FEISHU_USER_ACCESS_TOKEN", "")

    TAPD_API_USER: str = _get_env_str("TAPD_API_USER", "")
    TAPD_API_PASSWORD: str = _get_env_str("TAPD_API_PASSWORD", "")

    YUQUE_API_TOKEN: str = _get_env_str("YUQUE_API_TOKEN", "")

    SHIMO_CLIENT_ID: str = _get_env_str("SHIMO_CLIENT_ID", "")
    SHIMO_CLIENT_SECRET: str = _get_env_str("SHIMO_CLIENT_SECRET", "")
    SHIMO_API_TOKEN: str = _get_env_str("SHIMO_API_TOKEN", "")

    CONFLUENCE_BASE_URL: str = _get_env_str("CONFLUENCE_BASE_URL", "")
    CONFLUENCE_EMAIL: str = _get_env_str("CONFLUENCE_EMAIL", "")
    CONFLUENCE_API_TOKEN: str = _get_env_str("CONFLUENCE_API_TOKEN", "")

    SENSITIVE_KEYS = frozenset([
        "FEISHU_USER_ACCESS_TOKEN", "TAPD_API_PASSWORD", "TAPD_API_USER",
        "YUQUE_API_TOKEN", "SHIMO_CLIENT_SECRET", "SHIMO_API_TOKEN",
        "CONFLUENCE_API_TOKEN", "CONFLUENCE_EMAIL",
    ])

    def ensure_dirs(self) -> None:
        cls = self if isinstance(self, type) else self.__class__
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        errors = []
        cls = self if isinstance(self, type) else self.__class__

        if cls.SERVER_PORT < 1 or cls.SERVER_PORT > 65535:
            errors.append(f"SERVER_PORT 必须在 1-65535 范围内，当前值: {cls.SERVER_PORT}")

        if cls.RETRY_MAX_RETRIES < 0:
            errors.append(f"RETRY_MAX_RETRIES 不能为负数，当前值: {cls.RETRY_MAX_RETRIES}")

        if cls.AGENT_TIMEOUT_SECONDS <= 0:
            errors.append(f"AGENT_TIMEOUT_SECONDS 必须大于 0，当前值: {cls.AGENT_TIMEOUT_SECONDS}")

        if not cls.CORS_ORIGINS:
            errors.append("CORS_ORIGINS 不能为空")

        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR")
        if cls.LOG_LEVEL not in valid_log_levels:
            errors.append(f"LOG_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_LEVEL}")
        if cls.LOG_CONSOLE_LEVEL not in valid_log_levels:
            errors.append(f"LOG_CONSOLE_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_CONSOLE_LEVEL}")
        if cls.LOG_FILE_LEVEL not in valid_log_levels:
            errors.append(f"LOG_FILE_LEVEL 必须是 {valid_log_levels} 之一，当前值: {cls.LOG_FILE_LEVEL}")

        if errors:
            logger.error("配置验证失败:")
            for error in errors:
                logger.error(f"  - {error}")
            raise ValueError("配置验证失败，请检查环境变量和配置文件")

        logger.info("配置验证通过")

    def safe_repr(self) -> Dict:
        result = {}
        cls = self if isinstance(self, type) else self.__class__
        for key in dir(cls):
            if key.startswith("_") or key in ("SENSITIVE_KEYS", "ensure_dirs", "validate", "safe_repr"):
                continue
            value = getattr(cls, key)
            if callable(value):
                continue
            if key in self.SENSITIVE_KEYS:
                result[key] = "***" if value else ""
            else:
                result[key] = value
        return result


Config.ensure_dirs = classmethod(Config.ensure_dirs)
Config.validate = classmethod(Config.validate)
Config.safe_repr = classmethod(Config.safe_repr)

_config_singleton = Config()
