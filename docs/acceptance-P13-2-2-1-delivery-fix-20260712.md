# P13-2-2-1 fix 交付报告：mutation 假阳性与退化 κ 修复

交付日期：2026-07-12

## 结论

- fixture 工具链：PASS（FIXTURE_PASS）
- 真实候选：BLOCKED（0 条合格授权候选）
- annotation mutation：**PASS（26/26 严格 exit=1 + 1/1 readiness invariant）**
- 退化 κ：**阻断**（全 true / 全 false 标签返回 DEGENERATE_KAPPA=-1.0，不能 READY）
- 校准发布：NOT_ALLOWED（`calibration_allowed=false` 从冻结阶段策略文件读取）

## 逐项回应 Commander 阻断

### P0-1：mutation gate 假阳性 → 已修复

**根因**：两个 mutation 被特殊放行——`calibration_flag_ignored` 的 `detected` 被手工反转（真实 exit=0/check=true 被改成 detected=true）；`zero_real_candidates` 的正常 exit=2/BLOCKED 被计作 detected。

**修复**：
1. 删除 `calibration_flag_ignored` 的 `detected` 反转逻辑
2. 把 `zero_real_candidates` 移出 mutation 计数，改为独立 readiness invariant（期望 exit=2，不计入 detected_count）
3. 统一判定函数：只有 `child_exit==1 + check_exists + target_passed is False` 才算 detected
4. 任何 exit=0、exit=2、异常或 check 缺失 → NOT detected → gate FAIL

**证据**（同一次运行 `docs/P13-2-evidence/human-annotation-mutation-gate.json`）：

```json
{
  "passed": true,
  "total_mutations": 26,
  "detected_count": 26,
  "readiness_invariants_passed": true
}
```

所有 26 条 mutation 的 `child_exit` 均为 1、`check_exists` 均为 true、`target_passed` 均为 false。

### P0-2：退化 Cohen's κ 可绕过门槛 → 已修复

**根因**：`cohens_kappa` 在全 true / 全 false（无类别变化）时返回 1.0，注释声称返回 0.0 但实际返回 1.0。

**修复**：
1. 引入 `DEGENERATE_KAPPA = -1.0` 哨兵值
2. 退化情形（`pe ≈ 1.0` 即两个 rater 的标签分布完全相同且无类别变化）返回 `-1.0`
3. `compute_agreement_metrics` 新增 `kappa_degenerate` 布尔字段
4. validator 新增 `kappa_non_degenerate` check：有 pairs 但退化 → check=false → exit=1
5. readiness 阈值判定：`kappa_ok = bool(pairs) and (not kappa_degenerate) and kappa >= 0.70`

**新增两个正式 CLI mutation**：
- `all_true_degenerate_kappa`（#24）：A/B 标注 has_signals 全设为 true → exit=1，`kappa_non_degenerate=false`
- `all_false_degenerate_kappa`（#25）：A/B 标注 has_signals 全设为 false → exit=1，`kappa_non_degenerate=false`

**单元测试验证**：
```python
cohens_kappa([True] * 20, [True] * 20)  == -1.0  # DEGENERATE
cohens_kappa([False] * 20, [False] * 20) == -1.0  # DEGENERATE
cohens_kappa([T,F,T,F,T,F], [T,F,T,F,T,F]) > 0.5  # valid high kappa
cohens_kappa([T,T,T,T,F,F], [F,F,F,F,T,T]) < 0.0  # valid negative kappa
```

### P1-1：calibration 禁止项没有可变输入 → 已修复

**根因**：validator 把 `cal_allowed=False` 硬编码，向 store 注入 `calibration_allowed=true` 被静默忽略。

**修复**：
1. 新增冻结阶段策略文件 `docs/P13-2/stage-policy.json`：
   ```json
   {"stage": "P13-2-2-1", "calibration_allowed": false}
   ```
2. validator 新增 `--stage-policy` 参数（默认指向该文件）
3. `calibration_not_allowed` check 真实读取该文件：
   - 文件缺失 → fail
   - JSON 损坏 → fail
   - `calibration_allowed` 键缺失 → fail
   - 类型错误（非 bool） → fail
   - 值为 true → fail
4. 三条 mutation 分别变异该文件：
   - `calibration_policy_true` → exit=1，`calibration_not_allowed=false`
   - `calibration_policy_missing` → exit=1，`calibration_not_allowed=false`
   - `calibration_policy_wrong_type` → exit=1，`calibration_not_allowed=false`

### P1-2：交付报告声明的 contract-metrics.json 不存在 → 已修复

**根因**：交付报告引用了未生成的 artifact。

**修复**：正式生成三份 evidence JSON（均通过 `python3 -m json.tool` 校验）：

```
docs/P13-2-evidence/human-annotation-contract-metrics.json  ← validator 输出
docs/P13-2-evidence/human-annotation-mutation-gate.json     ← mutation gate 输出
docs/P13-2-evidence/human-annotation-readiness.json         ← readiness 输出
```

metrics JSON 记录每条 mutation 的 `exit`、`target_check`、`target_passed`、`detected`，以及独立 readiness invariant。顶层 `passed` 由逐项真实结果复算。

## 修改文件

### 修改

| 文件 | 说明 |
| --- | --- |
| `signal_miner/evaluation/human_annotation.py` | 退化 κ 返回 `DEGENERATE_KAPPA=-1.0`；`compute_agreement_metrics` 新增 `kappa_degenerate` 字段 |
| `scripts/p13_2_validate_human_annotations.py` | 新增 `--stage-policy`；`calibration_not_allowed` 真实读取策略文件；新增 `kappa_non_degenerate` check；退化 κ 阻断 READY |
| `scripts/p13_2_annotation_mutation_gate.py` | 统一判定函数；删除 detected 反转；zero_real_candidates 改为独立 invariant；新增 calibration policy ×3 mutation + 退化 κ ×2 mutation |
| `tests/test_p13_2_human_annotation_contract.py` | 新增 7 项测试（退化 κ ×4、阶段策略 ×3） |

### 新增

| 文件 | 说明 |
| --- | --- |
| `docs/P13-2/stage-policy.json` | 冻结阶段策略文件（`calibration_allowed=false`） |

## 验收命令真实退出码

```bash
$ .venv/bin/ruff check signal_miner tests scripts
# exit 0 — All checks passed!

$ .venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
# exit 0 — 25 passed

$ .venv/bin/python -m pytest -o addopts= -q
# exit 0 — 249 passed, 3 warnings

$ .venv/bin/python scripts/p13_2_annotation_mutation_gate.py
# exit 0 — PASS (26/26 mutations, 1/1 invariants)

$ .venv/bin/python scripts/p13_1_behavior_probe.py
# exit 0 — Overall: PASS

$ .venv/bin/python scripts/p13_2_validate_goldset.py
# exit 0 — {"status": "READY", "passed": true}

$ python3 -m json.tool docs/P13-2-evidence/human-annotation-contract-metrics.json >/dev/null
# exit 0 — valid JSON

$ git diff --check
# exit 0 — clean
```

## Mutation 明细（26 条 + 1 invariant）

| # | mutation | target check | exit | detected |
| --- | --- | --- | --- | --- |
| 1 | fixture_counted_as_real | real_vs_fixture_count | 1 | true |
| 2 | llm_suggestion_as_gold_no_action | assisted_review_action | 1 | true |
| 3 | test_pack_has_model_confidence | no_blind_leakage_in_tasks | 1 | true |
| 4 | a_reads_b_label | schema_strict | 1 | true |
| 5 | same_pseudonym_a_and_b | no_self_pairing | 1 | true |
| 6 | task_hash_tampered | task_identity | 1 | true |
| 7 | content_hash_tampered | task_identity | 1 | true |
| 8 | signal_count_mismatch | signal_count_consistency | 1 | true |
| 9 | has_signals_false_but_signals_nonempty | has_signals_consistency | 1 | true |
| 10 | invalid_signal_type | signal_type_whitelist | 1 | true |
| 11 | unicode_evidence_offset_error | evidence_offsets | 1 | true |
| 12 | evidence_empty | summary_and_evidence_nonempty | 1 | true |
| 13 | summary_empty | summary_and_evidence_nonempty | 1 | true |
| 14 | pii_email_leak_in_notes | no_pii_leak | 1 | true |
| 15 | calibration_policy_true | calibration_not_allowed | 1 | true |
| 16 | calibration_policy_missing | calibration_not_allowed | 1 | true |
| 17 | calibration_policy_wrong_type | calibration_not_allowed | 1 | true |
| 18 | same_id_different_content_conflict | import_conflict | 1 | true |
| 19 | nonexistent_dataset_id | import_reject | 1 | true |
| 20 | nonexistent_sample_id | import_reject | 1 | true |
| 21 | unknown_schema_field | import_reject | 1 | true |
| 22 | llm_copy_as_gold_blind | import_reject | 1 | true |
| 23 | ab_task_packs_missing | task_pack_files_present | 1 | true |
| 24 | double_annotation_insufficient | double_annotation_coverage | 1 | true |
| 25 | all_true_degenerate_kappa | kappa_non_degenerate | 1 | true |
| 26 | all_false_degenerate_kappa | kappa_non_degenerate | 1 | true |

Readiness invariant（独立，不计入 mutation 分母）：

| name | expected | actual | passed |
| --- | --- | --- | --- |
| zero_real_candidates_blocked_exit2 | exit=2 | exit=2 | true |

## 状态不变量

```json
{
  "human_verified_count": 0,
  "human_labels_complete": false,
  "calibration_allowed": false,
  "fixture_only": true
}
```

## 完成边界

本 fix 通过只代表 P13-2-2-1 工具可信。真实授权候选仍为 0 时，P13-2-2-2、P13-2-3 和 P13-2-4 继续冻结。
