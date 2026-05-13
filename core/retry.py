# -*- coding: utf-8 -*-
import asyncio
from typing import Any, Dict, Optional

from config.config import Config
from utils.logger import logger


async def run_with_retry(
    agent: Any,
    payload: str,
    retries: int = Config.RETRY_MAX_RETRIES,
    model_settings: Optional[Dict] = None,
    timeout: Optional[int] = None
) -> Any:
    if retries <= 0:
        raise ValueError("retries 必须大于 0")

    if model_settings is None:
        model_settings = Config.MODEL_SETTINGS.copy()

    if timeout is None:
        timeout = Config.AGENT_TIMEOUT_SECONDS

    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            if i > 0:
                logger.info(f"第 {i + 1} 次重试开始")
            return await asyncio.wait_for(
                agent.run(payload, model_settings=model_settings),
                timeout=timeout
            )
        except Exception as e:
            last_err = e
            wait = 2 ** i
            err_type = "超时" if isinstance(e, asyncio.TimeoutError) else "错误"
            err_detail = f" ({timeout}秒)" if isinstance(e, asyncio.TimeoutError) else ""
            logger.warning(f"Agent{err_type}{err_detail}: {e}, {wait}秒后重试 ({i + 1}/{retries})")
            if i == retries - 1:
                logger.error(f"重试 {retries} 次后仍失败，最后一次错误: {e}")
            await asyncio.sleep(wait)
    raise last_err


def should_trigger_gap_filler(diagnosis: Dict) -> bool:
    """判断是否需要执行缺口填充节点
    
    根据审查结果和覆盖率分析决定是否触发缺口填充：
    - 风险等级为高
    - 存在审查问题
    - 存在覆盖率缺失
    
    Args:
        diagnosis: 包含审查和覆盖率信息的字典
        
    Returns:
        是否需要执行缺口填充
    """
    return (
        diagnosis.get("risk_level") == "high"
        or len(diagnosis.get("issues", [])) > 0
        or len(diagnosis.get("missing", [])) > 0
    )
