# P13-2-2-1A fix-4 交付报告：门禁集合与原子证据发布闭环

交付日期：2026-07-13
返修依据：`docs/acceptance-P13-2-2-1A-fix-3-commander-20260713.md`、`docs/deepseek-instruction-P13-2-2-1A-fix-4.md`

## 结论

**两个 Commander 阻断（P0-1 / P0-2）全部关闭。P1-1（测试未覆盖主路径）也通过重构解决。全量质量门禁通过。**

## 阻断关闭映射

### P0-1 关闭：版本化精确门禁集合 → exact-set 验证

**Commander 反例**：任意 1/1 未知 mutation + 0 pack invariant 仍 exit 0 / passed=true。门禁集合可被静默缩减或替换。

**根因**：orchestrator 只验证 count 一致性，不验证 mutation/invariant/meta-negative 的精确 names 集合。

**修复**：
1. **创建版本化契约模块** `signal_miner/evaluation/p13_2_gate_contract.py`：
   - 23 个 pack trust mutation 名称
   - 34 个 annotation mutation 名称
   - 2 个 pack readiness invariant 名称
   - 1 个 annotation readiness invariant 名称
   - 5 个 annotation meta-negative 名称
   - `contract_schema_version = "contract-1.0.0"`
   - `contract_sha256 = "45c134efc1e311cb53413a7fe094e323716aab954b95b55882c64b978d798d5e"`
2. **Orchestrator `_check_exact_set`**：对每类集合执行 exact-set equality（frozenset 比较）——缺失、多余、重复、改名、未知替换全部 fail。
3. **两个 gate 回写 contract_sha256**：gate evidence 包含 `contract_sha256`、`contract_schema_version`、`exit_code`、`command`。Orchestrator 验证三份文件 contract_sha256 一致。
4. **Commander 反例验证**：1/1 arbitrary + 0 invariants → orchestrator `exit 1 / passed=false`。

---

### P0-2 关闭：Single immutable bytes snapshot + 原子 os.replace 发布

**Commander 反例**：SHA 在复制前计算，复制后不复核。文件在 SHA 计算与复制之间被篡改为 `passed=false`，最终 metrics 记录旧 SHA 和 `passed=true`，实际落盘 gate 已是 `passed=false`。

**根因**：orchestrator 先对临时文件计算 SHA，再用 `write_text` 复制（两次读取之间可变化）。

**修复**：
1. **单次 immutable bytes snapshot**：`_run_gate` 返回 `(exit_code, bytes)`。parse、validate、SHA 全部基于同一份 bytes。不再从源路径读第二次。
2. **`_publish_atomic`**：写同目录临时文件 → flush + fsync → `os.replace` → 读回验证 SHA 与来源 bytes 一致。任一失败返回 errors。
3. **Metrics 为 commit marker**：两个 gate 发布并验证后，才原子发布 metrics。Metrics 包含 `orchestrator_finished_at` 和 artifact SHA。
4. **Contract SHA 一致性**：三个 evidence 文件全部包含相同 `contract_sha256` 和 `run_id`。

---

### 测试重写：真实 main() 调用

- 所有测试通过可注入 `gate_runner` 参数调用真实 `orchestrator_main()`，不再复制验证逻辑。
- 正例使用完整 23/34/2/1/5 契约数据（非 1/1 空壳）。
- 18 项测试：1 正向 + 16 元负例 + 1 恢复。

## 16 类元负例

| # | 场景 | exit | final passed |
|---|------|------|-------------|
| MN01 | pack mutation 缺一项 | 1 | false |
| MN02 | annotation mutation 缺一项 | 1 | false |
| MN03 | mutation 多一项未知名称 | 1 | false |
| MN04 | mutation 名称重复 | 1 | false |
| MN05 | 用未知 mutation 替换必需项 | 1 | false |
| MN06 | pack invariant 缺一项 | 1 | false |
| MN07 | annotation invariant 缺失 | 1 | false |
| MN08 | annotation meta-negative 缺一项 | 1 | false |
| MN09 | 子进程 exit≠0, evidence 伪绿 | 1 | false |
| MN10 | evidence exit_code 与真退出码不一致 | 1 | false |
| MN11 | run_id 不同 | 1 | false |
| MN12 | generated_at 窗口外 | 1 | false |
| MN13 | contract_sha256 mismatch | 1 | false |
| MN14 | _publish_atomic roundtrip 正常 | 0 | true |
| MN15 | Commander coverage-shrink (1/1 + 0 inv) | 1 | false |
| MN16 | SHA race: tamper after publish | 0→tamper→SHA mismatch verified | N/A |

---

## Commander 反例复验

1. **Coverage shrink**（MN15）：1/1 `arbitrary_unrecognized_probe` + 0 pack invariants → `exit 1 / passed=false`
2. **SHA race**（MN16）：orchestrator 正常跑完记录 SHA → tamper 发布文件 → 重读 SHA → `recorded_sha != actual_sha`（sha race detected）

## 三份 evidence 一致性

```
run_id:  all three identical
contract_sha256: all three = 45c134efc1e311cb...
artifact_sha256 (metrics) = source_bytes SHA → matches published file
```

## 质量门禁全量结果

| 门禁 | 结果 |
|------|------|
| Ruff | All checks passed! |
| 全量 pytest | 306 passed, 3 warnings |
| 契约测试（3 files） | 83 passed |
| Orchestrator | PASS (23/23 + 34/34, contract ok) |
| Behavior probe | PASS |
| Goldset validator | READY / passed=true |
| Evidence JSON (3 files) | VALID |
| Git diff --check | PASS |

## 文件变更清单

| 文件 | 类型 | 变更 |
|------|------|------|
| `signal_miner/evaluation/p13_2_gate_contract.py` | **新增** | 版本化门禁契约（23/34/2/1/5 + contract_sha256） |
| `scripts/p13_2_pack_trust_contract_metrics.py` | 完全重写 | exact-set 验证、单次 bytes 快照、原子 os.replace、contract SHA 核对 |
| `scripts/p13_2_pack_trust_mutation_gate.py` | CLI 增强 | 添加 contract_sha256、exit_code、command 字段 |
| `scripts/p13_2_annotation_mutation_gate.py` | CLI 增强 | 同上 |
| `tests/test_p13_2_pack_trust_metrics_contract.py` | 完全重写 | 18 项测试，真实 main() 调用，完整集合契约，无复制逻辑 |
| `docs/P13-2-evidence/*.json` | 更新 | 含 contract_sha256、exit_code、artifact_sha256、timestamps |

## 完成边界

通过仍只证明 P13-2-2-1A 外部 pack 信任根工具、证据发布链和聚合逻辑可信。真实授权候选为 0，P13-2-2-2 与校准继续冻结。
