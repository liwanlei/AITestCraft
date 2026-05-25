# -*- coding: utf-8 -*-
import json
from typing import Any, Callable, Dict, Optional

from config.config import Config
from utils.exceptions import NodeExecutionError, SchemaValidationError
from core.context import Context
from storage.repositories import insert_log, update_node_status
from utils.json_utils import safe_loads, validate_schema
from utils.logger import logger
from core.retry import run_with_retry
from utils.token_utils import extract_usage_info, extract_token_counts


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
            timeout: Optional[int] = Config.AGENT_TIMEOUT_SECONDS,
            model_settings: Optional[Dict] = None,
            output_format: str = "json"
    ):
        self.name = name
        self.agent = agent
        self.input_fn = input_fn
        self.output_key = output_key
        self.condition = condition
        self.schema = schema
        self.max_retry = max_retry
        self.timeout = timeout
        self.model_settings = model_settings or Config.MODEL_SETTINGS
        self.output_format = output_format

    def _log(self, task_id: str, event: str, detail: str = "", level: str = "INFO") -> None:
        if not task_id:
            return
        log_data = {"event": event, "detail": detail, "level": level}
        insert_log(task_id, self.name, json.dumps(log_data, ensure_ascii=False))

    def _log_result(self, task_id: str, raw_result: str) -> None:
        # 直接记录完整结果，不截断
        self._log(task_id, "result", raw_result)

    async def run(self, ctx: Context) -> Context:
        task_id = ctx.get("task_id", "")

        if self.condition and not self.condition(ctx):
            logger.info(f"节点 [{self.name}] 跳过")
            self._log(task_id, "skip", "condition not met", level="INFO")
            return ctx

        # 记录节点开始状态
        update_node_status(task_id, self.name, "running")

        # 注册节点到 token 统计（确保所有节点都出现在报告中）
        ctx["token_stats"].ensure_node(self.name)

        payload = self.input_fn(ctx)
        
        # 输入验证
        if not payload or not payload.strip():
            error_msg = f"节点 [{self.name}] 输入为空"
            logger.error(error_msg)
            self._log(task_id, "empty_input", "input payload is empty", level="ERROR")
            update_node_status(task_id, self.name, "failed", {"error": error_msg})
            raise NodeExecutionError(error_msg)
        
        self._log(task_id, "start", f"payload_size={len(payload)}", level="INFO")

        try:
            result = await run_with_retry(self.agent, 
            payload, retries=self.max_retry, 
            timeout=self.timeout,
            model_settings=self.model_settings)
        except Exception as e:
            error_msg = f"节点 [{self.name}] 多次重试仍失败: {e}"
            logger.error(error_msg)
            self._log(task_id, "failed", str(e), level="ERROR")
            update_node_status(task_id, self.name, "failed", {"error": error_msg})
            raise NodeExecutionError(error_msg) from e

        raw = result.text
        
        # 响应验证
        if raw is None:
            error_msg = f"节点 [{self.name}] 响应为 None"
            logger.error(error_msg)
            self._log(task_id, "null_response", "agent returned None", level="ERROR")
            update_node_status(task_id, self.name, "failed", {"error": error_msg})
            raise NodeExecutionError(error_msg)
        
        raw_str = str(raw).strip()
        
        self._log_result(task_id, raw_str)
        logger.debug(f"节点 [{self.name}] 原始响应长度: {len(raw_str)}")
        logger.info(f"节点 [{self.name}] 响应长度: {len(raw_str)} 字符")
        logger.debug(f"节点 [{self.name}] 原始响应前500字符:\n{raw_str[:500]}")
        usage_info = extract_usage_info(result)

        token_usage_data = None
        if usage_info:
            input_tokens, output_tokens = extract_token_counts(usage_info)

            if input_tokens > 0 or output_tokens > 0:
                token_usage_data = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens
                }
                ctx["token_stats"].add(self.name, {
                    "input_token_count": input_tokens,
                    "output_token_count": output_tokens,
                    "total_token_count": input_tokens + output_tokens
                })
                logger.info(f"节点 [{self.name}] Token统计: 输入={input_tokens}, 输出={output_tokens}")

        if self.output_format == "md":
            if not raw_str:
                # 对于 markdown 格式的节点，输出为空时设置默认值而不是失败
                logger.warning(f"节点 [{self.name}] 输出为空，使用默认值")
                default_output = "# 分析结果\n\n未生成分析内容"
                self._log(task_id, "empty_output", "using default output", level="WARNING")
                ctx.set(self.output_key, default_output)
                logger.info(f"节点 [{self.name}] 成功 (markdown，使用默认值)")
                self._log(task_id, "complete", "markdown output (default)", level="INFO")
                update_node_status(task_id, self.name, "completed", {"output": default_output}, token_usage=token_usage_data)
                return ctx
            ctx.set(self.output_key, raw_str)
            logger.info(f"节点 [{self.name}] 成功 (markdown)")
            self._log(task_id, "complete", "markdown output", level="INFO")
            update_node_status(task_id, self.name, "completed", {"output": raw_str}, token_usage=token_usage_data)
            return ctx

        # JSON 格式输出
        if not raw_str:
            error_msg = f"节点 [{self.name}] JSON输出为空"
            logger.error(error_msg)
            self._log(task_id, "empty_output", "JSON output is empty", level="ERROR")
            update_node_status(task_id, self.name, "failed", {"error": error_msg})
            raise NodeExecutionError(error_msg)

        try:
            parsed = safe_loads(raw_str)
        except Exception as e:
            error_msg = f"节点 [{self.name}] JSON解析失败: {e}"
            logger.error(error_msg)
            # 记录更多上下文信息
            context_info = f"原始响应长度: {len(raw_str)}, 前100字符: {raw_str[:100]}"
            self._log(task_id, "parse_error", f"{str(e)} | {context_info}", level="ERROR")
            update_node_status(task_id, self.name, "failed", {"error": error_msg, "context": context_info})
            raise NodeExecutionError(error_msg) from e

        if self.schema:
            try:
                parsed = validate_schema(parsed, self.schema)
            except SchemaValidationError as e:
                error_msg = f"节点 [{self.name}] Schema校验失败: {e}"
                logger.error(error_msg)
                self._log(task_id, "schema_error", str(e), level="ERROR")
                update_node_status(task_id, self.name, "failed", {"error": error_msg})
                raise

        token_info = json.dumps(ctx["token_stats"].get_node_usage(self.name) or {}, ensure_ascii=False) if token_usage_data else ""
        self._log(task_id, "complete", token_info, level="INFO")
        
        logger.info(f"节点 [{self.name}] 成功")
        
        result_preview = json.dumps(parsed, ensure_ascii=False)
        logger.debug(f"节点 [{self.name}] 输出数据:\n{result_preview}")
        
        ctx.set(self.output_key, parsed)
        update_node_status(task_id, self.name, "completed", {"output": parsed}, token_usage=token_usage_data)
        return ctx
