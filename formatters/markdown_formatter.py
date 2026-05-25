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

        module_groups = self._group_by_module(testcases)
        if module_groups and len(module_groups) > 1:
            return self._format_by_module(testcases, meta, module_groups)

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

    def _format_by_module(self, testcases: List[Dict[str, Any]], meta: Dict[str, Any], module_groups: Dict[str, List[Dict[str, Any]]]) -> str:
        lines = []
        lines.append("# 测试用例文档")
        lines.append("")
        lines.append("## 项目概述")
        lines.append(f"- **需求**: {meta['requirement'] or '未指定'}")
        lines.append(f"- **生成时间**: {meta['generated_at'] or datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"- **总计用例**: {len(testcases)} 条")
        lines.append(f"- **模块数**: {len(module_groups)}")
        lines.append("")

        p0_total = 0
        p1_total = 0
        p2_total = 0

        for module_name, cases in module_groups.items():
            lines.append("---")
            lines.append("")
            lines.append(f"## 模块: {module_name}")
            lines.append(f"- **用例数**: {len(cases)}")
            lines.append("")
            lines.append(self._format_table(cases))
            lines.append("")

            for c in cases:
                p = c.get("priority", "P2")
                if p == "P0":
                    p0_total += 1
                elif p == "P1":
                    p1_total += 1
                else:
                    p2_total += 1

        lines.append("---")
        lines.append("")
        lines.append("## 用例统计")
        lines.append("")
        lines.append("| 模块 | P0 | P1 | P2 | 总计 |")
        lines.append("|------|----|----|----|----|")
        for module_name, cases in module_groups.items():
            p0 = len([c for c in cases if c.get("priority", "") == "P0"])
            p1 = len([c for c in cases if c.get("priority", "") == "P1"])
            p2 = len([c for c in cases if c.get("priority", "") == "P2"])
            lines.append(f"| {module_name} | {p0} | {p1} | {p2} | {len(cases)} |")
        lines.append(f"| **总计** | **{p0_total}** | **{p1_total}** | **{p2_total}** | **{len(testcases)}** |")

        return "\n".join(lines)

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
