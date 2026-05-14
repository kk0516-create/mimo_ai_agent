"""单元测试：测试各 Agent 和解析器的核心功能。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.locator import LocatorAgent
from agent.conflict_detector import ConflictDetectorAgent
from agent.conclusion import ConclusionAgent
from agent.arbiter import ArbiterAgent
from parser.pdf_to_md import PDFToMarkdownParser


class TestLocatorAgent(unittest.TestCase):
    """定位 Agent 单元测试。"""

    def setUp(self) -> None:
        """每个测试前的初始化。"""
        self.agent = LocatorAgent(mock_mode=True)

    def test_locate_with_risk(self) -> None:
        """测试定位包含合规风险的文档切片。"""
        chunk = {
            "chunk_id": 0,
            "title": "## 数据隐私条款",
            "content": (
                "第一条 乙方应遵守《个人信息保护法》的规定，"
                "对用户数据进行数据脱敏处理，确保数据隐私安全。"
                "如发生数据泄露，应在7天内通知甲方。"
            ),
            "page_number": 1,
        }
        result = self.agent.locate(chunk)

        self.assertIn("has_risk", result)
        self.assertIn("risk_labels", result)
        self.assertIn("relevant_text", result)
        self.assertIn("confidence", result)
        self.assertTrue(result["has_risk"])
        self.assertGreater(len(result["risk_labels"]), 0)
        self.assertGreater(result["confidence"], 0.0)

    def test_locate_no_risk(self) -> None:
        """测试定位不包含合规风险的文档切片。"""
        chunk = {
            "chunk_id": 1,
            "title": "## 产品介绍",
            "content": "本产品是一款高效的项目管理工具，支持多人协作和实时编辑。",
            "page_number": 2,
        }
        result = self.agent.locate(chunk)

        self.assertIn("has_risk", result)
        self.assertFalse(result["has_risk"])
        self.assertEqual(len(result["risk_labels"]), 0)

    def test_locate_custom_keywords(self) -> None:
        """测试使用自定义合规关键词列表。"""
        chunk = {
            "chunk_id": 2,
            "title": "## 特殊条款",
            "content": "本合同中关于特定审计程序的约定...",
            "page_number": 3,
        }
        custom_keywords = ["审计"]
        result = self.agent.locate(chunk, compliance_keywords=custom_keywords)

        self.assertTrue(result["has_risk"])
        self.assertIn("审计", result["risk_labels"])

    def test_locate_output_format(self) -> None:
        """测试定位 Agent 输出格式是否正确。"""
        chunk = {
            "chunk_id": 0,
            "title": "## 测试",
            "content": "保密协议约定数据隐私保护措施",
            "page_number": 1,
        }
        result = self.agent.locate(chunk)

        self.assertIsInstance(result["has_risk"], bool)
        self.assertIsInstance(result["risk_labels"], list)
        self.assertIsInstance(result["relevant_text"], str)
        self.assertIsInstance(result["confidence"], float)


class TestConflictDetectorAgent(unittest.TestCase):
    """冲突检测 Agent 单元测试。"""

    def setUp(self) -> None:
        """每个测试前的初始化。"""
        self.agent = ConflictDetectorAgent(mock_mode=True)

    def test_detect_conflicts_with_time_conflict(self) -> None:
        """测试检测时间矛盾。"""
        chunks = [
            {
                "chunk_id": 0,
                "title": "通知期限A",
                "content": "乙方应在收到通知后30天内完成安全评估",
                "risk_labels": ["违约责任"],
                "page_number": 1,
            },
            {
                "chunk_id": 1,
                "title": "通知期限B",
                "content": "乙方应在7天内通知甲方数据泄露事件",
                "risk_labels": ["数据隐私"],
                "page_number": 2,
            },
        ]
        result = self.agent.detect_conflicts(chunks)

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for conflict in result:
            self.assertIn("clause_a", conflict)
            self.assertIn("clause_b", conflict)
            self.assertIn("conflict_type", conflict)
            self.assertIn("description", conflict)

    def test_detect_no_conflicts_with_empty_input(self) -> None:
        """测试空输入时返回空列表。"""
        result = self.agent.detect_conflicts([])
        self.assertEqual(result, [])

    def test_detect_conflicts_output_format(self) -> None:
        """测试冲突检测输出格式。"""
        chunks = [
            {
                "chunk_id": 0,
                "title": "测试条款",
                "content": "甲方不得向第三方披露保密信息，但可以授权关联公司使用",
                "risk_labels": ["保密协议"],
                "page_number": 1,
            },
        ]
        result = self.agent.detect_conflicts(chunks)

        self.assertIsInstance(result, list)
        if result:
            conflict = result[0]
            self.assertIn("conflict_type", conflict)
            self.assertIn(conflict["conflict_type"],
                          ["时间矛盾", "权限矛盾", "定义矛盾", "责任矛盾", "潜在矛盾"])


class TestArbiterAgent(unittest.TestCase):
    """仲裁 Agent 单元测试。"""

    def setUp(self) -> None:
        """每个测试前的初始化。"""
        self.agent = ArbiterAgent(mock_mode=True)

    def test_arbitrate_time_conflict(self) -> None:
        """测试仲裁时间矛盾冲突。"""
        conflict = {
            "clause_a": "通知期限条款（30天）",
            "clause_b": "通知期限条款（7天）",
            "conflict_type": "时间矛盾",
            "description": "不同条款中关于通知期限的规定存在矛盾",
        }
        result = self.agent.arbitrate(conflict)

        self.assertIn("decision", result)
        self.assertIn("priority_basis", result)
        self.assertIn("final_confidence", result)
        self.assertIsInstance(result["decision"], str)
        self.assertIsInstance(result["final_confidence"], float)

    def test_arbitrate_permission_conflict(self) -> None:
        """测试仲裁权限矛盾冲突。"""
        conflict = {
            "clause_a": "禁止性条款（不得...）",
            "clause_b": "授权性条款（可以...）",
            "conflict_type": "权限矛盾",
            "description": "禁止某些行为的同时又授权了相应行为",
        }
        result = self.agent.arbitrate(conflict)

        self.assertIn("decision", result)
        self.assertGreater(len(result["decision"]), 0)

    def test_arbitrate_custom_hierarchy(self) -> None:
        """测试使用自定义法规优先级。"""
        conflict = {
            "clause_a": "条款A",
            "clause_b": "条款B",
            "conflict_type": "定义矛盾",
            "description": "定义不一致",
        }
        custom_hierarchy = {"国际法": 4, "国家法律": 3, "行业规范": 2, "合同条款": 1}
        result = self.agent.arbitrate(conflict, regulation_hierarchy=custom_hierarchy)

        self.assertIn("priority_basis", result)
        self.assertIn("国际法", result["priority_basis"])

    def test_arbitrate_output_format(self) -> None:
        """测试仲裁输出格式。"""
        conflict = {
            "clause_a": "A",
            "clause_b": "B",
            "conflict_type": "定义矛盾",
            "description": "测试",
        }
        result = self.agent.arbitrate(conflict)

        self.assertIsInstance(result["decision"], str)
        self.assertIsInstance(result["priority_basis"], str)
        self.assertIsInstance(result["final_confidence"], float)
        self.assertGreater(result["final_confidence"], 0.0)
        self.assertLessEqual(result["final_confidence"], 1.0)


class TestConclusionAgent(unittest.TestCase):
    """结论生成 Agent 单元测试。"""

    def setUp(self) -> None:
        """每个测试前的初始化。"""
        self.agent = ConclusionAgent(mock_mode=True)

    def test_generate_report(self) -> None:
        """测试生成合规报告。"""
        locations = [
            {
                "has_risk": True,
                "risk_labels": ["数据隐私"],
                "relevant_text": "涉及数据隐私条款",
                "confidence": 0.85,
            },
            {
                "has_risk": True,
                "risk_labels": ["保密协议"],
                "relevant_text": "涉及保密协议条款",
                "confidence": 0.72,
            },
        ]
        conflicts = [
            {
                "clause_a": "通知期限（30天）",
                "clause_b": "通知期限（7天）",
                "conflict_type": "时间矛盾",
                "description": "期限矛盾",
            }
        ]
        result = self.agent.generate_report(locations, conflicts)

        self.assertIn("summary", result)
        self.assertIn("risk_level", result)
        self.assertIn("recommendations", result)
        self.assertIn("evidence_count", result)
        self.assertIn(result["risk_level"], ["high", "medium", "low"])
        self.assertIsInstance(result["recommendations"], list)
        self.assertGreater(len(result["recommendations"]), 0)

    def test_generate_report_with_arbitrations(self) -> None:
        """测试包含仲裁结果的报告生成。"""
        locations = [{"has_risk": True, "risk_labels": ["GDPR"], "relevant_text": "", "confidence": 0.9}]
        conflicts = [{"clause_a": "A", "clause_b": "B", "conflict_type": "权限矛盾", "description": "test"}]
        arbitrations = [{"decision": "以法律为准", "priority_basis": "国际法 > 国家法律", "final_confidence": 0.82}]

        result = self.agent.generate_report(locations, conflicts, arbitrations)
        self.assertIn("summary", result)
        self.assertIn("risk_level", result)

    def test_generate_report_low_risk(self) -> None:
        """测试低风险场景的报告生成。"""
        locations = [{"has_risk": False, "risk_labels": [], "relevant_text": "", "confidence": 0.1}]
        conflicts = []
        result = self.agent.generate_report(locations, conflicts)

        self.assertIn("risk_level", result)
        self.assertEqual(result["risk_level"], "low")

    def test_report_output_format(self) -> None:
        """测试报告输出格式。"""
        locations = [{"has_risk": True, "risk_labels": ["数据隐私"], "relevant_text": "test", "confidence": 0.8}]
        conflicts = []
        result = self.agent.generate_report(locations, conflicts)

        self.assertIsInstance(result["summary"], str)
        self.assertIsInstance(result["risk_level"], str)
        self.assertIsInstance(result["recommendations"], list)
        self.assertIsInstance(result["evidence_count"], int)


class TestPDFToMarkdownParser(unittest.TestCase):
    """PDF 解析器单元测试。"""

    def setUp(self) -> None:
        """每个测试前的初始化。"""
        self.parser = PDFToMarkdownParser()

    def test_extract_text_file_not_found(self) -> None:
        """测试提取不存在的文件时抛出异常。"""
        with self.assertRaises(FileNotFoundError):
            self.parser.extract_text("nonexistent_file.pdf")

    def test_semantic_chunking_basic(self) -> None:
        """测试基本的语义切片功能。"""
        markdown_text = (
            "## 第一章 总则\n\n"
            "第一条 本合同旨在规范双方的合作关系。\n\n"
            "## 第二章 数据隐私\n\n"
            "第二条 乙方应遵守数据隐私相关规定。\n\n"
            "### 第2.1条 细节\n\n"
            "具体的数据隐私保护措施。\n\n"
            "## 第三章 违约责任\n\n"
            "第三条 违约方应承担赔偿责任。"
        )
        chunks = self.parser.semantic_chunking(markdown_text)

        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertIn("chunk_id", chunk)
            self.assertIn("title", chunk)
            self.assertIn("content", chunk)
            self.assertIn("page_number", chunk)

    def test_semantic_chunking_no_headers(self) -> None:
        """测试无标题的文本切片。"""
        markdown_text = "这是一段没有标题的纯文本内容。" * 100
        chunks = self.parser.semantic_chunking(markdown_text, chunk_size=500)

        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)

    def test_semantic_chunking_large_section(self) -> None:
        """测试过大章节的拆分。"""
        markdown_text = "## 大章节\n\n" + "内容段落。\n\n" * 200
        chunks = self.parser.semantic_chunking(markdown_text, chunk_size=500)

        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 1)

    def test_semantic_chunking_custom_size(self) -> None:
        """测试自定义切片大小。"""
        markdown_text = (
            "## 章节1\n\n" + "内容A。" * 50 + "\n\n"
            "## 章节2\n\n" + "内容B。" * 50
        )
        chunks_small = self.parser.semantic_chunking(markdown_text, chunk_size=200)
        chunks_large = self.parser.semantic_chunking(markdown_text, chunk_size=5000)

        self.assertGreaterEqual(len(chunks_small), len(chunks_large))


class TestIntegration(unittest.TestCase):
    """集成测试：测试多 Agent 协作流程。"""

    def test_full_pipeline_mock(self) -> None:
        """测试 Mock 模式下的完整流水线。"""
        locator = LocatorAgent(mock_mode=True)
        detector = ConflictDetectorAgent(mock_mode=True)
        arbiter = ArbiterAgent(mock_mode=True)
        conclusion = ConclusionAgent(mock_mode=True)

        chunk = {
            "chunk_id": 0,
            "title": "## 数据隐私条款",
            "content": (
                "乙方应遵守《个人信息保护法》，"
                "在30天内完成数据安全评估。"
                "如发生数据泄露，应在7天内通知甲方。"
            ),
            "page_number": 1,
        }

        location = locator.locate(chunk)
        self.assertTrue(location["has_risk"])

        enriched = {**chunk, **location}
        conflicts = detector.detect_conflicts([enriched])
        self.assertIsInstance(conflicts, list)

        if conflicts:
            arbitration = arbiter.arbitrate(conflicts[0])
            self.assertIn("decision", arbitration)
            arbitrations = [arbitration]
        else:
            arbitrations = []

        report = conclusion.generate_report([location], conflicts, arbitrations)
        self.assertIn("summary", report)
        self.assertIn("risk_level", report)
        self.assertIn("recommendations", report)


if __name__ == "__main__":
    unittest.main()
