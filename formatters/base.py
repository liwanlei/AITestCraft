# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional


class FormatterError(Exception):
    pass


class BaseFormatter(ABC):
    @abstractmethod
    def format(self, testcases: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> Union[str, bytes]:
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        pass

    def _build_metadata(self, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if metadata is None:
            metadata = {}
        return {
            "title": metadata.get("title", "测试用例文档"),
            "requirement": metadata.get("requirement", ""),
            "generated_at": metadata.get("generated_at", ""),
            "total_count": metadata.get("total_count", 0),
            "coverage": metadata.get("coverage", 0)
        }
