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
        content = self._build_content_json(testcases, meta, version)
        metadata_json = self._build_metadata_json(version)
        manifest_json = self._build_manifest_json(version)

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

    def _build_content_json(self, testcases: List[Dict[str, Any]], metadata: Dict[str, Any], version: str = "8") -> List[Dict[str, Any]]:
        sheet_id = str(uuid.uuid4())
        root_id = str(uuid.uuid4())

        module_groups = self._group_by_module(testcases)
        if module_groups and len(module_groups) > 1:
            children = []
            for module_name, cases in module_groups.items():
                module_node = self._build_module_node(module_name, cases)
                children.append(module_node)
        else:
            children = [self._build_case_node(case) for case in testcases]

        structure_class = "org.xmind.ui.map.clockwise" if version == "8" else "org.xmind.ui.logic.right"

        sheet = {
            "id": sheet_id,
            "class": "sheet",
            "title": metadata.get("title", "测试用例文档"),
            "rootTopic": {
                "id": root_id,
                "class": "topic",
                "title": metadata.get("requirement", "测试用例"),
                "structureClass": structure_class,
                "children": {
                    "attached": children
                }
            }
        }

        return [sheet]

    def _build_case_node(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = str(uuid.uuid4())
        case_title = f"{case.get('id', '')}: {case.get('name', '')}"

        priority = case.get("priority", "")
        precondition = case.get("precondition", "")
        if priority:
            precondition_title = f"前置条件: {precondition} [{priority}]" if precondition else f"前置条件: [{priority}]"
        else:
            precondition_title = f"前置条件: {precondition}" if precondition else "前置条件: 无"

        attached = [
            {"id": str(uuid.uuid4()), "class": "topic", "title": precondition_title}
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

    def _build_metadata_json(self, version: str = "8") -> Dict[str, Any]:
        if version == "2023":
            return {
                "dataStructureVersion": "3",
                "creator": {
                    "name": "AITestCraft",
                    "version": "1.0.0"
                },
                "layoutEngineVersion": "3",
                "format": "xmind-2023"
            }
        return {
            "dataStructureVersion": "2",
            "creator": {
                "name": "AITestCraft",
                "version": "1.0.0"
            },
            "layoutEngineVersion": "3"
        }

    def _build_manifest_json(self, version: str = "8") -> Dict[str, Any]:
        entries = {
            "content.json": {},
            "metadata.json": {},
            "manifest.json": {}
        }
        if version == "2023":
            entries["content.json"] = {"encoding": "utf-8"}
        return {"file-entries": entries}

    def _build_module_node(self, module_name: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        module_id = str(uuid.uuid4())
        case_nodes = [self._build_case_node(case) for case in cases]
        return {
            "id": module_id,
            "class": "topic",
            "title": f"{module_name} ({len(cases)}条)",
            "children": {
                "attached": case_nodes
            }
        }

    def encode_base64(self, xmind_bytes: bytes) -> str:
        return base64.b64encode(xmind_bytes).decode("utf-8")
