# -*- coding: utf-8 -*-
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.schemas import MultiFormatResult, XMindFormats
from formatters import MarkdownFormatter, XMindFormatter, KityMinderFormatter
from utils.json_utils import parse_markdown_table
from utils.logger import logger

RESULT_DIR = Path("result")
RESULT_DIR.mkdir(parents=True, exist_ok=True)

_markdown_formatter = MarkdownFormatter()
_xmind_formatter = XMindFormatter()
_kityminder_formatter = KityMinderFormatter()


def _parse_result_data(raw_result: Optional[str]) -> Tuple[List[Dict[str, Any]], int]:
    if raw_result is None:
        return [], 0

    try:
        result_data = json.loads(raw_result)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"结果数据 JSON 解析失败: {e}, 数据长度: {len(raw_result)}")
        return [], 0

    if isinstance(result_data, list):
        return result_data, 0
    elif isinstance(result_data, dict):
        return result_data.get("testcases", []), result_data.get("coverage", 0)
    elif isinstance(result_data, str):
        if result_data.strip().startswith("|"):
            testcases = parse_markdown_table(result_data)
            logger.info(f"将 Markdown 表格转换为 JSON，共 {len(testcases)} 条用例")
            return testcases, 0
        return [], 0
    else:
        return [], 0


def _save_atomic(target_path: Path, content: Any, mode: str = "w") -> Optional[Path]:
    try:
        suffix = target_path.suffix
        dir_path = target_path.parent
        open_kwargs: Dict[str, Any] = {"dir": dir_path, "suffix": suffix, "delete": False}
        if "b" not in mode:
            open_kwargs["encoding"] = "utf-8"
        with tempfile.NamedTemporaryFile(mode, **open_kwargs) as tf:
            if "b" in mode:
                tf.write(content)
            elif isinstance(content, (dict, list)):
                json.dump(content, tf, ensure_ascii=False, indent=2)
            else:
                tf.write(content)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_path = Path(tf.name)

        os.replace(str(tmp_path), str(target_path))
        logger.info(f"文件已保存: {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"保存文件失败 ({target_path.suffix}): {e}")
        return None


def build_result(task: Dict[str, Any]) -> Dict[str, Any]:
    task_id = task.get("id", "")
    task_status = task.get("status", "")

    if task_status in ("running",):
        return {"result": None, "message": "任务执行中", "status": "running"}
    if task_status in ("pending",):
        return {"result": None, "message": "任务等待执行", "status": "pending"}
    if task_status in ("failed",):
        return {"result": None, "message": "任务执行失败", "status": "failed"}

    testcases, coverage = _parse_result_data(task.get("result"))
    if not testcases and task.get("result") is None:
        return {"result": None, "message": "任务无结果", "status": task_status}

    metadata: Dict[str, Any] = {
        "title": "测试用例文档",
        "requirement": task.get("task", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(testcases),
        "coverage": coverage
    }

    # 格式化
    try:
        markdown_content = _markdown_formatter.format(testcases, metadata)
    except Exception as e:
        logger.error(f"Markdown 格式化失败: {e}")
        markdown_content = ""

    try:
        xmind_8_bytes = _xmind_formatter.format_8(testcases, metadata)
    except Exception as e:
        logger.error(f"XMind 8 格式化失败: {e}")
        xmind_8_bytes = b""

    try:
        xmind_2023_bytes = _xmind_formatter.format_2023(testcases, metadata)
    except Exception as e:
        logger.error(f"XMind 2023 格式化失败: {e}")
        xmind_2023_bytes = b""

    try:
        kityminder_data = _kityminder_formatter.format(testcases, metadata)
    except Exception as e:
        logger.error(f"KityMinder 格式化失败: {e}")
        kityminder_data = {}

    # 原子保存文件（仅保存非空内容）
    json_path = _save_atomic(RESULT_DIR / f"{task_id}.json", testcases, "w") if testcases else None
    md_path = _save_atomic(RESULT_DIR / f"{task_id}.md", markdown_content, "w") if markdown_content else None
    xmind_8_path = _save_atomic(RESULT_DIR / f"{task_id}_xmind8.xmind", xmind_8_bytes, "wb") if xmind_8_bytes else None
    xmind_2023_path = _save_atomic(RESULT_DIR / f"{task_id}_xmind2023.xmind", xmind_2023_bytes, "wb") if xmind_2023_bytes else None
    km_path = _save_atomic(RESULT_DIR / f"{task_id}.km", kityminder_data, "w") if kityminder_data else None

    # 构建响应
    xmind_formats = XMindFormats(
        xmind_8=_xmind_formatter.encode_base64(xmind_8_bytes),
        xmind_2023=_xmind_formatter.encode_base64(xmind_2023_bytes),
        xmind_8_filename=f"{task_id}_xmind8.xmind",
        xmind_2023_filename=f"{task_id}_xmind2023.xmind"
    )

    multi_format_result = MultiFormatResult(
        json=testcases,
        markdown=markdown_content,
        xmind=xmind_formats,
        kityminder=kityminder_data
    )

    logger.info(f"返回多格式结果，Markdown: {len(markdown_content)} 字符，XMind: {len(xmind_8_bytes)} 字节")
    return {
        "result": multi_format_result,
        "files": {
            "json": str(json_path) if json_path else None,
            "markdown": str(md_path) if md_path else None,
            "xmind_8": str(xmind_8_path) if xmind_8_path else None,
            "xmind_2023": str(xmind_2023_path) if xmind_2023_path else None,
            "kityminder": str(km_path) if km_path else None
        }
    }