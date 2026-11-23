# P13-2-2-1 人工标注操作说明 v1

> 适用阶段：P13-2-2-1（工具建设）。真实授权候选当前为 0，业务状态 BLOCKED。
> 本文档面向标注协调员与标注员，描述如何使用本阶段建设的工具完成授权样本接入、任务分发、标注导入与一致性验收。

## 1. 阶段边界

- **本阶段只建设工具与机器门禁。** 工具链使用 fixture 数据验证通过即视为 FIXTURE_PASS。
- **不允许**用 DeepSeek、其他 LLM、规则标签或 fixture 冒充真实人工金标。
- **不允许**把业务状态写成 COMPLETE 或 READY。
- 真实授权候选到位前，`human_verified_count` 必须保持 0，`human_labels_complete` 必须保持 false，`calibration_allowed` 必须保持 false。
- 在真实授权数据与人工 A/B 标签满足验收阈值前，P13-2-2-2（人工标注执行）不得开始；P13-2-3 / P13-2-4 继续冻结。

## 2. 工具链概览

```
授权候选(dataset)
   │
   ▼
p13_2_export_annotation_pack.py  ──► candidates.json + manifest.json
   │                                   (P13-2-1 门禁)
   ▼
p13_2_prepare_human_tasks.py     ──► human_tasks_{dev,cal,test_A,test_B}.json
   │                                   (四类任务包)
   ▼
[人工标注]
   │
   ▼
p13_2_import_human_annotations.py ──► human_annotations.json (annotation store)
   │                                    (严格 schema + 完整性校验)
   ▼
p13_2_validate_human_annotations.py ──► contract-metrics.json
                                        (一致性 + 阈值 + 状态判定)
```

## 3. 授权候选接入

### 3.1 前置条件

- 候选数据集必须通过 P13-2-1 的 exporter 和 validator 全部门禁。
- 每条候选必须有显式 `authorization_basis`、`source_platform`、`capture_method` 和冻结 content hash。
- **禁止**根据公开 URL、capture method 或来源名称推导授权。

### 3.2 当前状态

真实数据库独立复跑结果：

```json
{
  "status": "BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES",
  "eligible_count": 0,
  "rejected_count": 1257
}
```

候选为 0 时，prepare 脚本输出：

```
status = BLOCKED_WAITING_AUTHORIZED_DATA
exit code = 2
```

这是**正确安全行为**，不是契约错误。

### 3.3 外部授权数据接入流程

1. 外部授权数据只能先进入独立输入文件（如 `sample_data/p13_2/positive/external_authorized.json`）。
2. 该文件经 P13-2-1 exporter 全部门禁后生成新 dataset version。
3. **禁止**直接修改历史 DB 记录伪造授权字段。
4. 新 dataset version 需使用 `--new-dataset-version` 并指定新的 manifest 路径。

## 4. 任务包

### 4.1 四类任务

| 包 | split | slot | annotation_mode | suggestion | 文件 |
| --- | --- | --- | --- | --- | --- |
| development assisted-review | development | assisted | assisted_review | 允许（已脱敏） | human_tasks_development.json |
| calibration assisted-review | calibration | assisted | assisted_review | 允许（已脱敏） | human_tasks_calibration.json |
| test A blind | test | A | blind | **禁止** | human_tasks_test_A.json |
| test B blind | test | B | blind | **禁止** | human_tasks_test_B.json |

### 4.2 隔离规则

- **assisted-review**：可显示明确标记的 suggestion，但**隐藏**模型身份、provider、prompt 和任何 score。
- **test A/B blind**：**不得包含**任何 prediction、suggestion、model、provider、prompt、confidence、score 字段。
- **A/B 互相隔离**：A 包看不到 B 的标签、完成状态或备注；反之亦然。
- **B 包**只包含被选为双标的 test 样本（double_annotation_ids）。

### 4.3 任务字段

每个任务含：

- `dataset_id`：冻结数据集 ID
- `sample_id`：样本 ID
- `annotator_slot`：A / B / assisted
- `task_hash`：任务冻结 hash（dataset_id + sample_id + slot + content_hash）
- `content_hash`：脱敏文本冻结 hash
- `profile`：所属 profile（决定 signal_type 白名单）
- `redacted_text`：脱敏后的待标注文本

### 4.4 生成任务包

```bash
# 真实候选到位后（不加 --fixture）
.venv/bin/python scripts/p13_2_prepare_human_tasks.py \
  --candidates sample_data/p13_2/positive/candidates.json \
  --manifest sample_data/p13_2/manifest.json \
  --preannotations sample_data/p13_2/positive/preannotations.json \
  --out-dir sample_data/p13_2/human_tasks

# fixture 模式（当前可用）
.venv/bin/python scripts/p13_2_prepare_human_tasks.py \
  --candidates sample_data/p13_2/positive/candidates.json \
  --manifest sample_data/p13_2/manifest.json \
  --preannotations sample_data/p13_2/positive/preannotations.json \
  --out-dir sample_data/p13_2/human_tasks \
  --fixture
```

## 5. 人工标签 schema

### 5.1 顶层字段（严格 extra="forbid"）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| annotation_id | str | 唯一 ID |
| dataset_id | str | 与冻结任务一致 |
| sample_id | str | 与冻结任务一致 |
| annotator_slot | str | A / B / assisted，与冻结任务一致 |
| annotator_pseudonym | str | 不可逆 pseudonym，**不得**写姓名/邮箱/账号 |
| annotation_mode | str | assisted_review / blind |
| has_signals | bool | 是否含信号 |
| signal_count | int | 必须 == len(signals) |
| signals | list | 见下 |
| review_action | str / null | assisted_review 必填：accepted / modified / rejected |
| started_at | str | ISO 时间戳 |
| completed_at | str | ISO 时间戳 |
| task_hash | str | 与冻结任务一致 |
| content_hash | str | 与冻结任务一致 |
| fixture | bool | fixture 标注必须为 true |

### 5.2 单条 signal 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| signal_type | str | 必须在生产 profile 白名单内 |
| summary | str | 非空 |
| evidence_spans | list | 非空，每条 start:end 必须等于 text |
| implicit_need | str / null | |
| implicit_need_has_basis | bool | |
| hallucination | bool | |
| notes | str / null | |

### 5.3 signal_type 白名单

由 `signal_miner.pipeline.pipeline_profile.get_profile(profile).signal_types` 单一真源决定：

- **product_feedback**：feature_request, bug_report, usability_issue, question, praise, complaint, churn_risk
- **aigc_video**：viral_hook, content_pattern, visual_technique, audio_strategy, engagement_trigger, platform_algorithm, topic_trend, monetization_pattern

非法 signal_type 会被导入和验证工具拒绝。

## 6. 标注员身份保护

- 标注员真实身份只保存不可逆 `annotator_pseudonym`（`anno_` + sha256(identity)[:12]）。
- **禁止**在 annotation 任何字段写入姓名、邮箱、手机号或账号。
- validator 的 PII 检测会扫描所有非 hash 字段，匹配到邮箱或中国手机号即失败。

## 7. 导入与完整性验证

### 7.1 导入

```bash
.venv/bin/python scripts/p13_2_import_human_annotations.py \
  --input path/to/annotations.json \
  --tasks sample_data/p13_2/human_tasks \
  --store sample_data/p13_2/human_annotations.json
```

导入时校验：

1. Pydantic 严格 schema（未知字段失败）
2. sample_id / dataset_id / task_hash / content_hash 与冻结任务一致
3. signal_count == len(signals)
4. has_signals 一致性
5. evidence offset 正确（Unicode 安全）
6. summary 非空，evidence 非空
7. annotator_slot 与任务一致
8. **同一 pseudonym 不得同时承担同一样本 A 和 B**
9. signal_type 白名单
10. assisted_review 必须有 review_action
11. 同 annotation hash 幂等（重复导入安全）
12. 同 ID 不同内容 → 冲突失败

### 7.2 验证与一致性

```bash
.venv/bin/python scripts/p13_2_validate_human_annotations.py \
  --tasks sample_data/p13_2/human_tasks \
  --store sample_data/p13_2/human_annotations.json \
  --adjudications path/to/adjudications.json \
  --out docs/P13-2-evidence/human-annotation-contract-metrics.json
```

一致性指标（对双标样本）：

- `has_signals` Cohen's kappa
- signal count exact agreement rate
- signal type 集合 Jaccard（均值）
- evidence span overlap rate
- 分歧样本数量与字段列表

## 8. 状态判定规则

| 条件 | 状态 |
| --- | --- |
| fixture-only（无真实标注） | FIXTURE_PASS |
| 真实候选为 0 | BLOCKED_WAITING_AUTHORIZED_DATA |
| 双标不足 max(20, ceil(n×20%)) | BLOCKED_INSUFFICIENT_DOUBLE_ANNOTATION |
| has_signals kappa < 0.70 | BLOCKED_GUIDELINE_REVISION |
| 分歧未裁决 | BLOCKED_PENDING_ADJUDICATION |
| 全部阈值满足 | READY |

### READY 必须同时满足

- 真实人工验证 ≥ 100
- test blind ≥ 25
- 双标达到 20% 且不少于 20
- kappa ≥ 0.70
- 分歧已裁决
- fixture / LLM / 规则 / 测试标签计数为 0

本阶段**不得**设置 `calibration_allowed = true`。

## 9. A/B 一致性与分歧裁决

- A/B 原始标签**不可覆盖**。
- 分歧裁决产生**独立记录**（AdjudicationRecord），不修改原标签。
- 裁决记录字段：adjudication_id, sample_id, annotator_a_pseudonym, annotator_b_pseudonym, field_in_dispute, final_value, adjudicator_pseudonym, adjudicated_at。
- 未裁决的分歧 → BLOCKED_PENDING_ADJUDICATION。

## 10. human_verified_count 单一真源

`human_verified_count` 只能由通过全部验证的真实人工 annotation 去重（按 sample_id）计算，**不能**来自 manifest 手写值。

fixture、LLM、规则和测试标签不计入此计数。

---

**工具建设到此为止。真实授权数据与人工 A/B 标签到位后，P13-2-2-2 才可开始。**
