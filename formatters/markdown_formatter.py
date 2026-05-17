# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Dict, Any, Optional

from formatters.base import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    @property
    def content_type(self) -> str:
        return "text/markdown"

    @property
    def file_extension(self) -> str:
        return "md"

    def format(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> str:
        if not testcases:
            return self._format_empty(metadata)

        meta = self._build_metadata(metadata)
        lines = []

        lines.append("# 测试用例文档")
        lines.append("")
        lines.append("## 项目概述")
        lines.append(f"- **需求**: {meta['requirement'] or '未指定'}")
        lines.append(f"- **生成时间**: {meta['generated_at'] or datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"- **总计用例**: {len(testcases)} 条")
        lines.append("")

        priority_groups = self._group_by_priority(testcases)

        for priority in ["P0", "P1", "P2"]:
            if priority not in priority_groups:
                continue
            cases = priority_groups[priority]
            lines.append("---")
            lines.append("")
            lines.append(f"## {priority} 优先级用例")
            lines.append("")
            lines.append(self._format_table(cases))
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 测试覆盖说明")
        lines.append("")
        lines.append(f"- **覆盖率**: {meta.get('coverage', 'N/A')}")
        lines.append("")

        lines.append("## 用例统计")
        lines.append("")
        lines.append("| 优先级 | 数量 |")
        lines.append("|--------|------|")
        for priority in ["P0", "P1", "P2"]:
            count = len(priority_groups.get(priority, []))
            if count > 0:
                lines.append(f"| {priority} | {count} |")
        lines.append(f"| **总计** | **{len(testcases)}** |")

        return "\n".join(lines)

    def _format_table(self, testcases: List[Dict[str, Any]]) -> str:
        lines = []
        lines.append("| 用例ID | 用例名称 | 优先级 | 前置条件 | 测试步骤 | 预期结果 |")
        lines.append("|--------|----------|--------|----------|----------|----------|")

        for case in testcases:
            case_id = case.get("id", "")
            name = case.get("name", "")
            priority = case.get("priority", "")
            precondition = case.get("precondition", "")

            steps = case.get("steps", [])
            if isinstance(steps, list):
                steps_text = "<br>".join([f"{i+1}. {s}" for i, s in enumerate(steps)])
            else:
                steps_text = str(steps)

            assert_list = case.get("assert", [])
            if isinstance(assert_list, list):
                assert_text = "<br>".join([f"{i+1}. {s}" for i, s in enumerate(assert_list)])
            else:
                assert_text = str(assert_list)

            lines.append(f"| {case_id} | {name} | {priority} | {precondition} | {steps_text} | {assert_text} |")

        return "\n".join(lines)

    def _group_by_priority(self, testcases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for case in testcases:
            priority = case.get("priority", "P2")
            if priority not in groups:
                groups[priority] = []
            groups[priority].append(case)
        return groups

    def _format_empty(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        meta = self._build_metadata(metadata)
        lines = []
        lines.append("# 测试用例文档")
        lines.append("")
        lines.append("## 项目概述")
        lines.append(f"- **需求**: {meta['requirement'] or '未指定'}")
        lines.append(f"- **生成时间**: {meta['generated_at'] or datetime.now().strftime('%Y-%m-%d')}")
        lines.append("- **总计用例**: 0 条")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("**暂无测试用例**")
        return "\n".join(lines)
