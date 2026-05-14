# 长文档合规审查多 Agent 系统

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AutoGen](https://img.shields.io/badge/AutoGen-0.2%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Mock Mode](https://img.shields.io/badge/Mock_Mode-Supported-orange)

## 核心痛点

在金融和法律行业中，长文档（合同、法规、协议）的合规审查面临以下挑战：

- **文档冗长**：动辄数百页的合同，人工审查耗时且易遗漏
- **条款矛盾**：不同章节/条款间的矛盾难以系统性发现
- **法规更新**：法规频繁更新，人工难以保证审查依据的时效性
- **专业门槛高**：合规审查需要法律+领域知识，人才稀缺
- **效率低下**：传统审查流程线性推进，无法并行处理

本系统通过多 Agent 协作，将审查任务分解为定位、冲突检测、仲裁、结论四个环节，大幅提升审查效率和准确性。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    合规审查流水线                          │
│                  ComplianceReviewPipeline                  │
└──────────┬──────────┬──────────┬──────────┬──────────────┘
           │          │          │          │
     ┌─────▼─────┐ ┌──▼──────┐ ┌▼────────┐ ┌▼────────────┐
     │  PDF 解析  │ │ 定位    │ │ 冲突    │ │ 仲裁 / 结论 │
     │  Parser    │ │ Agent   │ │ 检测    │ │   Agent     │
     └─────┬─────┘ └──┬──────┘ └┬────────┘ └┬────────────┘
           │          │         │            │
     ┌─────▼─────┐ ┌──▼──────┐ │      ┌─────▼─────┐
     │ PDF→MD    │ │ 风险    │ │      │  裁决 /    │
     │ 语义切片  │ │ 定位    │ │      │  报告生成  │
     └───────────┘ └─────────┘ │      └───────────┘
                           ┌───▼───────┐
                           │ 条款矛盾  │
                           │ 检测      │
                           └───────────┘
```

## 多 Agent 协作流程

```
PDF 文件
  │
  ▼
┌──────────────────┐
│  PDFToMarkdown   │  1. 解析 PDF，转为 Markdown
│  Parser          │  2. 按章节/条款语义切片
└────────┬─────────┘
         │  List[Chunk]
         ▼
┌──────────────────┐
│  LocatorAgent    │  3. 对每个切片进行合规风险定位
│  (定位 Agent)    │     输出：has_risk, risk_labels, confidence
└────────┬─────────┘
         │  筛选有风险的切片
         ▼
┌──────────────────────┐
│  ConflictDetector    │  4. 检测有风险切片间的条款矛盾
│  Agent (冲突检测)    │     输出：conflict_type, clause_a, clause_b
└────────┬─────────────┘
         │  如有冲突
         ▼
┌──────────────────┐
│  ArbiterAgent    │  5. 根据法规优先级裁决冲突
│  (仲裁 Agent)    │     优先级：国际法 > 国家法律 > 行业规范 > 合同条款
└────────┬─────────┘
         │  仲裁结果
         ▼
┌──────────────────┐
│  ConclusionAgent │  6. 汇总所有分析结果，生成最终合规报告
│  (结论 Agent)    │     输出：summary, risk_level, recommendations
└────────┬─────────┘
         │
         ▼
   合规审查报告
```

## 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd compliance-agent-autogen

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 文件，填入 OPENAI_API_KEY
```

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 空 |
| `MODEL_NAME` | 使用的模型名称 | `gpt-3.5-turbo` |
| `MOCK_MODE` | 是否使用 Mock 模式 | `true` |

## 使用示例

### 1. 演示模式（无需 API Key）

```bash
python demo/sample_inference.py
```

### 2. 审查 PDF 文件（Mock 模式）

```bash
python main.py --pdf path/to/document.pdf --mock
```

### 3. 审查 PDF 文件（LLM 模式，需要 API Key）

```bash
python main.py --pdf path/to/document.pdf --no-mock
```

### 4. 输出报告到文件

```bash
python main.py --pdf path/to/document.pdf --mock --output report.json
```

### 5. 运行测试

```bash
python -m pytest tests/ -v
```

## 落地数据（预期效果）

| 指标 | 人工审查 | 本系统 |
|------|---------|--------|
| 审查速度 | 2-4 小时/份 | 5-15 分钟/份 |
| 风险检出率 | ~70% | ~85% |
| 冲突识别率 | ~50% | ~80% |
| 误报率 | ~10% | ~15% |
| 人力成本 | 高（需专业人员） | 低（辅助决策） |

> 注：以上数据为预期效果，实际效果取决于文档复杂度和 LLM 模型质量。

## Token 消耗说明

| Agent | 单次调用预估 Token | 说明 |
|-------|-------------------|------|
| 定位 Agent | ~500-1500 | 每个切片调用一次 |
| 冲突检测 Agent | ~1000-3000 | 每组风险切片调用一次 |
| 仲裁 Agent | ~500-1000 | 每个冲突调用一次 |
| 结论 Agent | ~1000-2000 | 最终调用一次 |
| **总计（50页文档）** | **~5000-15000** | Mock 模式无实际消耗 |

基于 GPT-3.5-turbo 定价（$0.0015/1K tokens），50页文档的审查费用约 **$0.01-$0.02**。

## 申请更高额度的理由

1. **社会价值**：合规审查直接影响金融安全和用户权益，更高的额度能支持更大规模文档的审查，减少合规风险遗漏
2. **研究价值**：本系统探索多 Agent 协作在专业领域的应用范式，可为 AI Agent 领域提供有价值的实践参考
3. **效率提升**：自动化审查可释放大量专业人力资源，使其专注于更高价值的判断工作
4. **持续优化**：更高的额度支持更频繁的测试和迭代，有助于持续提升系统准确性和稳定性

## 项目结构

```
compliance-agent-autogen/
├── agent/
│   ├── __init__.py
│   ├── locator.py           # 定位 Agent：识别合规相关段落
│   ├── conflict_detector.py # 冲突检测 Agent：检测条款矛盾
│   ├── conclusion.py        # 结论生成 Agent：输出风险报告
│   └── arbiter.py           # 仲裁 Agent：裁决冲突
├── parser/
│   ├── __init__.py
│   └── pdf_to_md.py         # PDF 转 Markdown 解析器
├── demo/
│   └── sample_inference.py  # 演示推理脚本
├── tests/
│   └── test_agents.py       # 单元测试
├── config.py                # 配置文件
├── main.py                  # 主入口文件
├── requirements.txt         # 依赖列表
└── README.md                # 项目说明文档
```

## License

MIT
