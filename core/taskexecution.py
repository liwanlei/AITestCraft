import os.path

from agent_framework import SkillsProvider
from fastapi import Path

from agents.base import build_agents
from core.context import Context, TokenStats
from core.workflow import build_workflow
from utils.logger import logger
base_path = os.path.join(os.getcwd(),"skills")
providers = {
    "requirement": SkillsProvider(os.path.join(base_path,"requirement-parser")),
    "testpoint": SkillsProvider(os.path.join(base_path, "testpoint-extractor")),
    "dedup": SkillsProvider(os.path.join(base_path, "testpoint-deduplicator")),
    "testcase": SkillsProvider(os.path.join(base_path,"testcase-generator")),
    "review": SkillsProvider(os.path.join(base_path,"testcase-reviewer")),
    "coverage": SkillsProvider(os.path.join(base_path,"testcase-coverage")),
    "gap": SkillsProvider(os.path.join(base_path,"gap-filler")),
}

async def taskexecution(task_id,task,isapi=False):
    agents = build_agents(providers)
    wf = build_workflow(agents)
    ctx = Context()
    ctx.set("task", task)
    ctx.set("token_stats", TokenStats())
    ctx.set("task_id",task_id)
    ctx.set("isapi",isapi)
    result = await wf.run("requirement", ctx)
    stats = ctx["token_stats"].report()

    logger.info(f"Token usage: {stats}")
    # 输出最终结果
    if "final_cases" in result:
        logger.info(result["final_cases"])
        return result["final_cases"]
    else:
        logger.info(result["testcase"])
        return result["testcase"]