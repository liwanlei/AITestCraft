# -*- coding: utf-8 -*-
import base64
import json
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Any, Optional

from formatters.base import BaseFormatter


class XMindFormatter(BaseFormatter):
    @property
    def content_type(self) -> str:
        return "application/xmind"

    @property
    def file_extension(self) -> str:
        return "xmind"

    def format(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, version: str = "8") -> bytes:
        if version not in ["8", "2023"]:
            version = "8"

        meta = self._build_metadata(metadata)

        if version == "2023":
            return self._build_xmind_2023(testcases, meta)
        return self._build_xmind_8(testcases, meta)

    def format_8(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bytes:
        return self.format(testcases, metadata, "8")

    def format_2023(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bytes:
        return self.format(testcases, metadata, "2023")

    def _build_xmind_8(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bytes:
        content = self._build_content_json(testcases, metadata)
        metadata_json = self._build_metadata_json(metadata)

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
            zf.writestr("metadata.json", json.dumps(metadata_json, ensure_ascii=False, indent=2))
            zf.writestr("META-INF/manifest.xml", self._build_manifest())

        zip_buffer.seek(0)
        return zip_buffer.read()

    def _build_xmind_2023(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bytes:
        content = self._build_content_json(testcases, metadata)
        metadata_json = self._build_metadata_json(metadata, version="2023")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
            zf.writestr("metadata.json", json.dumps(metadata_json, ensure_ascii=False, indent=2))
            zf.writestr("META-INF/manifest.xml", self._build_manifest_2023())
            zf.writestr("thumbnail/thumbnail.png", self._build_empty_thumbnail())

        zip_buffer.seek(0)
        return zip_buffer.read()

    def _build_content_json(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        root_id = str(uuid.uuid4())
        topic_id = str(uuid.uuid4())

        priority_groups = self._group_by_priority(testcases)

        children = []
        for priority in ["P0", "P1", "P2"]:
            if priority not in priority_groups:
                continue
            cases = priority_groups[priority]
            priority_node = self._build_priority_node(priority, cases)
            children.append(priority_node)

        summary_node = self._build_summary_node(testcases, metadata)
        children.append(summary_node)

        return {
            "id": topic_id,
            "title": metadata.get("title", "测试用例文档"),
            "metadata": {
                "generator": "AITestCraft",
                "created": datetime.now().isoformat() + "Z",
                "modified": datetime.now().isoformat() + "Z"
            },
            "rootTopic": {
                "id": root_id,
                "title": metadata.get("requirement", "测试用例"),
                "children": {
                    "attached": children
                }
            }
        }

    def _build_priority_node(self, priority: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        priority_id = str(uuid.uuid4())
        case_nodes = []

        for case in cases:
            case_node = self._build_case_node(case)
            case_nodes.append(case_node)

        return {
            "id": priority_id,
            "title": f"{priority} 优先级",
            "children": {
                "attached": case_nodes
            }
        }

    def _build_case_node(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = str(uuid.uuid4())
        case_title = f"{case.get('id', '')}: {case.get('name', '')}"

        attached = [
            {"id": str(uuid.uuid4()), "title": f"优先级: {case.get('priority', '')}"},
            {"id": str(uuid.uuid4()), "title": f"前置条件: {case.get('precondition', '')}"}
        ]

        steps = case.get("steps", [])
        if isinstance(steps, list) and steps:
            steps_node = {"id": str(uuid.uuid4()), "title": "测试步骤"}
            step_items = []
            for i, step in enumerate(steps):
                step_items.append({"id": str(uuid.uuid4()), "title": f"{i+1}. {step}"})
            steps_node["children"] = {"attached": step_items}
            attached.append(steps_node)

        assert_list = case.get("assert", [])
        if isinstance(assert_list, list) and assert_list:
            assert_node = {"id": str(uuid.uuid4()), "title": "预期结果"}
            assert_items = []
            for i, item in enumerate(assert_list):
                assert_items.append({"id": str(uuid.uuid4()), "title": f"{i+1}. {item}"})
            assert_node["children"] = {"attached": assert_items}
            attached.append(assert_node)

        return {
            "id": case_id,
            "title": case_title,
            "children": {
                "attached": attached
            }
        }

    def _build_summary_node(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        summary_id = str(uuid.uuid4())
        priority_counts = {}

        for case in testcases:
            priority = case.get("priority", "P2")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        attached = [
            {"id": str(uuid.uuid4()), "title": f"总计用例: {len(testcases)}"}
        ]

        for priority in ["P0", "P1", "P2"]:
            if priority in priority_counts:
                attached.append({"id": str(uuid.uuid4()), "title": f"{priority}: {priority_counts[priority]}"})

        if metadata.get("coverage"):
            attached.append({"id": str(uuid.uuid4()), "title": f"覆盖率: {metadata['coverage']}"})

        return {
            "id": summary_id,
            "title": "统计信息",
            "children": {
                "attached": attached
            }
        }

    def _build_metadata_json(self, metadata: Dict[str, Any], version: str = "8") -> Dict[str, Any]:
        if version == "2023":
            return {
                "creator": {
                    "name": "AITestCraft",
                    "version": "1.0.0"
                },
                "created": datetime.now().isoformat() + "Z",
                "modified": datetime.now().isoformat() + "Z",
                "sheet": {
                    "id": str(uuid.uuid4()),
                    "title": metadata.get("requirement", "测试用例")
                }
            }
        return {
            "creator": {
                "name": "AITestCraft",
                "version": "1.0.0"
            },
            "created": datetime.now().isoformat() + "Z",
            "modified": datetime.now().isoformat() + "Z"
        }

    def _build_manifest(self) -> str:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <file-entry full-path="content.json" media-type="application/json"/>
  <file-entry full-path="metadata.json" media-type="application/json"/>
  <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
</manifest>'''

    def _build_manifest_2023(self) -> str:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <file-entry full-path="content.json" media-type="application/json"/>
  <file-entry full-path="metadata.json" media-type="application/json"/>
  <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
  <file-entry full-path="thumbnail/thumbnail.png" media-type="image/png"/>
</manifest>'''

    def _build_empty_thumbnail(self) -> bytes:
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

    def _group_by_priority(self, testcases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for case in testcases:
            priority = case.get("priority", "P2")
            if priority not in groups:
                groups[priority] = []
            groups[priority].append(case)
        return groups

    def encode_base64(self, xmind_bytes: bytes) -> str:
        return base64.b64encode(xmind_bytes).decode("utf-8")
