# P13-2-2-1A fix-3 交付报告：证据Orchestrator与顶层Passed闭环

交付日期：2026-07-13
返修依据：`docs/acceptance-P13-2-2-1A-fix-2-commander-20260713.md`、`docs/deepseek-instruction-P13-2-2-1A-fix-3.md`

## 结论

**两个 Commander 阻断（P0-1 / P1-1）全部关闭。全量质量门禁通过。**

## 阻断关闭映射

### P0-1 关闭：聚合器假绿 → 完整复算 passed

**Commander 反例**：把 annotation gate 的 `passed`、`meta_negatives_passed`、`readiness_invariants_passed` 同时设为 `false` 后，聚合器仍 exit 0，输出 `passed=true`。

**根因**：`contract_metrics.py` 输出中的 `"passed": True` 是硬编码常量，不是从 gate 层级字段推导出的计算结果。读取了 `ptmg.passed`、`amg.passed`、`invariants`、`meta_negatives` 但从未用于判定。

**修复**：`p13_2_pack_trust_contract_metrics.py` 重写为 orchestrator（不只聚合器，也运行 gate）。

最终 `passed` 必须同时 AND：
- pack gate `passed is strictly True`（非 truthy 字符串、非 1）
- pack gate `readiness_invariants_passed is strictly True`
- annotation gate `passed is strictly True`
- annotation gate `readiness_invariants_passed is strictly True`
- annotation gate `meta_negatives_passed is strictly True`
- pack trust 和 annotation 子进程 exit=0
- run_id 一致性检查通过
- 时间窗口检查通过
- 逐行严格契约全部通过（child_exit==1、check_exists、target_passed===False、detected===True）
- 声明计数与实际计数一致

任一 false/null/缺失/错误类型/unknown → exit 1，`passed=false`。禁止硬编码 `"passed": True`。

---

### P1-1 关闭：run_id 形成同次运行证据链

**Commander 发现**：两 gate JSON 无 `run_id`/`generated_at`。任意文件混入新旧不同次运行产物，聚合器无法识别。

**修复**：
1. **Orchestrator 生成 run_id**：`p13_2_pack_trust_contract_metrics.py` 先生成 `run_id` + `started_at`，再用 `--run-id` 参数传入两个 gate。
2. **Gate 回写 run_id**：两个 mutation gate 新增 `--run-id` 和 `--out` CLI 参数。Gate 将传入的 `run_id` + 各自的 `generated_at` + `phase` 写入输出 JSON。
3. **三方验证**：orchestrator 读回 gate JSON，验证 (a) run_id 一致、(b) generated_at 在 `[started_at, finished_at]` 窗口内。
4. **原子拷贝**：验证通过后，先把 gate JSON 从临时目录拷贝到 evidence 目录，再写 metrics JSON，确保三者同次。

**结果**：
```
pack-trust-mutation-gate.json:      run_id=651dbb15-83be-43...
human-annotation-mutation-gate.json: run_id=651dbb15-83be-43...
pack-trust-contract-metrics.json:    run_id=651dbb15-83be-43...
→ 全部相同
```

---

## 12 类元负例验证

| # | 场景 | 结果 |
|---|------|------|
| MN1 | pack gate `passed=false`，逐行仍全 true | exit 1, passed=false |
| MN2 | annotation gate `passed=false`，逐行全 true | exit 1, passed=false |
| MN3 | annotation `meta_negatives_passed=false` | exit 1, passed=false |
| MN4 | annotation `readiness_invariants_passed=false` | exit 1, passed=false |
| MN5 | pack `readiness_invariants_passed=false` | exit 1, passed=false |
| MN6 | `passed="true"`（string 非 bool） | exit 1, passed=false |
| MN7 | 两个 gate run_id 不同 | exit 1, passed=false |
| MN8 | gate 缺失 run_id | exit 1, passed=false |
| MN9 | gate generated_at 早于 orchestrator start | exit 1, passed=false |
| MN10 | gate generated_at 缺失 | exit 1, passed=false |
| MN11 | 逐行检测 child_exit≠1 | exit 1, passed=false |
| MN12 | 逐行检测 target_passed=True | exit 1, passed=false |

全部通过 `tests/test_p13_2_pack_trust_metrics_contract.py`（13 项 = 12 元负例 + 1 正向）。

---

## 质量门禁全量执行结果

| 门禁 | 命令 | 结果 |
|------|------|------|
| Ruff | `ruff check signal_miner tests scripts` | **All checks passed!** |
| 全量 pytest | `pytest -q` | **302 passed, 3 warnings** |
| Pack trust + annotation + metrics 契约 | 三大合约测试文件 | **78/78 PASS** |
| Orchestrator | `python scripts/p13_2_pack_trust_contract_metrics.py` | **PASS (23/23 + 34/34, exit=0)** |
| Behavior probe | `python scripts/p13_1_behavior_probe.py` | **PASS** |
| Goldset | `python scripts/p13_2_validate_goldset.py` | **READY / passed=true** |
| Evidence JSON (3 files) | `python3 -m json.tool` | **VALID** |
| Git diff --check | `git diff --check` | **PASS** |

---

## 文件变更清单

| 文件 | 类型 | 变更摘要 |
|------|------|----------|
| `scripts/p13_2_pack_trust_contract_metrics.py` | 完全重写 | 从 aggregator 升级为 orchestrator：运行两个 gate → 验证 → 拷贝 → 写 metrics。完整复算 passed（无硬编码 True）。run_id 一致性 + 时间窗口 + 逐行契约。_check_row_contract 独立可调用（供 meta-negative 测试） |
| `scripts/p13_2_pack_trust_mutation_gate.py` | CLI 增强 | 新增 argparse、`--run-id`、`--out` 参数。输出 JSON 含 `run_id`、`generated_at`、`phase` |
| `scripts/p13_2_annotation_mutation_gate.py` | CLI 增强 | 新增 argparse、`--run-id`、`--out` 参数。输出 JSON 含 `run_id`、`generated_at`、`phase` |
| `tests/test_p13_2_pack_trust_metrics_contract.py` | **新增** | 13 项测试：12 元负例 + 1 正向。`_UNSET` sentinel 辅助合成 gate payload。直接调用 orchestrator 模块的验证函数 |
| `docs/P13-2-evidence/pack-trust-mutation-gate.json` | 更新 | 新增 `run_id`、`generated_at`、`phase` 字段（由 orchestrator 通过 gate 写入） |
| `docs/P13-2-evidence/human-annotation-mutation-gate.json` | 更新 | 同上 |
| `docs/P13-2-evidence/pack-trust-contract-metrics.json` | 更新 | 新增 `orchestrator_started_at`、`exit_code`、`artifact_sha256`。passed 由完整复算得出 |

---

## 回归状态

- 省略 dataset manifest → exit 1（未回退）
- fixture 缺 pack manifest → exit 1（未回退）
- production/development/empty/staging 测试密钥拒绝（未回退）
- pack gate 23/23、annotation gate 34/34 保持
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`

---

## Commander 反例复验

1. **P0-1 反例**：设置 annotation gate `passed=false`、`meta_negatives_passed=false`、`readiness_invariants_passed=false`，即便 34/34 mutation detected → orchestrator exit 1, final passed=false, 列出三个失败原因。
2. **P1-1 反例**：两个 gate run_id 不同 → orchestrator exit 1；gate 缺失 run_id → orchestrator exit 1。

## 完成边界

通过仍只表示外部 pack 信任根工具、证据链和聚合逻辑可信。真实授权候选为 0，P13-2-2-2 与校准继续冻结。
