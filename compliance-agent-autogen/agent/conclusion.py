"""结论生成 Agent：输出风险报告。"""

import json
from typing import Any, Optional

from config import AGENT_CONFIG, MOCK_MODE, MODEL_NAME, OPENAI_API_KEY


class MockLLM:
    """结论生成模拟 LLM。"""

    def __init__(self) -> None:
        """初始化 MockLLM。"""
        self.call_count: int = 0
        self.total_tokens: int = 0

    def run(self, prompt: str) -> str:
        """模拟结论生成推理。

        Args:
            prompt: 输入提示词。

        Returns:
            模拟的风险报告 JSON 字符串。
        """
        self.call_count += 1
        estimated_tokens = len(prompt) // 4 + 100
        self.total_tokens += estimated_tokens
        return self._mock_conclusion(prompt)

    def _mock_conclusion(self, prompt: str) -> str:
        """生成模拟结论响应。

        Args:
            prompt: 包含定位和冲突检测结果的提示词。

        Returns:
            风险报告 JSON 字符串。
        """
        high_risk_keywords = ["严重", "高风险", "重大矛盾", "违规"]
        low_risk_keywords = ["轻微", "低风险", "基本合规", "无明显冲突"]

        risk_level = "medium"
        if any(kw in prompt for kw in high_risk_keywords):
            risk_level = "high"
        elif any(kw in prompt for kw in low_risk_keywords):
            risk_level = "low"

        risk_count = prompt.count("has_risk") + prompt.count("conflict_type")
        if risk_count > 4:
            risk_level = "high"
        elif risk_count <= 1:
            risk_level = "low"

        summary_parts: list[str] = []
        if "数据隐私" in prompt or "GDPR" in prompt or "个人信息" in prompt:
            summary_parts.append("文档中涉及数据隐私相关条款，需确保符合《个人信息保护法》和GDPR的要求")
        if "保密协议" in prompt:
            summary_parts.append("保密协议条款需审查其适用范围和期限是否合理")
        if "违约" in prompt:
            summary_parts.append("违约责任条款需确认其与法律规定的一致性")
        if "时间矛盾" in prompt:
            summary_parts.append("不同条款间存在时限矛盾，需统一标准")
        if "权限矛盾" in prompt:
            summary_parts.append("部分条款存在权限冲突，需厘清权责边界")

        if not summary_parts:
            summary_parts.append("经审查，文档存在一定合规风险点，建议进一步核实")

        recommendations: list[str] = [
            "建议对涉及的合规风险条款进行修订，确保与最新法规一致",
            "建议引入专业法律顾问对高风险条款进行复核",
            "建议建立合规审查跟踪机制，确保整改落实",
        ]

        if risk_level == "high":
            recommendations.insert(0, "建议立即暂停相关业务流程，直至合规风险消除")
            recommendations.append("建议进行全面的合规培训，提升全员合规意识")

        result = {
            "summary": "；".join(summary_parts),
            "risk_level": risk_level,
            "recommendations": recommendations,
            "evidence_count": max(risk_count, 2),
        }
        return json.dumps(result, ensure_ascii=False)


class ConclusionAgent:
    """结论生成 Agent：基于定位和冲突检测结果，生成最终合规报告。

    该 Agent 汇总所有 Agent 的分析结果，生成包含风险等级、
    摘要和建议的完整合规审查报告。
    """

    def __init__(self, mock_mode: Optional[bool] = None) -> None:
        """初始化结论生成 Agent。

        Args:
            mock_mode: 是否使用 Mock 模式。默认从 config.py 读取。
        """
        self.mock_mode = mock_mode if mock_mode is not None else MOCK_MODE
        self.llm: Optional[MockLLM] = None
        self.autogen_agent = None
        self.token_count: int = 0

        if self.mock_mode:
            self.llm = MockLLM()
        else:
            self._init_autogen_agent()

    def _init_autogen_agent(self) -> None:
        """初始化 AutoGen AssistantAgent。"""
        if not OPENAI_API_KEY:
            print("[警告] 未设置 OPENAI_API_KEY，自动切换到 Mock 模式")
            self.mock_mode = True
            self.llm = MockLLM()
            return

        try:
            import autogen

            llm_config = {
                "model": MODEL_NAME,
                "api_key": OPENAI_API_KEY,
                "temperature": AGENT_CONFIG["conclusion"]["temperature"],
                "max_tokens": AGENT_CONFIG["conclusion"]["max_tokens"],
            }

            self.autogen_agent = autogen.AssistantAgent(
                name="ConclusionAgent",
                system_message=(
                    "你是一名专业的合规审查结论专家。你的任务是基于定位和冲突检测的结果，"
                    "生成最终的合规风险报告。请严格按照 JSON 格式输出：\n"
                    '{"summary": str, "risk_level": "high/medium/low", '
                    '"recommendations": List[str], "evidence_count": int}'
                ),
                llm_config=llm_config,
            )
        except ImportError:
            print("[警告] autogen 未安装，自动切换到 Mock 模式")
            self.mock_mode = True
            self.llm = MockLLM()
        except Exception as e:
            print(f"[警告] AutoGen Agent 初始化失败: {e}，切换到 Mock 模式")
            self.mock_mode = True
            self.llm = MockLLM()

    def generate_report(
        self,
        locations: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        arbitrations: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """基于定位和冲突检测结果，生成最终合规报告。

        Args:
            locations: 定位 Agent 的输出列表，每个元素包含 has_risk, risk_labels 等。
            conflicts: 冲突检测 Agent 的输出列表。
            arbitrations: 仲裁 Agent 的输出列表（可选）。

        Returns:
            包含 summary, risk_level, recommendations, evidence_count 的字典。
        """
        if self.mock_mode and self.llm:
            prompt = self._build_prompt(locations, conflicts, arbitrations)
            response = self.llm.run(prompt)
            try:
                result = json.loads(response)
                self.token_count = self.llm.total_tokens
                return result
            except json.JSONDecodeError:
                pass

        return self._rule_based_report(locations, conflicts, arbitrations)

    def _build_prompt(
        self,
        locations: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        arbitrations: Optional[list[dict[str, Any]]],
    ) -> str:
        """构建发送给 LLM 的提示词。

        Args:
            locations: 定位结果列表。
            conflicts: 冲突检测结果列表。
            arbitrations: 仲裁结果列表。

        Returns:
            完整的提示词字符串。
        """
        prompt_parts: list[str] = [
            "报告生成任务：请基于以下分析结果生成合规审查报告。\n",
            "=== 定位结果 ===",
            json.dumps(locations, ensure_ascii=False, indent=2),
            "\n=== 冲突检测结果 ===",
            json.dumps(conflicts, ensure_ascii=False, indent=2),
        ]

        if arbitrations:
            prompt_parts.extend([
                "\n=== 仲裁结果 ===",
                json.dumps(arbitrations, ensure_ascii=False, indent=2),
            ])

        prompt_parts.append(
            "\n请综合以上信息，输出 JSON 格式的合规审查报告："
            "summary, risk_level, recommendations, evidence_count"
        )

        return "\n".join(prompt_parts)

    def _rule_based_report(
        self,
        locations: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        arbitrations: Optional[list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """基于规则的报告生成方法（兜底方案）。

        Args:
            locations: 定位结果列表。
            conflicts: 冲突检测结果列表。
            arbitrations: 仲裁结果列表。

        Returns:
            合规审查报告字典。
        """
        risk_count = sum(1 for loc in locations if loc.get("has_risk"))
        all_labels: list[str] = []
        for loc in locations:
            all_labels.extend(loc.get("risk_labels", []))

        if risk_count > 3 or len(conflicts) > 2:
            risk_level = "high"
        elif risk_count > 1 or len(conflicts) > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        unique_labels = list(set(all_labels))
        summary = f"经合规审查，共发现 {risk_count} 个风险点，{len(conflicts)} 个条款冲突"
        if unique_labels:
            summary += f"，涉及领域：{'、'.join(unique_labels[:5])}"

        recommendations: list[str] = [
            "建议对识别的风险条款进行修订",
            "建议引入专业法律顾问复核",
        ]
        if risk_level == "high":
            recommendations.insert(0, "建议立即暂停相关业务流程")
        if conflicts:
            recommendations.append("建议统一矛盾条款的表述和标准")

        return {
            "summary": summary,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "evidence_count": risk_count + len(conflicts),
        }
