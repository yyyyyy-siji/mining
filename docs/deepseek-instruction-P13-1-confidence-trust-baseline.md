# DeepSeek 执行指令：P13-1 置信度可信基线与伪向量熔断

## 任务目标

停止系统继续输出或利用误导性的“置信度”和伪语义结论。本阶段只建立安全基线，不实施真正的概率校准、Embedding选型、去重算法重写或历史数据批量清洗。

完整路线参考：`docs/development-taskbook-P13-confidence-source-multimodal.md`。

## 背景 / 当前问题

1. `SignalRow.confidence`来自LLM自评，没有人工金标校准，却在前端显示为百分比，并用于筛选和去重保留决策。
2. 默认DeepSeek不支持Embedding，当前fallback生成80% signal_type + 20%文本哈希的伪向量。
3. 当前数据库1,425条信号全部使用`deepseek_pseudo_embedding`，其中1,408条为dismissed。
4. 当前17个主题全部是单信号主题。
5. 当前代码没有强制验证signalType属于Profile白名单，也没有程序化验证evidence确实来自原文。

本阶段最高优先级是“诚实表达不确定性”和“阻止新的错误dismiss”，不是让结果看起来更漂亮。

## 执行前检查

工作区存在未提交改动。开始前必须执行并在报告中保存：

```bash
git status --short
git diff --stat
```

不得覆盖、回滚或格式化无关用户改动。

## 允许修改范围

- `signal_miner/models/feedback.py`
- `signal_miner/db/models.py`
- `signal_miner/pipeline/extraction.py`
- `signal_miner/pipeline/embedding.py`
- `signal_miner/pipeline/deduplication.py`
- `signal_miner/pipeline/clustering.py`
- `signal_miner/pipeline/runner.py`
- `signal_miner/routes/signals.py`
- `signal_miner/routes/pipeline.py`
- `signal_miner/settings.py`
- `alembic/versions/` 中新增本阶段迁移
- `frontend/static/app.js`
- `frontend/static/style.css`
- `frontend/app.py`
- 本阶段新增或修改的聚焦测试
- `scripts/` 下新增P13-1只读验收脚本
- `docs/P13-1-evidence/`
- `docs/P13-1-screenshots/`
- `docs/acceptance-P13-1-delivery-YYYYMMDD.md`

如确需修改其他文件，必须先在交付报告中列出理由；不得以此授权修改数据来源连接器、PRD生成器或资产生成逻辑。

## 禁止修改范围

- 不得修改P13-2及后续任务书。
- 不得引入或选择新的真实Embedding模型；那属于P13-3。
- 不得声称模型置信度已经校准。
- 不得批量删除、恢复、重新dismiss当前1,425条历史信号。
- 不得物理删除原始反馈、信号、主题或证据链。
- 不得通过降低测试断言、删除历史测试或把失败标成skip来获得全绿。
- 不得让伪Embedding继续进入正式去重、聚类或相似检索。
- 不得把“跳过语义阶段”伪装成“pipeline全部成功”。

## 实现要求

### 1. 建立置信度语义契约

保留旧`confidence`兼容读取，但新增并结构化表达：

- `model_self_score`: LLM原始自评分数，0–1。
- `calibrated_confidence`: 校准概率，本阶段必须为`null`。
- `confidence_method`: 本阶段固定为`llm_self_reported`或明确兼容值。
- `confidence_model_version`: 至少包含provider/model/prompt version可追踪信息。
- `evidence_validation_status`: `verified` / `partial` / `invalid` / `not_checked`。

具体列名可按现有架构调整，但API必须能表达以上语义。迁移必须保留原`confidence`数值，不得把旧值自动写成已校准概率。

### 2. 强制SignalType白名单

- 使用当前PipelineProfile的`signal_types`验证LLM输出。
- 非法类型不得作为有效信号入库。
- 处理策略必须可审计：记录被拒绝类型、原始输出和原因，但注意原始输出大小与敏感信息。
- 产品反馈类型不得进入AIGC视频profile，反之亦然。

### 3. 验证Evidence原文一致性

- 对LLM返回的每条evidence做确定性原文匹配。
- 最低要求支持Unicode规范化、首尾空白规范化；不得进行会把改写误认为原文的宽松语义匹配。
- 全部匹配为`verified`；部分匹配为`partial`；全部不匹配为`invalid`。
- invalid evidence不得在前端显示为“已验证原文证据”。
- 不得悄悄改写模型quote使其看起来匹配。

### 4. 熔断伪Embedding语义决策

- 正式pipeline发现adapter不支持Embedding时，不再生成伪向量。
- 旧`*_pseudo_embedding`记录不得参与deduplication、clustering和similar search。
- 语义阶段应返回结构化状态，例如`blocked_no_real_embedding`或`skipped_no_real_embedding`。
- Pipeline最终状态必须区分：文本提取完成、语义去重/聚类未执行。
- 本阶段不得因为语义阶段被跳过而dismiss任何新信号。
- 测试环境如需伪向量，必须显式test-only，且不允许被生产配置启用。

### 5. 取消未校准分数的破坏性决策

- 去重保留者不得再仅凭LLM自评分数决定。
- 本阶段由于真实Embedding尚未完成，应阻止正式自动dismiss，而不是设计临时新算法。
- 保留历史状态不变；只阻止新增错误状态。

### 6. API和前端诚实展示

- 信号API同时返回模型自评、校准值、方法和evidence验证状态。
- 兼容旧`confidence`字段，但文档标记deprecated/legacy semantics。
- 静态SPA和Streamlit将无修饰“置信度XX%”改成“模型自评 0.xx（未校准）”。
- 若`calibrated_confidence`为空，不得显示百分比准确率含义。
- Pipeline页面明确显示“文本提取已完成；语义去重/聚类因未配置真实Embedding而跳过”。

### 7. 只读基线证据脚本

新增可复跑脚本，至少输出：

- 信号总数。
- 按embedding_model计数。
- 按processing_state计数。
- pseudo embedding数量。
- dismissed数量。
- 主题总数及单例主题率。
- P13-1运行前后新产生的pseudo/dismissed数量。

脚本不得修改数据库。

输出：`docs/P13-1-evidence/metrics.json`。

顶层`passed`必须至少依赖：

- `confidence_contract.passed`
- `signal_type_validation.passed`
- `evidence_validation.passed`
- `pseudo_embedding_blocked.passed`
- `no_new_destructive_dismiss.passed`
- `frontend_semantics.passed`
- `regression.passed`

任一字段缺失或false时，顶层不得为true。

## 验收标准

### 数据与迁移验收

1. Alembic升级、回滚、再次升级均成功。
2. 迁移前后RawFeedback、Signal、Theme总数守恒。
3. 旧confidence数值保留，但`calibrated_confidence`不得被伪填充。
4. 历史1,408条dismissed记录本阶段不自动变化。

### 功能验收

必须新增测试覆盖：

1. LLM返回`confidence=0.99`：
   - `model_self_score=0.99`；
   - `calibrated_confidence is None`；
   - `confidence_method=llm_self_reported`。
2. LLM在product profile返回`viral_hook`：不得入库为有效信号。
3. LLM返回原文不存在的quote：状态为invalid，不能显示为已验证证据。
4. LLM返回一真一假quote：状态为partial。
5. DeepSeek不支持Embedding：
   - 不生成pseudo向量；
   - 不调用dedup/cluster；
   - 不新增dismissed；
   - pipeline结果明确标记语义阶段skipped/blocked。
6. 旧pseudo记录不会被`find_similar_signals`返回。
7. 两种profile的signalType白名单互相隔离。

### 前端运行态验收

启动本地服务，用浏览器验证并保存截图：

- 信号卡片显示“模型自评（未校准）”，不显示裸“置信度XX%”。
- Pipeline结果显示语义阶段被跳过的真实原因。
- DeepSeek主模型和多模态模型状态卡仍正常显示。
- 原始来源按钮、证据链、AIGC模式未消失。

证据保存到`docs/P13-1-screenshots/`，报告必须说明检查的具体DOM区域和页面URL。

### 语法 / 静态检查

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
git diff --check
```

### 聚焦测试

```bash
.venv/bin/python -m pytest tests/test_confidence_contract.py tests/test_evidence_validation.py tests/test_embedding_safety.py -q
```

测试文件名如因项目结构调整可变化，但交付报告必须列出等价测试与逐项覆盖关系。

### 回归验证

```bash
.venv/bin/python -m pytest -q
```

### 迁移验证

必须在临时数据库副本上运行，不得直接拿唯一生产数据库做破坏性回滚：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### 机器证据断言

交付前必须执行等价断言：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

p = Path("docs/P13-1-evidence/metrics.json")
data = json.loads(p.read_text())
required = [
    "confidence_contract",
    "signal_type_validation",
    "evidence_validation",
    "pseudo_embedding_blocked",
    "no_new_destructive_dismiss",
    "frontend_semantics",
    "regression",
]
assert all(name in data["checks"] for name in required)
assert all(data["checks"][name]["passed"] is True for name in required)
assert data["passed"] is True
print("P13-1 machine gates passed")
PY
```

## 交付前质量门禁

- 每条命令必须记录退出码。
- 不能只运行新增测试；必须运行全量pytest。
- 浏览器检查必须针对本次启动的本地服务，不得检查旧页面或错误端口。
- 如果迁移、浏览器或外部环境无法验证，结论只能是BLOCKED。
- `metrics.json`与Markdown报告数值必须一致。
- 报告中不得出现“置信度已校准”“语义去重已修复”“聚类已可信”等超出本阶段范围的结论。

## 交付报告模板

```markdown
# P13-1 交付报告：置信度可信基线与伪向量熔断

交付日期：YYYY-MM-DD

## 结论

- 自评：PASS / FAIL / BLOCKED
- 机器证据：docs/P13-1-evidence/metrics.json

## 修改文件

| 文件 | 修改目的 |
| --- | --- |

## 置信度字段契约

| 字段 | 含义 | 是否校准 | 前端文案 |
| --- | --- | --- | --- |

## SignalType与Evidence验证

## 伪Embedding熔断行为

## 数据迁移与计数守恒

| 指标 | 迁移前 | 迁移后 | 是否守恒 |
| --- | ---: | ---: | --- |

## 验收命令

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |

## 负例证据

| 场景 | 期望 | 实际 | 证据 |
| --- | --- | --- | --- |

## 浏览器证据

## 未覆盖风险

必须明确写出：真正的置信度校准属于P13-2，真实Embedding和语义去重属于P13-3，本阶段尚未完成。

## 需要指挥官重点复核
```

## 递交要求

完成后只提交交付报告、`metrics.json`和截图证据路径。不要开始P13-2。指挥官将独立运行迁移、测试、数据库守恒和浏览器验收；通过后再生成下一阶段指令。
