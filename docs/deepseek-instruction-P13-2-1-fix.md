# DeepSeek 返修指令：P13-2-1 fix 授权真实性与机器门禁收口

## 任务目标

只修复P13-2-1验收中暴露的授权真实性、验证器假阳性、负例隔离、真实导出证据和报告漂移。不得开始人工标注、主动学习指标或概率校准。

## 背景 / 当前问题

当前fixture基础路径可以运行，但Commander证明以下错误artifact仍全部返回`READY/passed=true`：清单哈希篡改、test分数泄漏、重复双标ID、错误evidence offset和虚假人工计数。同时授权依据会从采集方式自动推导，真实数据库导出没有交付，Ruff实际失败。

## 允许修改范围

- `signal_miner/evaluation/__init__.py`，或将其拆为`signal_miner/evaluation/goldset.py`并保持清晰导出
- `scripts/p13_2_export_annotation_pack.py`
- `scripts/p13_2_generate_preannotations.py`
- `scripts/p13_2_validate_goldset.py`
- 新增`scripts/p13_2_mutation_gate.py`
- `tests/test_p13_2_goldset_contract.py`
- `docs/P13-2/annotation-guideline-v1.md`
- `docs/P13-2/goldset-data-contract-v1.md`
- `sample_data/p13_2/` fixture与独立A/B包
- `docs/P13-2-evidence/`机器证据
- 新的P13-2-1 fix交付报告

## 禁止修改范围

- `signal_miner/pipeline/`、runner、去重、聚类和资产生成
- 数据库模型、Alembic、API路由、两个前端
- LLM adapter和生产prompt
- P13-1已通过的置信度与Embedding熔断逻辑
- P13-2-2人工标注导入、P13-2-3主动学习评测、P13-2-4校准
- P13-3及后续阶段

## 实现要求

### 1. 授权依据必须显式存在

- 删除`_derive_authorization`及等价逻辑。
- `authorization_basis`为空、非法或无可追溯来源时必须拒绝。
- 禁止根据`source_type`、`capture_method`、平台公开可见或URL存在推断授权。
- `source_platform`与`capture_method`分字段读取和统计；缺少`source_platform`的真实记录进入明确拒绝原因。
- rejection JSON不得包含原始敏感正文，只含不可逆/内部ID和reason code。

静态防复发门禁：

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("scripts/p13_2_export_annotation_pack.py").read_text()
helpers = Path("signal_miner/evaluation/__init__.py").read_text()
assert "_derive_authorization" not in text + helpers
print("explicit authorization gate present")
PY
```

### 2. 脱敏与严格schema

- `GoldRecord`增加`schema_version`并与manifest一致。
- 所有Pydantic契约使用`extra="forbid"`；未知字段必须失败，不能被静默丢弃后再扫描。
- 实现确定性脱敏：邮箱、手机号、token/key等替换为稳定占位符；保存`redaction_applied=true`，导出后再次扫描，残留敏感信息则拒绝。
- manifest保存脱敏文本hash；验证器重新计算并比对。

### 3. 验证器必须独立重算

验证器新增并强制读取：

- candidates
- manifest
- development assisted-review pack
- calibration assisted-review pack
- test A blind pack
- test B blind pack
- preannotations
- annotation guideline

必须独立重算并参与顶层`passed`：

- 样本数、profile/source平台分布和精确50/25/25 split
- manifest中的sample IDs、content hash list、ordered hash、guideline hash、blind pack hash
- `selection_query_fingerprint`，其输入至少包含有序raw ID/content hash、seed、schema和资格规则版本
- double IDs唯一、全部存在、数量满足`max(20, ceil(n×20%))`
- test A/B分配正确；A/B包不含对方标签，B只含双标样本
- 三类标注包无模型身份和confidence；test A/B无prediction/suggestion/prompt
- suggestion引用的sample存在且只属于development/calibration
- suggestion evidence满足`redacted_text[start:end] == text`
- `human_labels_complete=false`、`human_verified_count=0`、`calibration_allowed=false`来自真实manifest且彼此一致
- schema版本和annotation mode逐条一致

禁止：

- 使用`manifest.passed`代替重新计算。
- 硬编码`evidence_offsets=true`或输出字段固定为0/false。
- 先通过宽松Pydantic丢弃字段，再对`model_dump()`做泄漏扫描。

### 4. 冻结manifest不能静默覆盖

- 同一`dataset_id`的manifest已存在时，sample IDs、content hashes、split、guideline hash或选择指纹变化必须失败。
- 只有显式新dataset版本才能产生不同冻结清单。
- `created_at`不参与确定性内容hash。
- 使用不同`PYTHONHASHSEED`和相同seed运行，sample IDs、split、dataset ID及所有内容hash必须一致。

### 5. A/B包与预标注语义

- 生成独立`annotation_pack_test_A.json`与`annotation_pack_test_B.json`。
- A包包含test主标任务；B包只包含双标任务。两个包均不得包含任何已完成标签或对方字段。
- 固定模板 suggestion 只能通过显式`--fixture-mode`生成，且每项包含`fixture_only=true`，不得被描述为真实DeepSeek预标注。
- 默认非fixture模式必须调用现有配置adapter或在模型/密钥不可用时输出`BLOCKED_PREANNOTATION_UNAVAILABLE`并退出2；禁止静默生成`feature_request`模板。
- 真实模型调用不作为本次必须联网成功项；可用注入式fake adapter验证结构和错误处理，但报告必须如实标记实际联网状态。

### 6. 真实数据库导出

必须实际执行且始终保存结果：

```bash
.venv/bin/python scripts/p13_2_export_annotation_pack.py \
  --out docs/P13-2-evidence/real-candidate-export.json \
  --rejects docs/P13-2-evidence/real-rejections.json \
  --manifest docs/P13-2-evidence/real-manifest.json
```

退出码契约：

- READY：0
- 数据/授权/profile不足等诚实BLOCKED：2
- 代码、schema、hash或内部错误：1

即使BLOCKED，也必须写出`status`、eligible count、各reason count、profile/source platform分布、required值和`passed=false`。不得根据“预计”填写报告。

### 7. 测试必须隔离且是真负例

- 所有测试使用`tmp_path`或临时目录，不得写`sample_data/p13_2/`和`docs/P13-2-evidence/`固定交付路径。
- 删除所有空`pass`测试。
- 确定性测试必须在第一次运行后保存实际结果，再执行第二次并比较；额外使用至少两个不同`PYTHONHASHSEED`。
- 每个负例必须把篡改后的完整artifact交给正式CLI验证器，断言非零退出码与对应check为false。
- 聚焦测试前后对所有交付artifact计算SHA-256，必须完全不变。

## 强制mutation gate

新增`scripts/p13_2_mutation_gate.py`，在临时目录复制正例artifact并逐项篡改。至少覆盖：

1. 缺失授权依据。
2. 非法授权依据。
3. test/mock/sample冒充真实候选。
4. 残留邮箱、手机号、token。
5. 中文Unicode evidence offset错误。
6. content hash跨split泄漏。
7. 双标ID重复、ID不存在、数量不足。
8. test A/B包出现suggestion、model、prompt或confidence。
9. development/calibration suggestion被计入人工验证。
10. test少于25、profile少于30、单平台超过60%。
11. sample ID/content hash/guideline hash/blind pack hash任一篡改。
12. 同dataset ID静默改变冻结清单。
13. `human_labels_complete=false`但人工计数非0或校准开启。
14. suggestion引用test或不存在sample。
15. suggestion evidence offset错误。
16. 未知schema字段试图被静默忽略。

输出`docs/P13-2-evidence/mutation-gate.json`：每项包含child exit code、target check、detected、passed；顶层`passed`必须是全部项逻辑与。任一错误未被捕获，mutation gate退出1。

## 验收标准

### 静态与回归

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_goldset_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_1_behavior_probe.py
git diff --check
```

### 机器门禁

```bash
.venv/bin/python scripts/p13_2_mutation_gate.py
python3 -m json.tool docs/P13-2-evidence/goldset-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/mutation-gate.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/real-candidate-export.json >/dev/null
```

### Artifact隔离门禁

交付报告必须提供测试前后artifact SHA清单，并证明聚焦测试和全量测试都没有改变：

- `sample_data/p13_2/manifest.json`
- `sample_data/p13_2/positive/*.json`
- `docs/P13-2-evidence/*.json`

## 交付物

1. `docs/acceptance-P13-2-1-delivery-fix-20260710.md`
2. `docs/P13-2-evidence/goldset-contract-metrics.json`
3. `docs/P13-2-evidence/mutation-gate.json`
4. `docs/P13-2-evidence/real-candidate-export.json`
5. `docs/P13-2-evidence/real-rejections.json`
6. A/B独立盲标fixture包

## 交付报告模板

```markdown
# P13-2-1 fix交付报告：授权真实性与机器门禁收口

## 结论

- fixture契约：PASS / FAIL
- mutation gate：PASS / FAIL
- 真实候选：READY / BLOCKED / FAIL
- 真实预标注：READY / BLOCKED / NOT_RUN
- 人工标签：NOT_STARTED
- 校准发布：NOT_ALLOWED

## 修改文件

## 授权与来源平台拒绝统计

## Manifest逐字段重算

## A/B盲标包与预标注隔离

## Mutation gate结果

| mutation | child exit | check | detected |
| --- | ---: | --- | --- |

## 测试前后artifact SHA守恒

## 真实数据库导出

| status | exit | eligible | rejected | blocker |
| --- | ---: | ---: | ---: | --- |

## P13-1回归

## 未覆盖风险
```

## 完成边界

fix通过只代表P13-2-1基础设施可信，不代表真实金标已完成，也不允许开始校准。提交后等待Commander独立复验；P13-2-2继续冻结。
