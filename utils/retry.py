# =========================
# 2. Retry wrapper
# =========================
import asyncio

from utils.logger import logger


async def run_with_retry(agent, payload, retries=5):
    last_err = None
    for i in range(retries):
        try:
            return await agent. run(payload, model_settings={"seed": 40, "top": 1, "temperature": 0})
        except Exception as e:

            last_err = e
            wait = 2 ** i
            logger.warning(f"agent error: {e}, retry in {wait}s")
            await asyncio.sleep(wait)
    raise last_err
def should_trigger(diagnosis):
    return (
            diagnosis.get("risk_level") == "high"
            or len(diagnosis.get("issues", [])) > 0
            or len(diagnosis.get("missing", [])) > 0
    )
