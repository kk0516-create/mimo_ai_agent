"""演示推理脚本：不需要真实 API Key，模拟完整的多 Agent 协作流程。"""

import io
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def print_separator(title: str) -> None:
    """打印分隔线。

    Args:
        title: 分隔线标题。
    """
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def simulate_pipeline() -> None:
    """模拟完整的多 Agent 合规审查推理流程。"""

    print_separator("🤖 长文档合规审查多 Agent 系统 - 演示模式")
    print("本演示使用模拟数据，无需 API Key 即可体验完整的审查流程。")

    # 模拟文档切片
    sample_chunks: list[dict[str, Any]] = [
        {
            "chunk_id": 0,
            "title": "## 第一章 总则",
            "content": (
                "第一条 本合同旨在规范甲乙双方在数据处理方面的合作关系。"
                "甲方作为数据控制者，乙方作为数据处理者，双方应遵守"
                "《个人信息保护法》和GDPR的相关规定。\n\n"
                "第二条 乙方应在收到甲方通知后30天内完成数据安全评估，"
                "并提交评估报告。乙方不得将数据传输至境外服务器，"
                "除非获得甲方书面同意。"
            ),
            "page_number": 1,
        },
        {
            "chunk_id": 1,
            "title": "## 第二章 数据隐私与保密协议",
            "content": (
                "第三条 乙方承诺对在合作过程中获取的所有数据采取保密措施，"
                "签署保密协议，确保数据不被泄露、篡改或滥用。\n\n"
                "第四条 如发生数据泄露事件，乙方应在7天内通知甲方，"
                "并采取必要的补救措施。甲方有权对乙方进行审计，"
                "以确保其数据处理活动符合合规要求。"
            ),
            "page_number": 2,
        },
        {
            "chunk_id": 2,
            "title": "## 第三章 违约责任",
            "content": (
                "第五条 如乙方违反本合同约定，应承担违约责任，"
                "赔偿甲方因此遭受的直接损失。赔偿金额不超过"
                "合同总金额的200%。\n\n"
                "第六条 甲方可以在发现乙方违约行为后，"
                "无需提前通知即可解除合同，并要求乙方在15天内"
                "删除所有相关数据。争议解决方式为仲裁。"
            ),
            "page_number": 3,
        },
        {
            "chunk_id": 3,
            "title": "## 第四章 跨境数据传输",
            "content": (
                "第七条 在满足以下条件时，乙方可以进行跨境数据传输：\n"
                "1. 获得数据主体的知情同意\n"
                "2. 通过国家网信部门的安全评估\n"
                "3. 按照国家规定进行数据脱敏处理\n\n"
                "第八条 乙方可以授权其关联公司处理数据，"
                "但应确保关联公司遵守同等的数据保护标准。"
                "敏感信息应进行加密存储。"
            ),
            "page_number": 4,
        },
    ]

    # Step 1: 展示文档切片
    print_separator("📖 Step 1: 文档切片展示")
    for chunk in sample_chunks:
        print(f"📄 切片 {chunk['chunk_id']}: {chunk['title']}")
        print(f"   页码: {chunk['page_number']}")
        content_preview = chunk['content'][:80] + "..." if len(chunk['content']) > 80 else chunk['content']
        print(f"   内容: {content_preview}")
        print()

    # Step 2: 定位 Agent
    print_separator("🔍 Step 2: 定位 Agent 识别合规风险")
    from agent.locator import LocatorAgent

    locator = LocatorAgent(mock_mode=True)
    locations: list[dict[str, Any]] = []

    for chunk in sample_chunks:
        result = locator.locate(chunk)
        result["chunk_id"] = chunk["chunk_id"]
        result["chunk_title"] = chunk["title"]
        locations.append(result)

        status = "⚠️ 发现风险" if result["has_risk"] else "✅ 无风险"
        print(f"  切片 {chunk['chunk_id']}: {status}")
        print(f"    置信度: {result['confidence']}")
        print(f"    风险标签: {result.get('risk_labels', [])}")
        if result.get("relevant_text"):
            text = result["relevant_text"][:60] + "..."
            print(f"    相关文本: {text}")
        print()

    risky_count = sum(1 for loc in locations if loc["has_risk"])
    print(f"📊 汇总: {risky_count}/{len(sample_chunks)} 个切片存在合规风险")

    # Step 3: 冲突检测 Agent
    print_separator("⚔️ Step 3: 冲突检测 Agent 分析条款矛盾")
    from agent.conflict_detector import ConflictDetectorAgent

    detector = ConflictDetectorAgent(mock_mode=True)
    risky_chunks = []
    for loc in locations:
        if loc["has_risk"]:
            chunk_id = loc["chunk_id"]
            enriched = {**sample_chunks[chunk_id], **loc}
            risky_chunks.append(enriched)

    conflicts = detector.detect_conflicts(risky_chunks)
    print(f"📊 检测到 {len(conflicts)} 个条款冲突:\n")
    for i, conflict in enumerate(conflicts, 1):
        print(f"  🔴 冲突 {i}:")
        print(f"    类型: {conflict.get('conflict_type', 'N/A')}")
        print(f"    条款A: {conflict.get('clause_a', 'N/A')}")
        print(f"    条款B: {conflict.get('clause_b', 'N/A')}")
        print(f"    描述: {conflict.get('description', 'N/A')}")
        print()

    # Step 4: 仲裁 Agent
    print_separator("⚖️ Step 4: 仲裁 Agent 裁决冲突")
    from agent.arbiter import ArbiterAgent

    arbiter = ArbiterAgent(mock_mode=True)
    arbitrations: list[dict[str, Any]] = []

    for i, conflict in enumerate(conflicts, 1):
        arb_result = arbiter.arbitrate(conflict)
        arbitrations.append(arb_result)
        print(f"  裁决 {i}:")
        print(f"    决定: {arb_result.get('decision', 'N/A')}")
        print(f"    依据: {arb_result.get('priority_basis', 'N/A')}")
        print(f"    置信度: {arb_result.get('final_confidence', 'N/A')}")
        print()

    # Step 5: 结论 Agent
    print_separator("📝 Step 5: 结论 Agent 生成合规报告")
    from agent.conclusion import ConclusionAgent

    conclusion_agent = ConclusionAgent(mock_mode=True)
    report = conclusion_agent.generate_report(locations, conflicts, arbitrations)

    risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    risk_level = report.get("risk_level", "unknown")
    emoji = risk_emoji.get(risk_level, "⚪")

    print(f"  {emoji} 风险等级: {risk_level.upper()}")
    print(f"\n  📝 摘要:")
    print(f"  {report.get('summary', 'N/A')}")
    print(f"\n  🔢 证据数量: {report.get('evidence_count', 0)}")
    print(f"\n  📋 改进建议:")
    for i, rec in enumerate(report.get("recommendations", []), 1):
        print(f"    {i}. {rec}")

    # Token 消耗
    total_tokens = (
        locator.token_count
        + detector.token_count
        + arbiter.token_count
        + conclusion_agent.token_count
    )

    print_separator("💰 Token 消耗预估")
    print(f"  定位 Agent:       {locator.token_count:>6} tokens")
    print(f"  冲突检测 Agent:   {detector.token_count:>6} tokens")
    print(f"  仲裁 Agent:       {arbiter.token_count:>6} tokens")
    print(f"  结论生成 Agent:   {conclusion_agent.token_count:>6} tokens")
    print(f"  ────────────────────────────────")
    print(f"  总计:             {total_tokens:>6} tokens")
    print(f"  (Mock 模式，无实际 API 调用)")

    # 多 Agent 协作流程总结
    print_separator("🔄 多 Agent 协作流程总结")
    print("  1️⃣  PDF 解析器 → 将 PDF 转为 Markdown，按章节语义切片")
    print("  2️⃣  定位 Agent → 扫描每个切片，识别合规风险段落")
    print("  3️⃣  冲突检测 Agent → 分析有风险的切片，检测条款矛盾")
    print("  4️⃣  仲裁 Agent → 根据法规优先级裁决冲突")
    print("  5️⃣  结论 Agent → 汇总分析结果，生成最终合规报告")
    print()
    print("  🔗 Agent 间通过消息传递协作，每个 Agent 独立负责一个环节，")
    print("     体现了多 Agent 系统的分工协作和模块化优势。")
    print()
    print("  ✅ 演示完成！如需处理真实 PDF 文件，请运行:")
    print("     python main.py --pdf your_document.pdf")


if __name__ == "__main__":
    simulate_pipeline()
