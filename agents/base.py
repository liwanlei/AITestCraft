from agent_framework import Agent

from config.config import BASE_PROMPT
from agent_framework.openai import OpenAIChatClient

def build_agent(provider):
    client = OpenAIChatClient()
    return Agent(
        client=client,
        name="TestAgent",
        instructions=BASE_PROMPT,
        context_providers=[provider],
    )
def build_agents(providers):
    return {k: build_agent(v) for k, v in providers.items()}
