# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
import uuid

from dotenv import load_dotenv

load_dotenv()

from core.taskexecution import taskexecution


def main():
    parser = argparse.ArgumentParser(description="AITestCraft CLI - 生成测试用例")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--task", "-t", type=str, help="需求文本内容")
    input_group.add_argument("--doc-url", "-u", type=str, help="文档链接（飞书/TAPD/语雀/石墨/Confluence）")
    args = parser.parse_args()

    task_id = str(uuid.uuid4())

    if args.doc_url:
        from utils.parsers import parse_doc_url
        task = asyncio.run(parse_doc_url(args.doc_url))
    elif args.task:
        task = args.task
    else:
        parser.print_help()
        return

    result = asyncio.run(taskexecution(task=task, task_id=task_id, isapi=False))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()