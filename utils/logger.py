# -*- coding: utf-8 -*-
import logging
import os
import sys
from pathlib import Path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("AITestCraft")

    if logger.handlers:
        return logger

    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    console_level = os.getenv("LOG_CONSOLE_LEVEL", "DEBUG").upper()
    file_level = os.getenv("LOG_FILE_LEVEL", "DEBUG").upper()
    log_file_name = os.getenv("LOG_FILE_NAME", "AITestCraft.log")

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR
    }

    logger.setLevel(level_map.get(log_level, logging.INFO))

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level_map.get(console_level, logging.INFO))
    logger.addHandler(console)

    base_dir = Path(__file__).parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / log_file_name

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level_map.get(file_level, logging.DEBUG))
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
