"""仲裁 Agent：裁决冲突。"""

import json
from typing import Any, Optional

from config import AGENT_CONFIG, MOCK_MODE, MODEL_NAME, OPENAI_API_KEY, REGULATION_HIERARCHY


class MockLLM:
    """仲裁模拟 LLM。"""

    def __init__(self) -> None:
        """初始化 MockLLM。"""
        self.call_count: int = 0
        self.total_tokens: int = 0

    def run(self, prompt: str) -> str:
        """模拟仲裁推理。

        Args:
            prompt: 输入提示词。

        Returns:
            模拟的仲裁结果 JSON 字符串。
        """
        self.call_count += 1
        estimated_tokens = len(prompt) // 4 + 60
        self.total_tokens += estimated_tokens
        return self._mock_arbitrate(prompt)

    def _mock_arbitrate(self, prompt: str) -> str:
        """生成模拟仲裁响应。

        Args:
            prompt: 包含冲突信息和法规优先级的提示词。

        Returns:
            仲裁结果 JSON 字符串。
        """
        decision = "经仲裁分析，依据法规优先级原则，应以较高级别的法规规定为准"
        priority_basis = " > ".join(
            k for k, _ in sorted(
                REGULATION_HIERARCHY.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

        if "时间" in prompt:
            decision = "经仲裁分析，关于时限矛盾，应以国家法律规定的时限为准，合同条款不得低于法定最低标准"
        elif "权限" in prompt:
            decision = "经仲裁分析，关于权限矛盾，禁止性规定优先于授权性规定，以确保合规安全"
        elif "定义" in prompt:
            decision = "经仲裁分析，关于定义矛盾，应以法律层面的定义为准，合同自定义不得与法律定义冲突"

        result = {
            "decision": decision,
            "priority_basis": priority_basis,
            "final_confidence": 0.82,
        }
        return json.dumps(result, ensure_ascii=False)


class ArbiterAgent:
    """仲裁 Agent：当冲突检测到矛盾时，根据法规优先级裁决。

    法规优先级：国际法 > 国家法律 > 行业规范 > 合同条款。
    该 Agent 根据优先级层级对冲突做出裁决，输出决策依据和置信度。
    """

    def __init__(self, mock_mode: Optional[bool] = None) -> None:
        """初始化仲裁 Agent。

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
                "temperature": AGENT_CONFIG["arbiter"]["temperature"],
                "max_tokens": AGENT_CONFIG["arbiter"]["max_tokens"],
            }

            self.autogen_agent = autogen.AssistantAgent(
                name="ArbiterAgent",
                system_message=(
                    "你是一名专业的合规仲裁专家。当合同条款之间存在矛盾时，"
                    "你需要根据法规优先级进行裁决。优先级从高到低为："
                    "国际法 > 国家法律 > 行业规范 > 合同条款。\n"
                    "请严格按照 JSON 格式输出：\n"
                    '{"decision": str, "priority_basis": str, "final_confidence": float}'
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

    def arbitrate(
        self,
        conflict: dict[str, Any],
        regulation_hierarchy: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """对检测到的冲突进行仲裁裁决。

        Args:
            conflict: 冲突信息字典，包含 clause_a, clause_b, conflict_type, description。
            regulation_hierarchy: 自定义法规优先级字典，默认使用配置文件中的。

        Returns:
            包含 decision, priority_basis, final_confidence 的字典。
        """
        hierarchy = regulation_hierarchy or REGULATION_HIERARCHY

        if self.mock_mode and self.llm:
            prompt = (
                f"仲裁任务：请对以下冲突进行裁决。\n"
                f"冲突类型：{conflict.get('conflict_type', '未知')}\n"
                f"条款A：{conflict.get('clause_a', 'N/A')}\n"
                f"条款B：{conflict.get('clause_b', 'N/A')}\n"
                f"冲突描述：{conflict.get('description', 'N/A')}\n"
                f"法规优先级：{hierarchy}\n"
                "请依据法规优先级做出裁决，输出 JSON 格式："
                "decision, priority_basis, final_confidence"
            )
            response = self.llm.run(prompt)
            try:
                result = json.loads(response)
                self.token_count = self.llm.total_tokens
                return result
            except json.JSONDecodeError:
                pass

        return self._rule_based_arbitrate(conflict, hierarchy)

    def _rule_based_arbitrate(
        self,
        conflict: dict[str, Any],
        hierarchy: dict[str, int],
    ) -> dict[str, Any]:
        """基于规则的仲裁方法（兜底方案）。

        Args:
            conflict: 冲突信息。
            hierarchy: 法规优先级字典。

        Returns:
            仲裁结果字典。
        """
        conflict_type = conflict.get("conflict_type", "")
        sorted_hierarchy = sorted(
            hierarchy.items(), key=lambda x: x[1], reverse=True
        )
        priority_basis = " > ".join(k for k, _ in sorted_hierarchy)

        decision_map = {
            "时间矛盾": "关于时限矛盾，应以国家法律规定的时限为准，合同条款不得低于法定标准",
            "权限矛盾": "关于权限矛盾，禁止性规定优先于授权性规定，确保合规安全",
            "定义矛盾": "关于定义矛盾，应以法律层面的定义为准，合同自定义不得与法律冲突",
            "责任矛盾": "关于责任矛盾，应以对消费者/数据主体更有利的规定为准",
        }

        decision = decision_map.get(
            conflict_type,
            "依据法规优先级原则，应以较高级别的法规规定为准",
        )

        return {
            "decision": decision,
            "priority_basis": priority_basis,
            "final_confidence": 0.78,
        }
