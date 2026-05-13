# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.config import Config
from storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AITestCraft API",
    description="基于AI的测试用例生成和管理系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_ALLOW_CREDENTIALS,
    allow_methods=Config.CORS_ALLOW_METHODS,
    allow_headers=Config.CORS_ALLOW_HEADERS,
)

# 导入并注册路由
from api.endpoints.tasks import router as tasks_router
from api.endpoints.rate_limit import router as rate_limit_router

app.include_router(tasks_router, tags=["tasks"])
app.include_router(rate_limit_router, tags=["rate-limit"])
