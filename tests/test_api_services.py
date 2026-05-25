#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch, AsyncMock

from fastapi import HTTPException

from api.services.content_resolver import resolve_file_content, resolve_doc_content


class TestResolveFileContent(unittest.TestCase):

    @patch("api.services.content_resolver._parse_markdown")
    def test_resolve_file_content_md(self, mock_parse):
        mock_parse.return_value = "解析后的内容"
        mock_file = Mock()
        mock_file.filename = "test.md"
        mock_file.read = AsyncMock(side_effect=[b"# Test\nContent", b""])

        import asyncio
        result = asyncio.run(resolve_file_content(mock_file))
        self.assertEqual(result, "解析后的内容")

    @patch("api.services.content_resolver._parse_text")
    def test_resolve_file_content_txt(self, mock_parse):
        mock_parse.return_value = "test content"
        mock_file = Mock()
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(side_effect=[b"test content", b""])

        import asyncio
        result = asyncio.run(resolve_file_content(mock_file))
        self.assertEqual(result, "test content")

    @patch("api.services.content_resolver._parse_pdf", new_callable=AsyncMock)
    def test_resolve_file_content_pdf(self, mock_parse):
        mock_parse.return_value = "PDF content"
        mock_file = Mock()
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(side_effect=[b"%PDF-1.4", b""])

        import asyncio
        result = asyncio.run(resolve_file_content(mock_file))
        self.assertEqual(result, "PDF content")

    def test_resolve_file_content_unsupported(self):
        mock_file = Mock()
        mock_file.filename = "test.exe"
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        import asyncio
        with self.assertRaises(HTTPException) as context:
            asyncio.run(resolve_file_content(mock_file))
        self.assertEqual(context.exception.status_code, 400)


class TestResolveDocContent(unittest.TestCase):

    @patch("api.services.content_resolver.parse_doc_url", new_callable=AsyncMock)
    @patch("api.services.content_resolver.check_doc_support")
    def test_resolve_doc_content_feishu(self, mock_check, mock_parse):
        mock_parse.return_value = "飞书文档内容"
        import asyncio
        result = asyncio.run(resolve_doc_content("https://www.feishu.cn/docx/test"))
        self.assertEqual(result, "飞书文档内容")

    @patch("api.services.content_resolver.check_doc_support")
    def test_resolve_doc_content_unsupported(self, mock_check):
        mock_check.side_effect = ValueError("不支持的文档链接")
        import asyncio
        with self.assertRaises(HTTPException) as context:
            asyncio.run(resolve_doc_content("https://example.com/unknown"))
        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
