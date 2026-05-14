"""定位 Agent：识别合规相关段落。"""

import json
import re
from typing import Any, Optional

from config import AGENT_CONFIG, COMPLIANCE_KEYWORDS, MOCK_MODE, MODEL_NAME, OPENAI_API_KEY


class MockLLM:
    """模拟 LLM 推理，在无 API Key 时提供完整的流程演示。

    该类模拟 LLM 的响应行为，通过关键词匹配和规则引擎
    生成与真实 LLM 相同格式的输出，用于测试和演示。
    """

    def __init__(self) -> None:
        """初始化 MockLLM。"""
        self.call_count: int = 0
        self.total_tokens: int = 0

    def run(self, prompt: str) -> str:
        """模拟 LLM 推理过程。

        Args:
            prompt: 输入提示词。

        Returns:
            模拟的 LLM 响应文本。
        """
        self.call_count += 1
        estimated_tokens = len(prompt) // 4 + 50
        self.total_tokens += estimated_tokens

        if "定位" in prompt or "合规" in prompt or "风险" in prompt:
            return self._mock_locator_response(prompt)
        elif "冲突" in prompt or "矛盾" in prompt:
            return self._mock_conflict_response(prompt)
        elif "仲裁" in prompt or "裁决" in prompt:
            return self._mock_arbiter_response(prompt)
        elif "报告" in prompt or "结论" in prompt or "总结" in prompt:
            return self._mock_conclusion_response(prompt)
        return json.dumps({"status": "mock_response"}, ensure_ascii=False)

    def _mock_locator_response(self, prompt: str) -> str:
        """生成定位 Agent 的模拟响应。"""
        content_part = prompt
        content_marker = "内容："
        marker_idx = prompt.find(content_marker)
        if marker_idx != -1:
            content_part = prompt[marker_idx + len(content_marker):]

        matched_keywords = []
        for kw in COMPLIANCE_KEYWORDS:
            if kw in content_part:
                matched_keywords.append(kw)

        has_risk = len(matched_keywords) > 0
        confidence = min(0.6 + len(matched_keywords) * 0.08, 0.95)

        relevant_snippets: list[str] = []
        for kw in matched_keywords[:3]:
            idx = content_part.find(kw)
            start = max(0, idx - 30)
            end = min(len(content_part), idx + len(kw) + 30)
            relevant_snippets.append(content_part[start:end].replace("\n", " ").strip())

        result = {
            "has_risk": has_risk,
            "risk_labels": matched_keywords[:5] if has_risk else [],
            "relevant_text": "；".join(relevant_snippets) if relevant_snippets else "",
            "confidence": round(confidence, 2),
        }
        return json.dumps(result, ensure_ascii=False)

    def _mock_conflict_response(self, prompt: str) -> str:
        """生成冲突检测 Agent 的模拟响应。"""
        conflicts: list[dict[str, Any]] = []

        time_pattern = re.compile(r"(\d+)\s*[天日]")
        time_matches = time_pattern.findall(prompt)
        if len(set(time_matches)) >= 2:
            unique_times = list(set(time_matches))
            conflicts.append({
                "clause_a": f"期限条款（{unique_times[0]}天）",
                "clause_b": f"期限条款（{unique_times[1]}天）",
                "conflict_type": "时间矛盾",
                "description": f"不同条款中关于期限的规定存在矛盾：{unique_times[0]}天 vs {unique_times[1]}天",
            })

        perm_keywords = ["授权", "许可", "禁止", "不得", "应当"]
        found_perms = [kw for kw in perm_keywords if kw in prompt]
        if len(found_perms) >= 2:
            conflicts.append({
                "clause_a": f"权限条款（包含：{found_perms[0]}）",
                "clause_b": f"权限条款（包含：{found_perms[1]}）",
                "conflict_type": "权限矛盾",
                "description": f"不同条款中对权限的规定可能存在冲突：{found_perms[0]} vs {found_perms[1]}",
            })

        if not conflicts:
            conflicts.append({
                "clause_a": "条款A",
                "clause_b": "条款B",
                "conflict_type": "定义矛盾",
                "description": "不同条款中的术语定义存在差异，可能导致解释歧义",
            })

        return json.dumps(conflicts, ensure_ascii=False)

    def _mock_arbiter_response(self, prompt: str) -> str:
        """生成仲裁 Agent 的模拟响应。"""
        result = {
            "decision": "依据法规优先级，国家法律条款优先于合同条款，应以法律规定的时限和条件为准",
            "priority_basis": "国际法 > 国家法律 > 行业规范 > 合同条款",
            "final_confidence": 0.82,
        }
        return json.dumps(result, ensure_ascii=False)

    def _mock_conclusion_response(self, prompt: str) -> str:
        """生成结论 Agent 的模拟响应。"""
        risk_level = "medium"
        if "高风险" in prompt or "严重" in prompt:
            risk_level = "high"
        elif "低风险" in prompt or "轻微" in prompt:
            risk_level = "low"

        result = {
            "summary": "经多 Agent 协作审查，该文档存在合规风险点，建议重点关注数据隐私和违约责任相关条款",
            "risk_level": risk_level,
            "recommendations": [
                "建议修订数据隐私相关条款，确保符合《个人信息保护法》要求",
                "建议统一各条款中关于通知时限的规定，避免矛盾",
                "建议增加跨境数据传输的合规审查流程",
                "建议对违约责任条款进行重新评估，确保与行业规范一致",
            ],
            "evidence_count": prompt.count("风险") + prompt.count("冲突") + 2,
        }
        return json.dumps(result, ensure_ascii=False)


class LocatorAgent:
    """定位 Agent：扫描文档切片，识别合规相关段落。

    该 Agent 负责从文档切片中定位合规风险点，
    输出风险标签、相关文本片段和置信度评分。
    """

    def __init__(self, mock_mode: Optional[bool] = None) -> None:
        """初始化定位 Agent。

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
                "temperature": AGENT_CONFIG["locator"]["temperature"],
                "max_tokens": AGENT_CONFIG["locator"]["max_tokens"],
            }

            self.autogen_agent = autogen.AssistantAgent(
                name="LocatorAgent",
                system_message=(
                    "你是一名专业的合规审查定位专家。你的任务是扫描文档段落，"
                    "识别其中是否存在合规风险。请严格按照 JSON 格式输出：\n"
                    '{"has_risk": bool, "risk_labels": List[str], '
                    '"relevant_text": str, "confidence": float}'
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

    def locate(
        self,
        doc_chunk: dict,
        compliance_keywords: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """扫描文档切片，识别合规相关段落。

        Args:
            doc_chunk: 文档切片，包含 chunk_id, title, content, page_number。
            compliance_keywords: 自定义合规关键词列表，默认使用配置文件中的列表。

        Returns:
            包含 has_risk, risk_labels, relevant_text, confidence 的字典。
        """
        keywords = compliance_keywords or COMPLIANCE_KEYWORDS
        content = doc_chunk.get("content", "")
        title = doc_chunk.get("title", "")

        if self.mock_mode and self.llm:
            prompt = (
                f"定位任务：请分析以下文档段落是否存在合规风险。\n"
                f"标题：{title}\n"
                f"合规关键词：{', '.join(keywords)}\n"
                f"内容：{content}\n"
                f"请输出 JSON 格式：has_risk, risk_labels, relevant_text, confidence"
            )
            response = self.llm.run(prompt)
            try:
                result = json.loads(response)
                self.token_count = self.llm.total_tokens
                return result
            except json.JSONDecodeError:
                pass

        return self._rule_based_locate(content, keywords, title)

    def _rule_based_locate(
        self,
        content: str,
        keywords: list[str],
        title: str,
    ) -> dict[str, Any]:
        """基于规则的定位方法（兜底方案）。

        当 LLM 不可用时，使用关键词匹配规则进行定位。

        Args:
            content: 文档内容。
            keywords: 合规关键词列表。
            title: 文档标题。

        Returns:
            定位结果字典。
        """
        matched_keywords: list[str] = []
        relevant_text_parts: list[str] = []

        for kw in keywords:
            if kw in content:
                matched_keywords.append(kw)
                idx = content.find(kw)
                start = max(0, idx - 40)
                end = min(len(content), idx + len(kw) + 40)
                snippet = content[start:end].replace("\n", " ").strip()
                relevant_text_parts.append(snippet)

        has_risk = len(matched_keywords) > 0
        confidence = min(0.5 + len(matched_keywords) * 0.1, 0.95) if has_risk else 0.1

        return {
            "has_risk": has_risk,
            "risk_labels": matched_keywords,
            "relevant_text": "；".join(relevant_text_parts),
            "confidence": round(confidence, 2),
        }
