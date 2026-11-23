# P13-2-2-1 fix-2 交付报告

## 结论

**通过**。消除了 importer mutation 通过退出码伪造 target check 的假阳性，
修正了证据文件职责漂移。

- importer 的 `--out` 报告现在输出 12 类命名结构化 checks，顶层 `passed`
  由所有 checks 真实复算。
- mutation runner 统一使用 `_evaluate_detection()`，importer mutation 与
  validator mutation 适用同一硬契约：`child_exit==1 + 目标真实存在于同次
  报告 + target.passed is false`。
- 5 类元负例证明 runner 无法被退出码欺骗。
- 26/26 mutation 全部检测、1/1 readiness invariant 通过、5/5 元负例通过。

本 fix-2 通过仅代表 P13-2-2-1 工具可信。真实候选仍为 0，P13-2-2-2 及
后续阶段继续冻结。

## 修改文件

| 文件 | 变更 |
|---|---|
| `scripts/p13_2_import_human_annotations.py` | 重写为结构化 checks 输出；新增 `IMPORTER_CHECKS` 12 类命名检查；新增 `fixture_provenance` 检查阻断 fixture/LLM 冒充真实标签；`_validate_one` 按 check 名称分桶；顶层 `passed` 由所有 checks 复算 |
| `scripts/p13_2_annotation_mutation_gate.py` | 新增 `_read_report_checks()` + `_evaluate_detection()` 统一判定函数；`run_importer_mutation` 改为读取同次 `import_report.json` 的 `checks[target_check]`；新增 `_run_importer_meta_negatives()` 5 类元负例；m16 改为改 `started_at` 触发冲突；m17/m18/m19/m20 重映射到真实 importer check 名；禁止模式 (`"check_exists": True`、`"target_passed": not detected`、`target_check field is used for reporting only`) 全部清除 |
| `tests/test_p13_2_human_annotation_contract.py` | 新增 `TestImporterStructuredChecks`（7 项）验证 importer checks 契约；新增 `TestImporterMutationMetaNegatives`（4 项）验证 runner 判定逻辑不可欺骗 |
| `docs/P13-2-evidence/human-annotation-contract-metrics.json` | 重新生成（validator-only，不变更字段职责） |
| `docs/P13-2-evidence/human-annotation-mutation-gate.json` | 重新生成（含 meta_negatives 段） |
| `docs/P13-2-evidence/human-annotation-readiness.json` | 与 contract-metrics 同步 |

## Importer checks 契约表

`scripts/p13_2_import_human_annotations.py` 的 `--out` 报告现在输出
`IMPORTER_CHECKS` 定义的 12 类命名检查。每个 check 结构：

```json
{
  "passed": false,
  "observations": {
    "error_codes": ["ann_id.detail: reason", ...],
    "error_count": N
  }
}
```

| check 名 | 阻断规则 |
|---|---|
| `schema_strict` | Pydantic `extra="forbid"`，未知字段失败 |
| `task_exists` | `(sample_id, annotator_slot)` 必须命中冻结任务包 |
| `dataset_identity` | `dataset_id` / `task_hash` / `content_hash` / `annotation_mode` 与冻结任务一致 |
| `signal_count_consistency` | `signal_count == len(signals)` |
| `has_signals_consistency` | `has_signals` 与 signals 非空性一致 |
| `evidence_offsets` | `redacted_text[start:end] == text`（Unicode 安全） |
| `summary_and_evidence_nonempty` | 每 signal 的 summary / evidence_spans 非空 |
| `signal_type_whitelist` | `signal_type ∈ profile.signal_types`（生产单一真源） |
| `assisted_review_action` | assisted_review 任务必填 `review_action` |
| `no_self_pairing` | 同 pseudonym 不可同时标 A 和 B |
| `annotation_id_conflict` | 同 id 不同内容 → 拒绝（非幂等） |
| `fixture_provenance` | `fixture=false` 但 id 含 `fixann`/`fixture`/`test`/`mock`/`sample`/`fake`/`demo` 标记 → 拒绝（阻断 LLM/fixture 冒充真实 gold） |

顶层 `passed` = AND of all checks' `passed`（在 `_write_report` 中真实复算）。

## Mutation target 真实读取证据

所有 importer mutation 现在从同次 `import_report.json` 的 `checks[target_check]`
读取目标，不再通过退出码反推。证据来自
`docs/P13-2-evidence/human-annotation-mutation-gate.json`：

| mutation | target_check | child_exit | check_exists | target_passed | detected |
|---|---|---|---|---|---|
| same_id_different_content_conflict | annotation_id_conflict | 1 | true | false | true |
| nonexistent_dataset_id | dataset_identity | 1 | true | false | true |
| nonexistent_sample_id | task_exists | 1 | true | false | true |
| unknown_schema_field | schema_strict | 1 | true | false | true |
| fixture_impersonating_real | fixture_provenance | 1 | true | false | true |

（全部 validator-targeted mutation 同样从同次 `metrics.json` 读取，
21 条全部 `check_exists=true / target_passed=false / detected=true`。）

m16（同 id 不同内容冲突）原先翻转 `has_signals` 和 `signal_count` 会让
`signal_count_consistency` / `has_signals_consistency` 先失败，掩盖真正的
冲突。本次改为只改 `started_at` / `completed_at`（参与 content hash 但不
触发任何 per-item 规则），使冲突成为唯一失败点。

## 四类元负例

`_run_importer_meta_negatives()` 构造 5 类合成报告，直接喂给 runner 使用的
`_evaluate_detection()`（与正式 mutation 走同一函数）。每条断言
`detected=False`：

| 元负例 | 构造 | 预期 | 实际 | 通过 |
|---|---|---|---|---|
| meta_neg_exit1_target_true | exit=1，target.passed=true | 不检测 | detected=False | ✓ |
| meta_neg_exit1_target_absent | exit=1，目标不在 checks 中 | 不检测 | detected=False | ✓ |
| meta_neg_exit1_only_unrelated_false | exit=1，仅无关 check 失败，target=true | 不检测 | detected=False | ✓ |
| meta_neg_report_missing | exit=1，报告文件不存在 | 不检测 | detected=False | ✓ |
| meta_neg_report_corrupt | exit=1，报告非合法 JSON | 不检测 | detected=False | ✓ |

旧 runner（`check_exists=True / target_passed=not detected`）在 MN1/MN3
会错误返回 detected=true。新 runner 在全部 5 类正确返回 false。

## 退化 κ / stage policy / readiness invariant 回归

- 全 true has_signals → `kappa_non_degenerate` 失败，exit 1，target
  passed=false。✓
- 全 false has_signals → 同上。✓
- `calibration_allowed=true` → `calibration_not_allowed` 失败。✓
- stage policy 文件缺失 → `calibration_not_allowed` 失败
  （`stage_policy_file_missing`）。✓
- stage policy `calibration_allowed="yes"`（类型错误）→ 失败
  （`calibration_allowed_wrong_type`）。✓
- 零真实候选 → prepare 输出 exit 2 / BLOCKED，独立 readiness invariant，
  不计入 mutation 分母。✓

## Evidence 文件职责与一致性

采用**方案 B**：`human-annotation-contract-metrics.json` 只保留 validator
结果，mutation 明细只在 `human-annotation-mutation-gate.json`。机器聚合
门禁验证：

- contract-metrics.json 含字段：`status`、`passed`、`checks`、
  `human_verified_count`、`human_labels_complete`、`calibration_allowed`、
  `fixture_count`、`real_count`。✓
- contract-metrics.json **不含** mutation 结果字段（`results` /
  `detected_count`）。✓
- mutation-gate.json 含字段：`passed`、`total_mutations`、
  `detected_count`、`results`、`meta_negatives`、
  `meta_negatives_passed`。✓
- 每个 mutation result 含 `target_check` / `check_exists` /
  `target_passed` / `detected`。✓

机器一致性检查脚本输出：
`Responsibility check PASS: all declared fields present, no drift`

## 验收命令及真实退出码

| 命令 | 退出码 |
|---|---|
| `.venv/bin/ruff check signal_miner tests scripts` | 0 |
| `.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py` | 0（36 passed） |
| `.venv/bin/python -m pytest -o addopts= -q` | 0（260 passed） |
| `.venv/bin/python scripts/p13_2_annotation_mutation_gate.py` | 0（26/26 mutations, 1/1 invariants, 5/5 meta-negatives） |
| `.venv/bin/python scripts/p13_1_behavior_probe.py` | 0（PASS） |
| `.venv/bin/python scripts/p13_2_validate_goldset.py` | 0（READY） |
| `python3 -m json.tool docs/P13-2-evidence/human-annotation-contract-metrics.json >/dev/null` | 0 |
| `python3 -m json.tool docs/P13-2-evidence/human-annotation-mutation-gate.json >/dev/null` | 0 |
| `git diff --check` | 0 |

额外机器断言：

```
rg -n 'target_check field is used for reporting only|"check_exists": True|"target_passed": not detected' scripts/p13_2_annotation_mutation_gate.py
```

→ 无命中。✓

## 状态不变量与未覆盖风险

**状态不变量（fixture-only 运行）：**

- `status = FIXTURE_PASS`
- `human_verified_count = 0`
- `human_labels_complete = false`
- `calibration_allowed = false`
- `fixture_count = 120`，`real_count = 0`

**未覆盖风险：**

- 真实人工标签仍为 0，本 fix-2 仅证明工具链可信，不解除 P13-2-2-2 冻结。
- importer 的 `fixture_provenance` 检查依赖 id 中的标记词；若真实标注
  误用含这些词的 id 会被误拒（已在 `_FIXTURE_ID_TAGS` 中限定为明显标记）。
- content hash 函数不含 `fixture` 字段，故翻转 fixture 不会改变 hash；
  m20 必须同时改 `started_at` 才能避免幂等跳过。
