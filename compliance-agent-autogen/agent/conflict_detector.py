"""冲突检测 Agent：检测条款矛盾。"""

import json
import re
from typing import Any, Optional

from config import AGENT_CONFIG, MOCK_MODE, MODEL_NAME, OPENAI_API_KEY


class MockLLM:
    """冲突检测模拟 LLM（复用独立实例以避免与定位 Agent 混淆）。"""

    def __init__(self) -> None:
        """初始化 MockLLM。"""
        self.call_count: int = 0
        self.total_tokens: int = 0

    def run(self, prompt: str) -> str:
        """模拟冲突检测推理。

        Args:
            prompt: 输入提示词。

        Returns:
            模拟的冲突检测结果 JSON 字符串。
        """
        self.call_count += 1
        estimated_tokens = len(prompt) // 4 + 80
        self.total_tokens += estimated_tokens
        return self._detect_mock_conflicts(prompt)

    def _detect_mock_conflicts(self, prompt: str) -> str:
        """基于规则的模拟冲突检测。

        Args:
            prompt: 包含多个文档切片内容的提示词。

        Returns:
            冲突列表的 JSON 字符串。
        """
        conflicts: list[dict[str, Any]] = []

        time_pattern = re.compile(r"(\d+)\s*[天日个月周]")
        time_matches = time_pattern.findall(prompt)
        if len(time_matches) >= 2:
            unique_periods = list(set(time_matches))
            if len(unique_periods) >= 2:
                conflicts.append({
                    "clause_a": f"通知期限条款（{unique_periods[0]}天）",
                    "clause_b": f"通知期限条款（{unique_periods[1]}天）",
                    "conflict_type": "时间矛盾",
                    "description": (
                        f"不同条款中关于通知/响应期限的规定存在矛盾："
                        f"{unique_periods[0]}天 vs {unique_periods[1]}天，"
                        "可能导致合同履行中的时限争议"
                    ),
                })

        prohibitive = re.findall(r"(不得|禁止|严禁)\s*[\u4e00-\u9fff]+", prompt)
        permissive = re.findall(r"(可以|有权|允许|许可)\s*[\u4e00-\u9fff]+", prompt)
        if prohibitive and permissive:
            conflicts.append({
                "clause_a": f"禁止性条款（{prohibitive[0]}...）",
                "clause_b": f"授权性条款（{permissive[0]}...）",
                "conflict_type": "权限矛盾",
                "description": "部分条款禁止某些行为，而其他条款又授权了相应行为，存在逻辑冲突",
            })

        definition_patterns = re.findall(
            r"(?:是指|定义为|指的[是是])\s*[：:]*\s*([^\n。；]+)",
            prompt,
        )
        if len(definition_patterns) >= 2:
            conflicts.append({
                "clause_a": f"定义条款A（{definition_patterns[0][:20]}...）",
                "clause_b": f"定义条款B（{definition_patterns[1][:20]}...）",
                "conflict_type": "定义矛盾",
                "description": "同一术语在不同条款中的定义存在差异，可能导致解释歧义",
            })

        if not conflicts:
            conflicts.append({
                "clause_a": "通用条款A",
                "clause_b": "通用条款B",
                "conflict_type": "潜在矛盾",
                "description": "经分析，各条款间存在潜在的解释不一致风险，建议人工复核",
            })

        return json.dumps(conflicts, ensure_ascii=False)


class ConflictDetectorAgent:
    """冲突检测 Agent：检测不同条款之间的矛盾点。

    该 Agent 接收多个已标注合规风险的文档切片，
    分析它们之间是否存在时间矛盾、权限矛盾、定义矛盾等冲突。
    """

    def __init__(self, mock_mode: Optional[bool] = None) -> None:
        """初始化冲突检测 Agent。

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
                "temperature": AGENT_CONFIG["conflict_detector"]["temperature"],
                "max_tokens": AGENT_CONFIG["conflict_detector"]["max_tokens"],
            }

            self.autogen_agent = autogen.AssistantAgent(
                name="ConflictDetectorAgent",
                system_message=(
                    "你是一名专业的法律冲突检测专家。你的任务是分析多个合同条款之间"
                    "是否存在矛盾。请严格按照 JSON 数组格式输出冲突列表：\n"
                    '[{"clause_a": str, "clause_b": str, '
                    '"conflict_type": str, "description": str}]\n'
                    "冲突类型包括：时间矛盾、权限矛盾、定义矛盾、责任矛盾等。"
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

    def detect_conflicts(
        self,
        chunks_with_labels: list[dict],
    ) -> list[dict[str, Any]]:
        """检测多个文档切片之间的条款矛盾。

        Args:
            chunks_with_labels: 已标注风险的文档切片列表，
                每个元素应包含 chunk_id, title, content, risk_labels 等字段。

        Returns:
            冲突列表，每个元素包含 clause_a, clause_b, conflict_type, description。
        """
        if not chunks_with_labels:
            return []

        if self.mock_mode and self.llm:
            combined_text = ""
            for chunk in chunks_with_labels:
                combined_text += f"\n--- 切片 {chunk.get('chunk_id', '?')} ---\n"
                combined_text += f"标题：{chunk.get('title', 'N/A')}\n"
                combined_text += f"风险标签：{chunk.get('risk_labels', [])}\n"
                combined_text += f"内容：{chunk.get('content', '')}\n"

            prompt = (
                f"冲突检测任务：请分析以下{len(chunks_with_labels)}个合规相关段落，"
                f"检测其中是否存在条款矛盾。\n{combined_text}\n"
                "请输出 JSON 数组格式的冲突列表。"
            )
            response = self.llm.run(prompt)
            try:
                result = json.loads(response)
                self.token_count = self.llm.total_tokens
                if isinstance(result, list):
                    return result
                return [result]
            except json.JSONDecodeError:
                pass

        return self._rule_based_detect(chunks_with_labels)

    def _rule_based_detect(
        self,
        chunks: list[dict],
    ) -> list[dict[str, Any]]:
        """基于规则的冲突检测（兜底方案）。

        Args:
            chunks: 已标注风险的文档切片列表。

        Returns:
            冲突列表。
        """
        conflicts: list[dict[str, Any]] = []
        all_text = " ".join(c.get("content", "") for c in chunks)

        time_pattern = re.compile(r"(\d+)\s*[天日个月周]")
        time_matches = time_pattern.findall(all_text)
        if len(set(time_matches)) >= 2:
            unique_times = list(set(time_matches))
            conflicts.append({
                "clause_a": f"期限条款（{unique_times[0]}天）",
                "clause_b": f"期限条款（{unique_times[1]}天）",
                "conflict_type": "时间矛盾",
                "description": f"不同条款中的期限存在差异：{unique_times[0]}天 vs {unique_times[1]}天",
            })

        return conflicts if conflicts else []
