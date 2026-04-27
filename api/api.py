import json

from fastapi import FastAPI
import uuid
import asyncio

from core.taskexecution import taskexecution
from storage.db import get_task, insert_log, update_task, create_task, init_db

app = FastAPI()

init_db()


@app.post("/run")
async def run_task(payload: dict):
    task_id = str(uuid.uuid4())
    task = payload["task"]

    create_task(task_id, task)

    # 异步执行
    asyncio.create_task(execute(task_id, task))

    return {"task_id": task_id}


async def execute(task_id, task):
    try:
        update_task(task_id, status="running")

        result = await taskexecution(task=task,task_id=task_id,isapi=True)

        update_task(task_id, result=result)

    except Exception as e:
        update_task(task_id, status="failed")
        insert_log(task_id, "SYSTEM", str(e))


@app.get("/task/{task_id}")
def get_status(task_id: str):
    row = get_task(task_id)
    if not row:
        return {"error": "not found"}

    return {
        "id": row[0],
        "task": row[1],
        "status": row[2],
        "created_at": row[4],
        "updated_at": row[5],
    }


@app.get("/result/{task_id}")
def get_result(task_id: str):
    row = get_task(task_id)
    if not row:
        return {"error": "not found"}

    return {
        "result": row[3] and json.loads(row[3])
    }