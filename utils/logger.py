import logging
import sys
from pathlib import Path


def setup_logger():
    logger = logging.getLogger("AITestCraft")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    logger.addHandler(console)
    log_dir = Path("logs")  # 当前目录下 logs 文件夹
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "AITestCraft.log"
    # 文件日志
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


logger = setup_logger()