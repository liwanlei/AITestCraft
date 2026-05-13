# -*- coding: utf-8 -*-
import json
from typing import Any, Callable, Dict, Optional, TypedDict

from config.config import Config
from utils.exceptions import NodeExecutionError, SchemaValidationError
from core.context import Context
from storage.db import insert_log
from utils.json_utils import safe_loads, validate_schema
from utils.logger import logger
from core.retry import run_with_retry


class LogEvent(TypedDict):
    event: str
    detail: str


class Node:
    def __init__(
            self,
            name: str,
            agent: Any,
            input_fn: Callable[[Context], str],
            output_key: str,
            condition: Optional[Callable[[Context], bool]] = None,
            schema: Optional[Dict] = None,
            max_retry: int = Config.NODE_MAX_RETRY,
            timeout: Optional[int] = Config.AGENT_TIMEOUT_SECONDS
    ):
        self.name = name
        self.agent = agent
        self.input_fn = input_fn
        self.output_key = output_key
        self.condition = condition
        self.schema = schema
        self.max_retry = max_retry
        self.timeout = timeout

    def _log(self, task_id: str, event: str, detail: str = "") -> None:
        if not task_id:
            return
        log_data: LogEvent = {"event": event, "detail": detail}
        insert_log(task_id, self.name, json.dumps(log_data, ensure_ascii=False))

    def _log_result(self, task_id: str, raw_result: str) -> None:
        max_length = Config.LOG_RESULT_MAX_LENGTH
        truncated = raw_result[:max_length] + ("..." if len(raw_result) > max_length else "")
        self._log(task_id, "result", truncated)

    async def run(self, ctx: Context) -> Context:
        task_id = ctx.get("task_id", "")

        if self.condition and not self.condition(ctx):
            logger.info(f"节点 [{self.name}] 跳过")
            self._log(task_id, "skip", "condition not met")
            return ctx

        payload = self.input_fn(ctx)
        self._log(task_id, "start", f"payload_size={len(payload)}")

        try:
            result = await run_with_retry(self.agent, 
            payload, retries=self.max_retry, 
            timeout=self.timeout)
        except Exception as e:
            error_msg = f"节点 [{self.name}] 多次重试仍失败: {e}"
            logger.error(error_msg)
            self._log(task_id, "failed", str(e))
            raise NodeExecutionError(error_msg) from e

        raw = result.text
        self._log_result(task_id, raw)
        logger.debug(f"节点 [{self.name}] 原始响应: {raw}")

        usage = getattr(result, "usage", None) or getattr(result, "model_usage", None)
        if usage:
            ctx["token_stats"].add(self.name, usage)

        try:
            parsed = safe_loads(raw)
        except Exception as e:
            error_msg = f"节点 [{self.name}] JSON解析失败: {e}"
            logger.error(error_msg)
            self._log(task_id, "parse_error", str(e))
            raise NodeExecutionError(error_msg) from e

        if self.schema:
            try:
                validate_schema(parsed, self.schema)
            except SchemaValidationError as e:
                error_msg = f"节点 [{self.name}] Schema校验失败: {e}"
                logger.error(error_msg)
                self._log(task_id, "schema_error", str(e))
                raise

        token_info = json.dumps(ctx["token_stats"].nodes.get(self.name, {}), ensure_ascii=False) if usage else ""
        self._log(task_id, "complete", token_info)
        
        logger.info(f"节点 [{self.name}] 成功")
        
        result_preview = json.dumps(parsed, ensure_ascii=False)
        logger.debug(f"节点 [{self.name}] 输出数据:\n{result_preview}")
        
        ctx.set(self.output_key, parsed)
        return ctx
