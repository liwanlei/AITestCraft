# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
import uuid

from dotenv import load_dotenv

load_dotenv()

from core.taskexecution import taskexecution


def main():
    # parser = argparse.ArgumentParser(description="AITestCraft CLI - 生成测试用例")
    # parser.add_argument("--task", "-t", type=str, help="需求文本内容")
    # parser.add_argument("--doc-url", "-u", type=str, help="文档链接（飞书/TAPD/语雀/石墨/Confluence）")
    # args = parser.parse_args()
    #
    # if args.doc_url:
    #     from utils.parsers import parse_doc_url
    #     task = asyncio.run(parse_doc_url(args.doc_url))
    # elif args.task:
    #     task = args.task
    # else:
    #     parser.print_help()
    #     return

    task_id = str(uuid.uuid4())
    task = '''登录：手机号 + 短信验证码。
        - 验证码：6位数字；有效期5分钟；同手机号发送间隔≥60s；日上限10次（示例）。
        - 手机号：大陆11位），支持带/不带空格与`+86`。
        - 账号态：新用户自动注册/引导注册；黑名单/冻结不可登录，服务端控制黑名单列表。
        - 多端：App/小程序/H5支持。新用户自动注册并登录。只支持手机号验证码登录，
        - 手机号规则只包含国内，验证码错误会提示验证码错误，有效期五分钟从生成时间算
        - 60s间隔和每日10次限额是固定的
        '''
    result = asyncio.run(taskexecution(task=task, task_id=task_id, isapi=False))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
