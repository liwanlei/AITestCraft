# -*- coding: utf-8 -*-
import threading
from typing import Dict, Optional

from agent_framework import Agent, SkillsProvider
from agent_framework.openai import OpenAIChatClient

from agents.prompts import BASE_PROMPT

_client_cache: Dict[str, OpenAIChatClient] = {}
_cache_lock = threading.Lock()
_MAX_CACHE_SIZE = 32


def _get_client(model_id: Optional[str] = None) -> OpenAIChatClient:
    key = model_id or "__default__"
    with _cache_lock:
        if key not in _client_cache:
            if len(_client_cache) >= _MAX_CACHE_SIZE:
                oldest_key = next(iter(_client_cache))
                del _client_cache[oldest_key]
            _client_cache[key] = OpenAIChatClient(model_id=model_id) if model_id else OpenAIChatClient()
        return _client_cache[key]


def build_agent(provider: SkillsProvider, model_id: Optional[str] = None) -> Agent:
    client = _get_client(model_id)
    return Agent(
        client=client,
        name="TestAgent",
        instructions=BASE_PROMPT,
        context_providers=[provider],
    )


def build_agents(providers: Dict[str, SkillsProvider], model_configs: Optional[Dict[str, Dict]] = None) -> Dict[str, Agent]:
    agents = {}
    for k, v in providers.items():
        model_id = None
        if model_configs and k in model_configs:
            model_id = model_configs[k].get("model_id")
        agents[k] = build_agent(v, model_id)
    return agents
