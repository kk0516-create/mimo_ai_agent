import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"

AGENT_CONFIG: dict = {
    "locator": {
        "temperature": 0.2,
        "max_tokens": 1024,
    },
    "conflict_detector": {
        "temperature": 0.1,
        "max_tokens": 2048,
    },
    "conclusion": {
        "temperature": 0.3,
        "max_tokens": 2048,
    },
    "arbiter": {
        "temperature": 0.0,
        "max_tokens": 1024,
    },
}

COMPLIANCE_KEYWORDS: list[str] = [
    "数据隐私",
    "保密协议",
    "违约责任",
    "GDPR",
    "个人信息保护法",
    "数据安全法",
    "网络安全法",
    "跨境数据传输",
    "知情同意",
    "数据脱敏",
    "敏感信息",
    "合规义务",
    "审计",
    "处罚",
    "赔偿责任",
    "知识产权",
    "竞业限制",
    "不可抗力",
    "解除合同",
    "争议解决",
]

REGULATION_HIERARCHY: dict[str, int] = {
    "国际法": 4,
    "国家法律": 3,
    "行业规范": 2,
    "合同条款": 1,
}

PROJECT_ROOT: Path = Path(__file__).parent
