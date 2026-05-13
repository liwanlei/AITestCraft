# -*- coding: utf-8 -*-
from typing import Dict, Optional

from agent_framework import Agent, SkillsProvider
from agent_framework.openai import OpenAIChatClient

from agents.prompts import BASE_PROMPT

_client: Optional[OpenAIChatClient] = None


def _get_client() -> OpenAIChatClient:
    global _client
    if _client is None:
        _client = OpenAIChatClient()
    return _client


def build_agent(provider: SkillsProvider) -> Agent:
    return Agent(
        client=_get_client(),
        name="TestAgent",
        instructions=BASE_PROMPT,
        context_providers=[provider],
    )


def build_agents(providers: Dict[str, SkillsProvider]) -> Dict[str, Agent]:
    return {k: build_agent(v) for k, v in providers.items()}