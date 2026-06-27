# -*- coding: utf-8 -*-
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.config import Config
from storage.db import init_db
from utils.parsers._http import close_shared_session


class UnicodeJSONResponse(JSONResponse):
    """支持中文直接输出的 JSON 响应"""
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Config.validate()
    init_db()
    
    # 启动时恢复中断的任务
    if Config.TASK_RECOVERY_ENABLED:
        from api.recovery import recover_interrupted_tasks
        await recover_interrupted_tasks()
    
    yield
    from storage.db import get_db
    get_db().close_all_connections()
    close_shared_session()


app = FastAPI(
    title="AITestCraft API",
    description="基于AI的测试用例生成和管理系统",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=UnicodeJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_ALLOW_CREDENTIALS,
    allow_methods=Config.CORS_ALLOW_METHODS,
    allow_headers=Config.CORS_ALLOW_HEADERS,
)

from api.endpoints.tasks import router as tasks_router
from api.endpoints.knowledge import router as knowledge_router

app.include_router(tasks_router, tags=["tasks"])
app.include_router(knowledge_router, tags=["knowledge"])


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
