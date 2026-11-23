# DeepSeek 执行指令：P13-2-1 混合金标协议、脱敏导出、预标注隔离与冻结清单

## 任务目标

建立 P13-2 的第一块可审计基础设施：定义混合标注协议、金标数据格式、授权/脱敏门禁、确定性抽样、机器预标注隔离、双标分配和不可变 development/calibration/test 冻结清单。

本阶段只准备“机器先减负、人类作最终真值、验证器严格防泄漏”的数据包和工具。允许 DeepSeek 或其他模型为development/calibration生成明确标记的 `suggestion`，但**不允许机器suggestion代替人工gold label，不允许在冻结test标注包中出现预测或分数，不进行置信度拟合，也不写入 `calibrated_confidence`。**

## 背景 / 当前问题

- P13-1 已区分 `model_self_score` 与 `calibrated_confidence`，并保持后者为空。
- 完整 P13-2 要求不少于 100 条经过人工验证的真实或经授权反馈、至少 20 条双人标注、25 条冻结盲标测试样本，以及 Precision/Recall/F1、evidence exactness、幻觉率、Brier Score、ECE 等指标。
- 当前数据库含历史、样例和来源字段不完整的数据，不能直接假定全部具备真实/授权金标资格。
- 人工金标本身是外部人工工作，执行 AI 不能伪造“双人标注完成”或用模型输出充当金标；但可生成预标注候选，供后续人工确认/修改，以降低工作量。

因此 P13-2 拆为四个串行子阶段：

1. **P13-2-1（本次）**：协议、schema、合格样本导出、预标注隔离、双标分配、冻结 manifest 和验证器。
2. P13-2-2：人工标注导入、25条test盲标、按20%且不少于20条执行双标、一致性计算和分歧裁决。
3. P13-2-3：主动学习补充难例，完成提取、证据、幻觉指标与置信区间评测。
4. P13-2-4：独立calibration集拟合，Brier/ECE达标后才允许发布校准概率。

## 允许修改范围

- 新增 `docs/P13-2/annotation-guideline-v1.md`
- 新增 `docs/P13-2/goldset-data-contract-v1.md`
- 新增 `signal_miner/evaluation/` 下仅与金标 schema、清单哈希、抽样/分割、脱敏校验有关的模块
- 新增 `scripts/p13_2_export_annotation_pack.py`
- 新增 `scripts/p13_2_generate_preannotations.py`
- 新增 `scripts/p13_2_validate_goldset.py`
- 新增 `tests/test_p13_2_goldset_contract.py`
- 新增 `sample_data/p13_2/` 下的**纯合成、明确标记为 fixture**的正负例，不得命名为真实金标集
- 新增 `docs/P13-2-evidence/` 机器证据
- 如确有必要，可在 `pyproject.toml` 只增加本阶段验证器所需的轻量依赖；优先使用标准库、Pydantic 和现有依赖

## 禁止修改范围

- 禁止修改生产挖矿管线：`signal_miner/pipeline/`、runner、去重、聚类、资产生成
- 禁止修改数据库模型、Alembic 迁移、API 路由、两个前端
- 禁止修改 LLM adapter、prompt、Embedding 配置或模型选择
- 禁止写入 `feedback_signals.calibrated_confidence`
- 禁止实现 P13-2-4 的 Platt scaling、isotonic regression、ECE 发布门禁
- 禁止开始 P13-3 真实 Embedding、P13-4 聚类、P13-5 数据版本或 P13-6 来源治理
- 禁止把合成 fixture、现有 sample_data、LLM suggestion、模型间一致或单人机器复核描述为“真实人工金标”
- 禁止为凑满 100 条而放宽授权、来源、脱敏或 profile 条件
- 禁止在test annotation pack中写入DeepSeek预测、任何预标注、模型身份、prompt版本或模型自评分

## 实现要求

### 1. 金标记录契约

每个待标注样本必须有稳定 `sample_id`，且至少包含：

- `schema_version`
- `sample_id`
- `raw_feedback_id` 或不可逆关联 ID
- `profile`
- `source_platform`
- `capture_method`
- `authorization_basis`
- `content_hash`
- `redacted_text`
- `redaction_applied`
- `language`
- `hard_case_tags`
- `split`
- `split_seed`
- `annotation_mode`（`assisted_review`或`blind`）
- `annotation_status`
- `annotator_slot`（A/B；不能存真实姓名）

机器预标注必须与人工金标分离，至少包含：

- `suggestion_id`
- `suggestion_model`
- `suggestion_model_version`
- `suggestion_prompt_version`
- `suggested_signals`
- `suggestion_created_at`

上述字段只能存在于development/calibration的内部辅助包中。人工最终标签必须写入独立`human_annotations`结构，不能原地覆盖suggestion。冻结test的标注包和标注员视图中不得包含整个suggestion结构。

人工标签至少覆盖：

- 是否存在可提取信号
- 信号数量
- 每个信号的 `signal_type`
- 摘要要点
- 原文 evidence 的字符区间 `[start, end)` 与对应原文片段
- 隐含需求是否有原文依据
- 无依据新增事实 / hallucination 标记
- 分歧原因和裁决状态（在本阶段可为空，但 schema 必须定义）

字符区间必须针对 `redacted_text`，验证器必须断言 `redacted_text[start:end] == evidence_text`，并正确处理中文和 Unicode。

### 2. 授权与脱敏门禁

导出器默认拒绝以下记录进入候选包：

- 测试、样例、mock 或来源身份不明
- `authorization_basis` 为空或不在显式白名单
- 原文仍含明确的邮箱、手机号、访问令牌或用户配置的敏感字段模式
- profile 不在本阶段支持集合
- 正文为空、只有占位符或 content hash 重复

拒绝记录必须进入机器可读 rejection report，包含 `raw_feedback_id`、reason code，不得包含被拒绝的敏感原文。

若当前库不足 100 条合格记录，必须输出 `status=BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES` 和实际数量，退出非 0；不得用 sample fixture 补足。

### 3. 确定性抽样、覆盖与混合标注分工

- 使用显式 seed，给定相同输入、schema 版本和 seed，样本顺序、双标分配和 split 必须完全一致。
- 目标样本数不少于 100，覆盖 `product_feedback` 与 `aigc_video` 两个 profile；每个 profile 不得少于 30 条。
- 覆盖主要合格来源；单一来源占比不得超过 60%，若现实数据不足则 BLOCKED 并报告分布。
- split 必须按样本 ID 冻结为 development/calibration/test = 50/25/25；test 不得少于 25 条，且不能被后续调参脚本读取为训练输入。
- development和calibration使用`annotation_mode=assisted_review`，允许人类查看机器suggestion，但必须隐藏模型自评分；人工需要确认或修改，不能一键默认接受而没有审计动作。
- test使用`annotation_mode=blind`，导出的标注员包必须完全移除suggestion、模型/provider、prompt版本和模型分数。
- 双标数量必须不少于`max(20, ceil(sample_count × 20%))`，优先从25条test中选择；A/B不能看到对方标签，裁决不得覆盖原始标签。
- 同 content hash、同逻辑反馈的 revision、可判定的近重复不得跨 split 泄漏。

### 4. 预标注减负与泄漏隔离

- 预标注只能通过显式命令生成，不得在导出盲标test包时隐式调用LLM。
- 预标注输出必须标记`label_status=suggestion_only`、模型和prompt版本，且`counts_as_human_verified=false`。
- 标注员辅助包不得展示`model_self_score`或`calibrated_confidence`，避免分数锚定。
- 允许用第二模型或规则生成`disagreement_flags`，只用于主动学习排序，不能作为gold correctness。
- test盲标包必须有独立防泄漏验证：递归扫描任何`prediction`、`suggestion`、`confidence`、`model`、`prompt`类字段或值，发现即失败。
- 本阶段不得声称100条已经人工验证；manifest必须保持`human_verified_count=0`，除非真实人工标注由用户另行提供并进入P13-2-2验收。

### 5. 冻结清单

生成 manifest JSON，至少包含：

- `dataset_id`、`schema_version`、`created_at`
- `selection_query_fingerprint`、`seed`
- 每个 split 的 sample IDs、数量、profile/source 分布
- 双标 sample IDs、数量与比例
- 每个split的`annotation_mode`
- test盲标包哈希与`blind_pack_leakage_count`
- 每个脱敏文本的 SHA-256
- 全部样本有序清单 SHA-256
- annotation guideline SHA-256
- `human_labels_complete=false`
- `human_verified_count=0`
- `calibration_allowed=false`
- `passed`

时间字段不能参与确定性内容哈希。manifest 一旦冻结，同一 `dataset_id` 下 sample IDs 或 hash 改变必须硬失败；只能创建新 dataset 版本，不能静默覆盖。

### 6. 标注指南

`annotation-guideline-v1.md` 必须用中文写清：

- signal 与非 signal 的边界
- 各 profile 的 signal type 定义与正反例
- evidence 区间如何标注
- 显式需求、隐含需求、有依据推断和无依据幻觉的区别
- 一条文本包含多个信号时如何拆分
- 冲突、信息不足、讽刺、转述、重复、跨句 evidence 如何处理
- 所有标注员都不得查看模型自评分、校准分数或其他置信度字段
- assisted review可以查看明确标记的预标注suggestion，但不得查看模型身份或分数；blind test不得查看任何预测、suggestion、模型或prompt信息
- 双标独立完成、何时进入裁决、裁决不得覆盖原始 A/B 标签

### 7. 验证器与机器证据

`p13_2_validate_goldset.py` 输出 JSON，必须含：

- `status`
- `checks`，每项包含 `passed` 与 observations
- `sample_count`
- `eligible_count`
- `rejected_count_by_reason`
- `profile_distribution`
- `source_distribution`
- `double_annotation_ratio`
- `double_annotation_count`
- `split_counts`
- `annotation_mode_by_split`
- `blind_test_count`
- `blind_pack_leakage_count`
- `suggestion_count_by_split`
- `leakage_count`
- `offset_mismatch_count`
- `manifest_hash_match`
- `human_labels_complete`
- `human_verified_count`
- `calibration_allowed`
- 顶层 `passed`

顶层 `passed` 必须等于所有阻断 check 的逻辑与。对“合格真实数据不足”的实际运行，应诚实返回 BLOCKED/非 0；这不等同于代码验收失败，但交付报告必须明确需要人工/数据输入。

## 验收标准

### 语法 / 静态检查

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_goldset_contract.py
.venv/bin/python -m pytest -o addopts= -q
git diff --check
```

### 功能验证

- 合成正例 fixture 可生成确定性 annotation pack 和 manifest；连续运行两次，除非明确排除的 `created_at` 外，内容 hash 完全一致。
- Unicode evidence 区间精确匹配。
- A/B 双标分配数量不少于`max(20, ceil(sample_count × 20%))`，且原始A/B槽位相互不可见。
- development/calibration辅助包可以包含suggestion，但不得包含模型自评分。
- test恰好25条且全部`annotation_mode=blind`；test标注包递归检查无prediction/suggestion/confidence/model/prompt泄漏。
- 两个 profile、来源占比、split 数量和防泄漏规则均由验证器计算，不允许手写通过。
- manifest 修改一个 sample ID、content hash 或 guideline hash 后必须失败并退出非 0。

### 必须存在的负例

至少逐项证明下列错误会使验证器退出非 0，并令对应 `checks.*.passed=false`：

1. 用 `sample_data` 或 `is_test=true` 记录冒充真实金标候选。
2. `authorization_basis` 缺失。
3. 脱敏文本包含邮箱、手机号或 token fixture。
4. evidence offset 与片段不一致，含一个中文 Unicode 负例。
5. 同 content hash 或逻辑 revision 跨 split。
6. 双标样本少于`max(20, ceil(sample_count × 20%))`，或A/B能读取对方标签。
7. test 少于25条、test不是blind，或某 profile 少于30条。
8. 单一来源超过 60%。
9. 冻结 manifest 后静默更换 sample IDs 或文本 hash。
10. `human_labels_complete=false` 时尝试令 `calibration_allowed=true`。
11. 故意把任一关键 observation 改为不合格值时，顶层 `passed` 不能仍为 true。
12. test盲标包包含任意预测、suggestion、模型身份、prompt版本或confidence字段。
13. development/calibration的suggestion被计入`human_verified_count`。

### 回归验证

- P13-1 的 `model_self_score` / `calibrated_confidence` 契约不变。
- 行为探针继续通过，且正式库不新增 pseudo embedding、dismissed 或 theme。
- 本阶段运行前后数据库 Signal、Theme、PainPoint、Opportunity、Requirement 计数守恒。
- 不得产生任何非空 `calibrated_confidence`。

### 交付前质量门禁

```bash
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_1_baseline_metrics.py
.venv/bin/python scripts/p13_2_export_annotation_pack.py --help
.venv/bin/python scripts/p13_2_generate_preannotations.py --help
.venv/bin/python scripts/p13_2_validate_goldset.py --help
```

此外必须提交一次：

- 合成 fixture 正例运行，退出 0；
- 每一类负例运行，退出非 0；
- 当前实际数据库候选导出运行。若资格不足，保存 BLOCKED JSON 和退出码，不得写成 PASS；
- 机器 JSON 顶层决策与 Markdown 报告逐字段一致。

## 交付物

1. `docs/acceptance-P13-2-1-delivery-20260710.md`
2. `docs/P13-2-evidence/goldset-contract-metrics.json`
3. `docs/P13-2-evidence/real-candidate-export.json`（可以是诚实的 BLOCKED）
4. `docs/P13-2/annotation-guideline-v1.md`
5. `docs/P13-2/goldset-data-contract-v1.md`
6. development/calibration assisted-review fixture包与test blind fixture包
7. fixture manifest 与所有负例结果清单

## 交付报告模板

```markdown
# P13-2-1 交付报告：混合金标协议、脱敏导出、预标注隔离与冻结清单

## 结论

- 代码/fixture 门禁：PASS / FAIL
- 真实候选数据：READY / BLOCKED
- 人工标签：NOT_STARTED（本阶段不得写成 COMPLETE）
- 校准发布：NOT_ALLOWED

## 修改文件

| 文件 | 修改说明 |
| --- | --- |

## Schema 与标注协议

## 实际数据资格与拒绝原因

| 指标 | 值 | 机器证据字段 |
| --- | ---: | --- |

## 抽样、双标与 split 结果

## assisted-review 与 blind-test 泄漏隔离

| split | 数量 | annotation_mode | suggestion数量 | 泄漏数 |
| --- | ---: | --- | ---: | ---: |

## 确定性与 manifest 哈希

## 负例证据

| 负例 | 退出码 | 对应 check | passed |
| --- | ---: | --- | --- |

## P13-1 回归与数据库计数守恒

## 未覆盖风险 / 外部阻断

## 需要指挥官重点复核
```

## 完成边界

本指令完成只代表 P13-2 的混合标注基础设施可用，不代表100条已经人工验证、金标集完成、指标达标或置信度已校准。提交后等待指挥官独立验收；未通过只返修 P13-2-1，不得进入 P13-2-2。
