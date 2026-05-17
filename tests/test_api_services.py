#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 服务模块单元测试"""
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from fastapi import Request, HTTPException
from starlette.testclient import TestClient

from api.services.content_resolver import resolve_file_content, resolve_doc_content
from api.services.task_service import process_task
from api.main import app
from config.config import Config


class TestContentResolver(unittest.TestCase):
    """内容解析服务测试"""

    @patch("api.services.content_resolver.MDFileParser")
    async def test_resolve_file_content_md(self, mock_parser):
        """测试解析 Markdown 文件"""
        mock_file = Mock()
        mock_file.filename = "test.md"
        mock_file.file.read.return_value = b"# Test\nContent"

        mock_parser_instance = Mock()
        mock_parser_instance.parse.return_value = "解析后的内容"
        mock_parser.return_value = mock_parser_instance

        result = await resolve_file_content(mock_file)
        self.assertEqual(result, "解析后的内容")

    @patch("api.services.content_resolver.TXTFileParser")
    async def test_resolve_file_content_txt(self, mock_parser):
        """测试解析文本文件"""
        mock_file = Mock()
        mock_file.filename = "test.txt"
        mock_file.file.read.return_value = b"test content"

        mock_parser_instance = Mock()
        mock_parser_instance.parse.return_value = "test content"
        mock_parser.return_value = mock_parser_instance

        result = await resolve_file_content(mock_file)
        self.assertEqual(result, "test content")

    @patch("api.services.content_resolver.PDFFileParser")
    async def test_resolve_file_content_pdf(self, mock_parser):
        """测试解析 PDF 文件"""
        mock_file = Mock()
        mock_file.filename = "test.pdf"
        mock_file.file.read.return_value = b"%PDF-1.4"

        mock_parser_instance = Mock()
        mock_parser_instance.parse.return_value = "PDF content"
        mock_parser.return_value = mock_parser_instance

        result = await resolve_file_content(mock_file)
        self.assertEqual(result, "PDF content")

    async def test_resolve_file_content_unsupported(self):
        """测试不支持的文件类型"""
        mock_file = Mock()
        mock_file.filename = "test.exe"

        with self.assertRaises(HTTPException) as context:
            await resolve_file_content(mock_file)
        self.assertEqual(context.exception.status_code, 400)

    @patch("api.services.content_resolver.feishu_parser")
    async def test_resolve_doc_content_feishu(self, mock_parser):
        """测试解析飞书文档"""
        mock_parser.parse.return_value = "飞书文档内容"
        result = await resolve_doc_content("https://www.feishu.cn/docx/test")
        self.assertEqual(result, "飞书文档内容")

    @patch("api.services.content_resolver.tapd_parser")
    async def test_resolve_doc_content_tapd(self, mock_parser):
        """测试解析 TAPD 文档"""
        mock_parser.parse.return_value = "TAPD 文档内容"
        result = await resolve_doc_content("https://www.tapd.cn/xxx/stories/view/123")
        self.assertEqual(result, "TAPD 文档内容")

    async def test_resolve_doc_content_unsupported(self):
        """测试不支持的文档链接"""
        with self.assertRaises(HTTPException) as context:
            await resolve_doc_content("https://example.com/unknown")
        self.assertEqual(context.exception.status_code, 501)


class TestTaskService(unittest.TestCase):
    """任务服务测试"""

    def setUp(self):
        self.client = TestClient(app)

    def test_process_task_normal(self):
        """测试正常处理任务"""
        mock_request = Mock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # 由于 process_task 是异步的且依赖数据库，我们测试基本的客户端调用
        response = self.client.post("/run", data={"task": "测试任务"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("task_id", response.json())

    def test_process_task_empty_content(self):
        """测试空内容任务"""
        response = self.client.post("/run", data={"task": ""})
        self.assertEqual(response.status_code, 422)

    def test_process_task_too_long(self):
        """测试超长内容任务"""
        long_content = "x" * (Config.API_MAX_TASK_LENGTH + 1)
        response = self.client.post("/run", data={"task": long_content})
        self.assertEqual(response.status_code, 413)

    def test_process_task_no_params(self):
        """测试无参数"""
        response = self.client.post("/run")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)