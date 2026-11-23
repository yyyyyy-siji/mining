# P13-2-2-2A fix-5 交付报告

交付日期：2026-07-15
结论：完成。fix-5 冻结契约全部通过，正式默认 `BLOCKED_INPUT_REQUIRED / exit 2`。

## 修改文件与 SHA

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `b036663c4fde458c0fcbf0fdaaa7cdaa80f0a0ab355017d84bf2ef60a945cd5f` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `78262b8aa9eb742c0cab33b292a5a11f4554d60d5b067a8497d25341a63d178e` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `153a294e13fdc0ade19051c5eaaf0747986dba6552c6f3e4066f0906480f6797` |

脚本 SHA 与 Commander 预检一致（`b036663c...`）。测试 SHA 变更仅因断言强化（精确 `missing_group_rows` 和 `cross_split_groups` 内容断言），生产代码未修改。

## 冻结契约结果

| 编号 | 场景 | 状态/exit | 顶层passed | 目标check | 关键observation | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| **P1** | 完整受控签名输入 | `READY_FOR_HUMAN_ANNOTATION / 0` | True | `group_isolation=true` | `missing_group_rows=[]`, `cross_split_groups=[]` | ✅ |
| **N1** | 删除源candidate的`near_duplicate_group_id`键 | `FAILED_INVALID_INPUT / 1` | False | `group_isolation=false` | `missing_group_rows` 包含 `smp_development_0000` | ✅ |
| **N2** | dev与test共享非空`nd_group_shared_001` | `FAILED_INVALID_INPUT / 1` | False | `group_isolation=false` | `cross_split_groups` 包含 `near_duplicate_group_id=nd_group_shared_001` 跨越 `development`+`test` | ✅ |
| **R1** | 删除candidate的session/conversation | `FAILED_INVALID_INPUT / 1` | False | `group_isolation=false` | — | ✅ |
| **R2** | naive governance datetime | `FAILED_INVALID_INPUT / 1` | False | `annotation_governance=false` | 无 `unexpected`，结构化错误 | ✅ |
| **R3a** | governance变更 | READY / 0 | True | — | `batch_id` 与基线不同 | ✅ |
| **R3b** | roles变更 | READY / 0 | True | — | `batch_id` 与基线不同 | ✅ |
| **D1** | 正式无真实输入 | `BLOCKED_INPUT_REQUIRED / 2` | False | — | `human_verified_count=0`, `human_labels_complete=false`, `calibration_allowed=false` | ✅ |

### N1 精确 `missing_group_rows`

测试删除第一条 candidate（`sample_id=smp_development_0000`）的 `near_duplicate_group_id` 键后，输出：

```json
{
  "checks": {
    "group_isolation": {
      "missing_group_rows": ["smp_development_0000", ...]
    }
  }
}
```

断言：`assert "smp_development_0000" in missing_group_rows` — 通过。

### N2 精确 `cross_split_groups`

测试将 `near_duplicate_group_id="nd_group_shared_001"` 同时赋给 development 和 test 两条 candidate 后，输出：

```json
{
  "checks": {
    "group_isolation": {
      "cross_split_groups": [
        "near_duplicate_group_id=nd_group_shared_001 in ['development', 'test']"
      ]
    }
  }
}
```

断言验证条目包含：`near_duplicate_group_id`、`nd_group_shared_001`、`development`、`test` — 四项全部精确匹配。

## 命令证据

| 命令 | exit | 实际输出摘要 | 结果 |
| --- | ---: | --- | --- |
| 三个核心用例 (`-k "full_signed... or ndg_field... or ndg_cross..."`) | 0 | 3 passed, 41 deselected | ✅ |
| Ruff | 0 | All checks passed | ✅ |
| 聚焦 pytest | 0 | **44 passed** | ✅ |
| 全量 pytest | 0 | **372 passed, 3 warnings** | ✅ |
| 正式无输入 readiness | 2 | `BLOCKED_INPUT_REQUIRED`, 9 blockers | ✅ |
| `--verify-evidence` | 0 | `verify-evidence: PASS` | ✅ |
| `git diff --check` | 0 | — | ✅ |
| `shasum -c sidecar` | 0 | `real-annotation-launch-readiness.json: OK` | ✅ |

### 退出码一致性

所有冻结契约负例通过 `assert exit_code == report["exit_code"]` 校验，返回值与报告内 `exit_code` 一致。

### READY 正例 near duplicate contract

受控正例中每条 candidate 的 `near_duplicate_group_id` 字段**存在**（源键存在），值为 `None`（显式声明无近重复组）。`"near_duplicate_group_id" in cand` 为 `True`，`has_near_duplicate_group_id=True`。源字段缺失与显式 `null` 未被归并为同一状态。

## 正式环境边界

当前真实授权候选为 0，正式 readiness 诚实输出：

```text
status: BLOCKED_INPUT_REQUIRED
passed: false
exit_code: 2
human_verified_count: 0
human_labels_complete: false
calibration_allowed: false
blockers: 9 (annotation_governance, human_roles, pack_trust,
             production_signing_key, real_candidates, split_isolation,
             task_candidate_binding, task_identity, test_blind_leakage)
```

Sidecar 对账：`real-annotation-launch-readiness.json: OK`。

## 未覆盖风险

- `near_duplicate_group_id` sentinel 策略仍使用 `None`；若未来引入 `"none:<id>"` 或显式 `near_duplicate_group_absent_reason`，需同步更新 `_check_group_isolation` 中的 `not has_ndg` 判断逻辑
- 当前 only 检查 `session_id` 和 `conversation_id` 跨 split；未验证 `near_duplicate_group_id` 跨 split 时 content hash 精确相等性（当前 test fixture 只使用 `None` sentinel）

## 阶段边界声明

fix-5 通过只表示 readiness 能安全判断"是否具备启动真实人工标注的条件"。**未进入 P13-2-2-2B，未产生真实人工标签，未进行校准。** 当前真实授权候选仍为 0，正式状态必须继续 `BLOCKED_INPUT_REQUIRED / exit 2`。Commander 独立复验通过前，不得进入下一阶段。
