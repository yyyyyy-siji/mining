# P13-2-2-1 交付报告：人工标注接入与一致性工具

交付日期：2026-07-12

## 结论

- **fixture 工具链**：PASS（prepare → generate → import → validate 全链路 exit 0，FIXTURE_PASS）
- **真实候选**：BLOCKED（0 条合格授权候选，正确安全行为）
- **人工标签**：NOT_STARTED（fixture 工具链验证通过，等待真实人工标注）
- **annotation mutation**：PASS（23/23 全部捕获）
- **校准发布**：NOT_ALLOWED（`calibration_allowed=false` 保持不变）

## 修改文件

### 新增

| 文件 | 说明 |
| --- | --- |
| `signal_miner/evaluation/human_annotation.py` | 人工标注 schema（extra="forbid"）、任务包模型、Cohen's kappa / Jaccard / evidence agreement 一致性计算 |
| `scripts/p13_2_prepare_human_tasks.py` | 生成四类任务包（dev/cal assisted-review + test A/B blind） |
| `scripts/p13_2_generate_fixture_annotations.py` | 生成 fixture 标注（用于工具链验证） |
| `scripts/p13_2_import_human_annotations.py` | 标签导入与完整性校验（12 类规则） |
| `scripts/p13_2_validate_human_annotations.py` | 独立验证 CLI + 一致性计算 + 状态判定 |
| `scripts/p13_2_annotation_mutation_gate.py` | 23 类 annotation mutation gate |
| `tests/test_p13_2_human_annotation_contract.py` | 18 项契约测试（全部 tmp_path 隔离） |
| `sample_data/p13_2/human_tasks/*.json` | 四类 fixture 任务包 |
| `sample_data/p13_2/annotations/fixture_annotations.json` | 120 条 fixture 标注 |
| `sample_data/p13_2/human_annotations.json` | fixture annotation store |
| `docs/P13-2/human-annotation-operations-v1.md` | 人工标注操作说明 |
| `docs/P13-2-evidence/human-annotation-contract-metrics.json` | 验证指标 |
| `docs/P13-2-evidence/human-annotation-mutation-gate.json` | mutation gate 结果 |
| `docs/P13-2-evidence/human-annotation-readiness.json` | readiness 报告 |
| `docs/P13-2-evidence/human-task-readiness.json` | 任务包 readiness |

### 未修改

- 生产 pipeline、prompt、LLM adapter、Embedding、去重、聚类
- 数据库模型、迁移、API、前端
- P13-1 与 P13-2-1 已通过契约
- 真实历史数据的授权字段

## 授权候选接入

- 只接受通过 P13-2-1 exporter/validator 全部门禁的 candidate dataset。
- 每条必须有显式 `authorization_basis`、`source_platform`、`capture_method` 和冻结 content hash。
- 禁止根据公开 URL、capture method 或来源名称推导授权。
- 当前真实候选为 0 时，prepare 脚本输出 `BLOCKED_WAITING_AUTHORIZED_DATA / exit 2`，不使用 fixture 补足。
- 外部授权数据只能先进入独立输入文件，经 P13-2-1 全部门禁后生成新 dataset version。

独立复跑验证：

```bash
$ .venv/bin/python scripts/p13_2_prepare_human_tasks.py \
    --candidates <BLOCKED> --manifest sample_data/p13_2/manifest.json
{"status": "BLOCKED_WAITING_AUTHORIZED_DATA", "passed": false}
exit code = 2
```

## Assisted 与 blind 任务隔离

| 规则 | 实现 |
| --- | --- |
| assisted-review 显示明确标记的 suggestion | `_scrub_suggestion()` 保留 `suggested_signals` + `suggestion_label` |
| 隐藏 model/provider/prompt/score | `_count_identity_leak()` 扫描所有 identity 键 |
| test A/B 不得含 prediction/suggestion/model/confidence | `_count_task_pack_blind_leak()` 严格扫描 |
| A/B 互相隔离 | A pack 和 B pack 独立文件，B pack 只含 double-annotated 样本 |
| annotator_pseudonym 不可逆 | `compute_pseudonym(identity) = "anno_" + sha256(identity)[:12]` |

## 人工标签 schema 与导入幂等

严格 `extra="forbid"` Pydantic schema（`HumanAnnotationV2`），顶层 15 字段 + 单条 signal 7 字段。

signal_type 使用 `signal_miner.pipeline.pipeline_profile.get_profile(profile).signal_types` 单一真源。

导入校验 12 类规则：

1. Pydantic 严格 schema
2. sample_id / dataset_id / task_hash / content_hash 与冻结任务一致
3. signal_count == len(signals)
4. has_signals 一致性
5. evidence offset Unicode 安全（`redacted_text[start:end] == text`）
6. summary 非空、evidence 非空
7. annotator_slot 与任务一致
8. 同一 pseudonym 不得同时承担同一样本 A 和 B
9. signal_type 白名单（生产 profile 单一真源）
10. assisted_review 必须有 review_action
11. 同 annotation hash 幂等（重复导入安全）
12. 同 ID 不同内容 → 冲突失败

## A/B 一致性与分歧

对双标样本计算：

- `has_signals` Cohen's kappa
- signal count exact agreement rate
- signal type 集合 Jaccard（均值）
- evidence span overlap rate
- 分歧样本数量与字段列表

状态规则：

- 双标不足 `max(20, ceil(n×20%))` → BLOCKED
- kappa < 0.70 → BLOCKED_GUIDELINE_REVISION
- 分歧未裁决 → BLOCKED_PENDING_ADJUDICATION
- fixture 标注 → FIXTURE_PASS（不计入真实 human_verified_count）

## Mutation 结果

```
Annotation mutation gate: PASS (23/23)
```

覆盖指令要求的全部 20 个负例 + 3 个额外：

| # | mutation | target check | 类型 |
| --- | --- | --- | --- |
| 1 | fixture_counted_as_real | real_vs_fixture_count | validator |
| 2 | llm_suggestion_as_gold_no_action | assisted_review_action | validator |
| 3 | test_pack_has_model_confidence | no_blind_leakage_in_tasks | validator |
| 4 | a_reads_b_label | schema_strict | validator |
| 5 | same_pseudonym_a_and_b | no_self_pairing | validator |
| 6 | task_hash_tampered | task_identity | validator |
| 7 | content_hash_tampered | task_identity | validator |
| 8 | signal_count_mismatch | signal_count_consistency | validator |
| 9 | has_signals_false_but_signals_nonempty | has_signals_consistency | validator |
| 10 | invalid_signal_type | signal_type_whitelist | validator |
| 11 | unicode_evidence_offset_error | evidence_offsets | validator |
| 12 | evidence_empty | summary_and_evidence_nonempty | validator |
| 13 | summary_empty | summary_and_evidence_nonempty | validator |
| 14 | pii_email_leak_in_notes | no_pii_leak | validator |
| 15 | calibration_flag_ignored | calibration_not_allowed | validator |
| 16 | same_id_different_content_conflict | import_conflict | importer |
| 17 | nonexistent_dataset_id | import_reject | importer |
| 18 | nonexistent_sample_id | import_reject | importer |
| 19 | unknown_schema_field | import_reject | importer |
| 20 | llm_copy_as_gold_blind | import_reject | importer |
| 21 | zero_real_candidates_blocked_not_ready | blocked_exit_2 | prepare |
| 22 | ab_task_packs_missing | task_pack_files_present | validator |
| 23 | double_annotation_insufficient | double_annotation_coverage | validator |

## Artifact SHA 守恒

所有 P13-2-1 artifact 在本阶段全量测试后 SHA-256 不变：

```
12156bf3e3847aad  candidates.json
5bf92b95c12bef1a  manifest.json
85226ab46d6f8013  preannotations.json
03e8c0068c8c779f  annotation_pack_test_A.json
b7d172e5f22727d6  annotation_pack_test_B.json
36dccc0cd1f9f74b  annotation_pack_development.json
503ccf8f404c857f  annotation_pack_calibration.json
```

## P13-1 / P13-2-1 回归

| 验收项 | 结果 |
| --- | --- |
| ruff check | PASS（exit 0） |
| 全量 pytest | 242 passed, 3 warnings |
| 聚焦测试（human annotation contract） | 18 passed |
| annotation mutation gate | 23/23 PASS |
| behavior probe（P13-1） | PASS |
| goldset validator（P13-2-1） | READY / passed |
| git diff --check | 干净 |

## 状态不变量

```json
{
  "human_verified_count": 0,
  "human_labels_complete": false,
  "calibration_allowed": false,
  "fixture_only": true
}
```

fixture 标注不计入人工验证数量。真实 LLM 预标注未联网执行。未修改生产 pipeline、去重、聚类或 `calibrated_confidence`。

## 外部阻断与下一步人工动作

1. **需要用户提供可追溯授权数据**（含显式 `authorization_basis`、`source_platform`、`capture_method`）。
2. 授权数据到位后，经 P13-2-1 exporter 全门禁生成新 dataset version。
3. prepare 脚本生成真实任务包（不加 `--fixture`）。
4. 真实标注员完成 assisted-review 与 blind A/B 标注。
5. 标注导入 → 验证 → 一致性计算。
6. 达到阈值后（≥100 真实验证、≥25 test blind、≥20 双标、kappa≥0.70、分歧已裁决）才允许进入 P13-2-2-2。

**本阶段只建设工具。没有真实授权数据和人工 A/B 标签时，P13-2-2-2 不得开始，P13-2-3 / P13-2-4 继续冻结。**
