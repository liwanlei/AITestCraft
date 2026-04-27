from pathlib import Path

from agent_framework import SkillsProvider

BASE_PROMPT = """
你是测试设计引擎。

必须遵守：
1. 只输出JSON
2. 不允许解释
3. 不允许markdown
4. 字段必须完整
5. JSON必须可解析

否则视为失败
"""


