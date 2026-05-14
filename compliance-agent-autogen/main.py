"""主入口文件：整合所有 Agent 执行合规审查流程。"""

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if sys.stdout.encoding != "utf-8" else sys.stdout

from agent.locator import LocatorAgent
from agent.conflict_detector import ConflictDetectorAgent
from agent.conclusion import ConclusionAgent
from agent.arbiter import ArbiterAgent
from parser.pdf_to_md import PDFToMarkdownParser
from config import COMPLIANCE_KEYWORDS, MOCK_MODE, PROJECT_ROOT


class ComplianceReviewPipeline:
    """合规审查流水线：协调多个 Agent 完成文档审查。

    流程：
    1. 解析 PDF -> Markdown
    2. 语义切片
    3. 定位 Agent 识别风险段落
    4. 冲突检测 Agent 检测条款矛盾
    5. 仲裁 Agent 裁决冲突
    6. 结论 Agent 生成最终报告
    """

    def __init__(self, mock_mode: bool = True) -> None:
        """初始化合规审查流水线。

        Args:
            mock_mode: 是否使用 Mock 模式。
        """
        self.parser = PDFToMarkdownParser()
        self.locator = LocatorAgent(mock_mode=mock_mode)
        self.conflict_detector = ConflictDetectorAgent(mock_mode=mock_mode)
        self.arbiter = ArbiterAgent(mock_mode=mock_mode)
        self.conclusion = ConclusionAgent(mock_mode=mock_mode)
        self.mock_mode = mock_mode
        self.total_tokens: int = 0

    def run(self, pdf_path: str | Path) -> dict[str, Any]:
        """执行完整的合规审查流程。

        Args:
            pdf_path: 待审查的 PDF 文件路径。

        Returns:
            完整的合规审查报告。
        """
        pdf_path = Path(pdf_path)
        start_time = time.time()

        print("=" * 60)
        print("📋 长文档合规审查多 Agent 系统")
        print("=" * 60)
        mode_str = "Mock 模式" if self.mock_mode else "LLM 模式"
        print(f"🔧 运行模式: {mode_str}")
        print(f"📄 文件: {pdf_path.name}")
        print()

        # Step 1: 解析 PDF
        print("📖 Step 1: 解析 PDF 文件...")
        try:
            markdown_text = self.parser.to_markdown(pdf_path)
            print(f"   ✅ PDF 解析完成，文本长度: {len(markdown_text)} 字符")
        except Exception as e:
            print(f"   ❌ PDF 解析失败: {e}")
            return {"error": str(e)}

        # Step 2: 语义切片
        print("\n✂️  Step 2: 语义切片...")
        chunks = self.parser.semantic_chunking(markdown_text)
        print(f"   ✅ 切片完成，共 {len(chunks)} 个切片")
        for chunk in chunks:
            print(f"      - 切片 {chunk['chunk_id']}: {chunk['title']} "
                  f"({len(chunk['content'])} 字符, 第{chunk['page_number']}页)")

        # Step 3: 定位 Agent 识别风险段落
        print("\n🔍 Step 3: 定位 Agent 扫描合规风险...")
        locations: list[dict[str, Any]] = []
        for chunk in chunks:
            result = self.locator.locate(chunk, COMPLIANCE_KEYWORDS)
            result["chunk_id"] = chunk["chunk_id"]
            result["chunk_title"] = chunk["title"]
            locations.append(result)

            status = "⚠️ 风险" if result["has_risk"] else "✅ 通过"
            print(f"   {status} 切片 {chunk['chunk_id']}: "
                  f"置信度={result['confidence']}, "
                  f"标签={result.get('risk_labels', [])}")

        risky_chunks = [loc for loc in locations if loc["has_risk"]]
        print(f"\n   📊 风险切片: {len(risky_chunks)}/{len(chunks)}")

        if not risky_chunks:
            print("\n✅ 未发现合规风险，审查完成。")
            report = {
                "summary": "经合规审查，未发现明显合规风险",
                "risk_level": "low",
                "recommendations": ["建议定期复查以确保持续合规"],
                "evidence_count": 0,
            }
            self._print_report(report, start_time)
            return report

        # Step 4: 冲突检测 Agent
        print("\n⚔️  Step 4: 冲突检测 Agent 分析条款矛盾...")
        enriched_chunks = []
        for loc in risky_chunks:
            chunk_id = loc["chunk_id"]
            original_chunk = chunks[chunk_id]
            enriched = {**original_chunk, **loc}
            enriched_chunks.append(enriched)

        conflicts = self.conflict_detector.detect_conflicts(enriched_chunks)
        print(f"   📊 检测到 {len(conflicts)} 个冲突")
        for i, conflict in enumerate(conflicts):
            print(f"      🔴 冲突{i + 1}: [{conflict.get('conflict_type', 'N/A')}] "
                  f"{conflict.get('clause_a', 'N/A')} vs {conflict.get('clause_b', 'N/A')}")
            print(f"         描述: {conflict.get('description', 'N/A')}")

        # Step 5: 仲裁 Agent
        arbitrations: list[dict[str, Any]] = []
        if conflicts:
            print("\n⚖️  Step 5: 仲裁 Agent 裁决冲突...")
            for i, conflict in enumerate(conflicts):
                arb_result = self.arbiter.arbitrate(conflict)
                arbitrations.append(arb_result)
                print(f"   裁决{i + 1}: {arb_result.get('decision', 'N/A')}")
                print(f"      依据: {arb_result.get('priority_basis', 'N/A')}")
                print(f"      置信度: {arb_result.get('final_confidence', 'N/A')}")
        else:
            print("\n⚖️  Step 5: 无冲突，跳过仲裁环节")

        # Step 6: 结论 Agent 生成报告
        print("\n📝 Step 6: 结论 Agent 生成合规报告...")
        report = self.conclusion.generate_report(locations, conflicts, arbitrations)
        self._print_report(report, start_time)

        # 统计 Token 消耗
        self.total_tokens = (
            self.locator.token_count
            + self.conflict_detector.token_count
            + self.arbiter.token_count
            + self.conclusion.token_count
        )
        self._print_token_usage()

        return report

    def _print_report(self, report: dict[str, Any], start_time: float) -> None:
        """打印格式化的合规报告。

        Args:
            report: 合规报告字典。
            start_time: 开始时间戳。
        """
        elapsed = time.time() - start_time
        risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        risk_level = report.get("risk_level", "unknown")
        emoji = risk_emoji.get(risk_level, "⚪")

        print("\n" + "=" * 60)
        print(f"{emoji} 合规审查报告")
        print("=" * 60)
        print(f"📊 风险等级: {risk_level.upper()}")
        print(f"📝 摘要: {report.get('summary', 'N/A')}")
        print(f"🔢 证据数量: {report.get('evidence_count', 0)}")
        print(f"📋 建议:")
        for i, rec in enumerate(report.get("recommendations", []), 1):
            print(f"   {i}. {rec}")
        print(f"\n⏱️  总耗时: {elapsed:.2f}秒")
        print("=" * 60)

    def _print_token_usage(self) -> None:
        """打印 Token 消耗预估。"""
        print("\n💰 Token 消耗预估:")
        print(f"   定位 Agent:       {self.locator.token_count} tokens")
        print(f"   冲突检测 Agent:   {self.conflict_detector.token_count} tokens")
        print(f"   仲裁 Agent:       {self.arbiter.token_count} tokens")
        print(f"   结论生成 Agent:   {self.conclusion.token_count} tokens")
        print(f"   ─────────────────────────────────")
        print(f"   总计:             {self.total_tokens} tokens")
        if not self.mock_mode:
            cost = self.total_tokens * 0.00001
            print(f"   预估费用:         ${cost:.4f} (基于 GPT-3.5-turbo)")
        else:
            print("   (Mock 模式，无实际 API 调用)")


def main() -> None:
    """主入口函数。"""
    arg_parser = argparse.ArgumentParser(
        description="长文档合规审查多 Agent 系统",
    )
    arg_parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="待审查的 PDF 文件路径",
    )
    arg_parser.add_argument(
        "--mock",
        action="store_true",
        default=None,
        help="使用 Mock 模式（无需 API Key）",
    )
    arg_parser.add_argument(
        "--no-mock",
        action="store_true",
        help="禁用 Mock 模式（需要 API Key）",
    )
    arg_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="报告输出路径（JSON 格式）",
    )

    args = arg_parser.parse_args()

    mock_mode = MOCK_MODE
    if args.mock:
        mock_mode = True
    elif args.no_mock:
        mock_mode = False

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    pipeline = ComplianceReviewPipeline(mock_mode=mock_mode)
    report = pipeline.run(pdf_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n💾 报告已保存至: {output_path}")


if __name__ == "__main__":
    main()
