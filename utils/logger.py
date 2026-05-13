# -*- coding: utf-8 -*-
import logging
import sys

from config.config import Config


def setup_logger() -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger("AITestCraft")
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 日志级别映射
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR
    }
    
    # 设置根日志级别
    logger.setLevel(level_map.get(Config.LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    # 控制台日志
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level_map.get(Config.LOG_CONSOLE_LEVEL, logging.INFO))
    logger.addHandler(console)

    # 文件日志
    log_file = Config.LOGS_DIR / Config.LOG_FILE_NAME
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level_map.get(Config.LOG_FILE_LEVEL, logging.DEBUG))
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
