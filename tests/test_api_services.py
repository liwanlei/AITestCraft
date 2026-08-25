#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch, AsyncMock

from fastapi import HTTPException

from api.services.content_resolver import resolve_file_content, resolve_doc_content
from api.services.knowledge_service import CaseContentHashIndex


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


class TestCaseContentHashIndex(unittest.TestCase):
    """CaseContentHashIndex 单元测试"""

    def test_init_empty(self):
        """默认空 JSON 字符串初始化"""
        idx = CaseContentHashIndex("{}")
        self.assertEqual(idx.to_json(), "{}")

    def test_init_with_hashes(self):
        """带有效哈希的 JSON 字符串初始化"""
        idx = CaseContentHashIndex('{"TC001": "hash1", "TC002": "hash2"}')
        self.assertEqual(idx.get("TC001"), "hash1")
        self.assertEqual(idx.get("TC002"), "hash2")

    def test_init_invalid_json(self):
        """非法 JSON 字符串初始化，应降级为空字典"""
        idx = CaseContentHashIndex("not-json")
        self.assertEqual(idx.to_json(), "{}")

    def test_init_empty_string(self):
        """空字符串初始化"""
        idx = CaseContentHashIndex("")
        self.assertEqual(idx.to_json(), "{}")

    def test_get_existing(self):
        """获取存在的哈希"""
        idx = CaseContentHashIndex('{"TC001": "abc123"}')
        self.assertEqual(idx.get("TC001"), "abc123")

    def test_get_missing(self):
        """获取不存在的哈希，返回默认值"""
        idx = CaseContentHashIndex('{"TC001": "abc123"}')
        self.assertEqual(idx.get("TC999"), "")
        self.assertEqual(idx.get("TC999", "default"), "default")

    def test_update_overwrites_existing(self):
        """update 覆盖已有哈希"""
        idx = CaseContentHashIndex('{"TC001": "old_hash"}')
        idx.update({"TC001": "new_hash", "TC002": "hash2"})
        self.assertEqual(idx.get("TC001"), "new_hash")
        self.assertEqual(idx.get("TC002"), "hash2")

    def test_to_json_roundtrip(self):
        """to_json 后重新构造应一致"""
        original = '{"TC001": "hash1", "TC002": "hash2"}'
        idx = CaseContentHashIndex(original)
        idx.update({"TC003": "hash3"})
        new_idx = CaseContentHashIndex(idx.to_json())
        self.assertEqual(new_idx.get("TC001"), "hash1")
        self.assertEqual(new_idx.get("TC003"), "hash3")

    def test_detect_changes_no_change(self):
        """无变更时返回空列表"""
        idx = CaseContentHashIndex('{"TC001": "hash1", "TC002": "hash2"}')
        current = {"TC001": "hash1", "TC002": "hash2"}
        self.assertEqual(idx.detect_changes(current), [])

    def test_detect_changes_all_new(self):
        """全部是新用例，应全部返回"""
        idx = CaseContentHashIndex("{}")
        current = {"TC001": "hash1", "TC002": "hash2"}
        self.assertCountEqual(idx.detect_changes(current), ["TC001", "TC002"])

    def test_detect_changes_partial(self):
        """部分用例哈希变更"""
        idx = CaseContentHashIndex('{"TC001": "hash1", "TC002": "hash2", "TC003": "hash3"}')
        current = {"TC001": "hash1", "TC002": "changed_hash", "TC003": "hash3"}
        self.assertEqual(idx.detect_changes(current), ["TC002"])

    def test_detect_changes_empty_current(self):
        """当前哈希为空字典"""
        idx = CaseContentHashIndex('{"TC001": "hash1"}')
        self.assertEqual(idx.detect_changes({}), [])

    def test_detect_changes_new_case_added(self):
        """当前哈希新增了用例"""
        idx = CaseContentHashIndex('{"TC001": "hash1"}')
        current = {"TC001": "hash1", "TC002": "hash2"}
        self.assertEqual(idx.detect_changes(current), ["TC002"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
