# -*- coding: utf-8 -*-
import base64
import json
import uuid
import zipfile
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
        content = self._build_content_json(testcases, meta)
        metadata_json = self._build_metadata_json()
        manifest_json = self._build_manifest_json()

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
            zf.writestr("metadata.json", json.dumps(metadata_json, ensure_ascii=False, indent=2))
            zf.writestr("manifest.json", json.dumps(manifest_json, ensure_ascii=False, indent=2))

        zip_buffer.seek(0)
        return zip_buffer.read()

    def format_8(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bytes:
        return self.format(testcases, metadata, "8")

    def format_2023(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bytes:
        return self.format(testcases, metadata, "2023")

    def _build_content_json(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        sheet_id = str(uuid.uuid4())
        root_id = str(uuid.uuid4())

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

        sheet = {
            "id": sheet_id,
            "class": "sheet",
            "title": metadata.get("title", "测试用例文档"),
            "rootTopic": {
                "id": root_id,
                "class": "topic",
                "title": metadata.get("requirement", "测试用例"),
                "structureClass": "org.xmind.ui.map.clockwise",
                "children": {
                    "attached": children
                }
            }
        }

        return [sheet]

    def _build_priority_node(self, priority: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        priority_id = str(uuid.uuid4())
        case_nodes = []

        for case in cases:
            case_node = self._build_case_node(case)
            case_nodes.append(case_node)

        return {
            "id": priority_id,
            "class": "topic",
            "title": f"{priority} 优先级",
            "children": {
                "attached": case_nodes
            }
        }

    def _build_case_node(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = str(uuid.uuid4())
        case_title = f"{case.get('id', '')}: {case.get('name', '')}"

        attached = [
            {"id": str(uuid.uuid4()), "class": "topic", "title": f"优先级: {case.get('priority', '')}"},
            {"id": str(uuid.uuid4()), "class": "topic", "title": f"前置条件: {case.get('precondition', '')}"}
        ]

        steps = case.get("steps", [])
        if isinstance(steps, list) and steps:
            steps_node = {"id": str(uuid.uuid4()), "class": "topic", "title": "测试步骤"}
            step_items = []
            for i, step in enumerate(steps):
                step_items.append({"id": str(uuid.uuid4()), "class": "topic", "title": f"{i+1}. {step}"})
            steps_node["children"] = {"attached": step_items}
            attached.append(steps_node)

        assert_list = case.get("assert", [])
        if isinstance(assert_list, list) and assert_list:
            assert_node = {"id": str(uuid.uuid4()), "class": "topic", "title": "预期结果"}
            assert_items = []
            for i, item in enumerate(assert_list):
                assert_items.append({"id": str(uuid.uuid4()), "class": "topic", "title": f"{i+1}. {item}"})
            assert_node["children"] = {"attached": assert_items}
            attached.append(assert_node)

        return {
            "id": case_id,
            "class": "topic",
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
            {"id": str(uuid.uuid4()), "class": "topic", "title": f"总计用例: {len(testcases)}"}
        ]

        for priority in ["P0", "P1", "P2"]:
            if priority in priority_counts:
                attached.append({"id": str(uuid.uuid4()), "class": "topic", "title": f"{priority}: {priority_counts[priority]}"})

        if metadata.get("coverage"):
            attached.append({"id": str(uuid.uuid4()), "class": "topic", "title": f"覆盖率: {metadata['coverage']}"})

        return {
            "id": summary_id,
            "class": "topic",
            "title": "统计信息",
            "children": {
                "attached": attached
            }
        }

    def _build_metadata_json(self) -> Dict[str, Any]:
        return {
            "dataStructureVersion": "2",
            "creator": {
                "name": "AITestCraft",
                "version": "1.0.0"
            },
            "layoutEngineVersion": "3"
        }

    def _build_manifest_json(self) -> Dict[str, Any]:
        return {
            "file-entries": {
                "content.json": {},
                "metadata.json": {},
                "manifest.json": {}
            }
        }

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
