# =========================
# Node（执行单元）
# =========================
import asyncio

from core.context import Context
from storage.db import insert_log
from utils.json_utils import safe_loads, validate_schema
from utils.logger import logger
from utils.retry import run_with_retry


class Node:
    def __init__(
            self,
            name,
            agent,
            input_fn,
            output_key,
            condition=None,
            schema=None,
            max_retry=3
    ):
        self.name = name
        self.agent = agent
        self.input_fn = input_fn
        self.output_key = output_key
        self.condition = condition
        self.schema = schema
        self.max_retry = max_retry

    async def run(self, ctx: Context):
        task_id=""
        isapi=ctx.get("isapi")
        logger.info(isapi)
        if isapi:
            task_id = ctx.get("task_id")
        if self.condition and not self.condition(ctx):
            logger.info(f"{self.name} skipped")
            return ctx

        payload = self.input_fn(ctx)

        for i in range(self.max_retry):

            logger.info(f"{self.name} attempt {i + 1}")

            result = await run_with_retry(self.agent, payload)

            raw = result.text
            if isapi:
                insert_log(task_id, self.name, raw)
            logger.info(raw)
            # 1️⃣ JSON解析
            try:
                parsed = safe_loads(raw)
            except Exception as e:
                logger.info(e)
                logger.warning("JSON解析失败")
                logger.warning(f"JSON解析失败, 原始内容: {raw}")
                continue

            # 2️⃣ schema校验
            if self.schema:
                ok = validate_schema(parsed, self.schema)
                if not ok:
                    logger.warning(f"{self.name} schema失败 -> retry")
                    await asyncio.sleep(2 ** i)
                    continue

            # 3️⃣ 成功
            logger.info(f"{self.name} success")
            ctx.set(self.output_key, parsed)
            return ctx

        # 🚨 多次失败
        raise ValueError(f"{self.name} 多次重试仍失败")


