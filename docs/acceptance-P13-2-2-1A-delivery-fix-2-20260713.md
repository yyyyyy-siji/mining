# P13-2-2-1A fix-2 交付报告：Dataset Manifest 强制消费与证据同次聚合

交付日期：2026-07-13
返修依据：`docs/acceptance-P13-2-2-1A-fix-commander-20260713.md`、`docs/deepseek-instruction-P13-2-2-1A-fix-2.md`

## 结论

**三个 Commander 阻断（P0-1 / P0-2 / P1-1）全部关闭。全量质量门禁通过。**

该 fix 关闭了以下未在 fix-1A 中解决的遗留：
- 省略 `--dataset-manifest` 后 importer 仍 pack_trust=true, exit 0, store 创建
- Fixture 缺 pack manifest 返回 exit 2，被 mutation gate 特殊改写为 detected
- Contract metrics 记录 21/21/1 invariant，与实际 20/20/2 invariants 矛盾

## 阻断关闭映射

### P0-1 关闭：Dataset manifest 强制消费

**Commander 反例**：先对合法 dataset manifest 签名 pack manifest，导入时提供 manifest 但省略 `--dataset-manifest` → `exit 0 / pack_trust.passed=true / store_created=true`。

**根因**：importer 的 `--dataset-manifest` 默认空值 → `dataset_manifest_path=None` 传入 `verify_manifest_file()`，在 `pack_trust.py` 第 275 行 `if manifest and dataset_manifest_path is not None:` 被跳过。签名载荷包含 dataset_manifest_sha256 字段，但消费端从未强制验证。

**修复**：
1. **Importer 业务层检查**：`_verify_pack_trust` 在 manifest 存在时强制检查 `dataset_manifest_path`。None → `FAIL_MISSING_DATASET_MANIFEST` exit 1；文件不存在 → `FAIL_MISSING_DATASET_MANIFEST` exit 1。
2. **Verifier 无跳过**：`verify_manifest_file` 原为 `if manifest and dataset_manifest_path is not None:`，改为 `if manifest:` 后先检查 `dataset_manifest_path is None` → 记录错误，之后才执行 SHA/dataset_id 核对。
3. **新增 4 类 CLI mutation**：
   - 省略 `--dataset-manifest` → `FAIL_MISSING_DATASET_MANIFEST` exit 1
   - 指向不存在文件 → exit 1
   - 指向相同 dataset_id 但不同内容 → exit 1
   - 声明路径与实际路径不匹配（声明 `manifest.json`，实际为 `custom_name.json`）→ exit 1

**验证**：mutation gate 4 类新 mutation 全部 `detected=true / child_exit=1 / check_exists=true / target_passed=false`。

---

### P0-2 关闭：Fixture 缺 manifest 统一 exit 1

**Commander 反例**：`test_env_fixture_no_manifest_rejected` 使用自定义 runner，实际 exit 2 却被 `detected = (exit != 0 and not store_created)` 改写为 `detected=true`。违反计数 mutation 统一契约：`child_exit==1 AND target exists AND target.passed==false AND detected==true`。

**根因**：上一版 `_verify_pack_trust` 对 manifest 缺失统一返回 `BLOCKED_MISSING_MANIFEST`（exit 2）。mutation gate 无法通过统一 `run_mutation()` + `_evaluate_detection()` 流动，只能自定义 runner + 自定义 detected 规则。

**修复**：
1. `_verify_pack_trust` 区分 fixture/production：
   - **Fixture + 缺 manifest** → `FAIL_MISSING_PACK_MANIFEST` error_kind → exit 1（输入契约错误）
   - **Production + 缺 manifest** → `BLOCKED_MISSING_MANIFEST` error_kind → exit 2（readiness invariant）
2. Importer main()：`FAIL_MISSING_PACK_MANIFEST` 加入 `fail_exit1_kinds` 集合，统一 exit 1 分发。
3. Mutation gate：删除自定义 runner，改用 `run_mutation(manifest_path=None, dataset_manifest=None)` 走统一流。新增 `_UNSET` sentinel 支持显式跳过 manifest/dataset-manifest 参数。

**验证**：
```
mutation: test_env_fixture_no_manifest_rejected
  child_exit=1, check_exists=True, target_passed=False, detected=True
```

---

### P1-1 关闭：Contract metrics 同次聚合

**Commander 发现**：`pack-trust-contract-metrics.json` 仍写 21/21/1 invariant，与实际 gate 结果的 20/20/2 invariants 矛盾。

**修复**：
1. 创建 `scripts/p13_2_pack_trust_contract_metrics.py`：
   - 读取当前 `pack-trust-mutation-gate.json` 和 `human-annotation-mutation-gate.json`
   - 交叉验证声明数与实际结果数
   - 每个 count mutation 的 strict per-row 契约校验（child_exit==1、check_exists、target_passed==False、detected）
   - 统一 `run_id` + `generated_at` 绑定两个 evidence 文件
2. **5 类 meta-negative**：
   - 任一 count mutation 的 child_exit ≠ 1 → FAIL
   - 声明 mutation 计数与实际不一致 → FAIL
   - readiness invariant 计数漂移 → FAIL
   - dataset-manifest related mutation 少于 1 个 → FAIL（绑定未验证）
   - no-manifest mutation 的 pack_trust=true → FAIL

**输出**：`pack-trust-contract-metrics.json` 现已自动同步为 23/23/2 invariants。

---

## Annotation mutation gate 串联修复

`run_importer_mutation` 和 `run_validator_mutation` 新增 `_re_sign(tmpdir)` 步骤（在 `mutate_fn` 之后）：修改 pack 文件的 mutation 会在重签后走统一 flow。未修改 pack 的 mutation 则无害（重签生成相同的 SHA、相同的 manifest 签名）。

`pack_fixture_wrong_type` mutation 的 target 从 `fixture_provenance` 改为 `pack_trust`：`pack["fixture"] = "yes"`（string）导致 manifest 的 `fixture=True` 与实际 `fixture="yes"` 不匹配，pack_trust 在 pack 层级更早正确捕获。

---

## 质量门禁全量执行结果

| 门禁 | 命令 | 结果 |
|------|------|------|
| Ruff | `ruff check signal_miner tests scripts` | **All checks passed!** |
| 全量 pytest | `pytest -q` | **289 passed, 3 warnings** |
| Pack trust 契约 | `pytest tests/test_p13_2_pack_trust_contract.py` | **22/22 PASS** |
| Annotation 契约 | `pytest tests/test_p13_2_human_annotation_contract.py` | **43/43 PASS** |
| Pack trust mutation gate | `python scripts/p13_2_pack_trust_mutation_gate.py` | **PASS (23/23 mutations, 2/2 invariants)** |
| Annotation mutation gate | `python scripts/p13_2_annotation_mutation_gate.py` | **PASS (34/34 mutations, 1/1 invariants, 5/5 meta-negatives)** |
| Contract metrics | `python scripts/p13_2_pack_trust_contract_metrics.py` | **PASS (23/23 + 34/34, cross-verified)** |
| 行为探针 | `python scripts/p13_1_behavior_probe.py` | **PASS** |
| Goldset 验证 | `python scripts/p13_2_validate_goldset.py` | **READY / passed=true** |
| Evidence JSON | `python3 -m json.tool` | **VALID** |
| Git diff --check | `git diff --check` | **PASS** |

---

## 文件变更清单

| 文件 | 类型 | 变更摘要 |
|------|------|----------|
| `signal_miner/evaluation/pack_trust.py` | 关键改造 | `verify_manifest_file` 不再跳过 None；dataset manifest 缺失 → 错误而非沉默 |
| `scripts/p13_2_import_human_annotations.py` | 关键改造 | `_verify_pack_trust` 区分 fixture/production manifest 缺失；新增 `FAIL_MISSING_DATASET_MANIFEST`；统一 exit 1 路由 |
| `scripts/p13_2_pack_trust_mutation_gate.py` | 完全重写 | 删除自定义 runner；`_UNSET` sentinel 支持 manifest_path=None/dataset_manifest=None；4 类新增 dataset-manifest 缺失/不匹配 mutation |
| `scripts/p13_2_annotation_mutation_gate.py` | 关键改造 | 新增 `_re_sign`；`run_importer_mutation`/`run_validator_mutation` 新增重签步骤；`pack_fixture_wrong_type` target 迁移至 pack_trust |
| `scripts/p13_2_pack_trust_contract_metrics.py` | **新增** | 同次聚合器：从 gate JSON 读取、交叉验证、生成合同指标 |
| `tests/test_p13_2_human_annotation_contract.py` | 关键改造 | 新增 `_sign_dir` helper；3 个涉及 pack 修改的测试在修改后重签 |
| `docs/P13-2-evidence/pack-trust-contract-metrics.json` | 更新 | 自动生成：23/23/2 invariants |
| `docs/P13-2-evidence/pack-trust-mutation-gate.json` | 更新 | 23/23/2 invariants |

---

## 回归状态

- production/development/empty/staging 环境 `--fixture + test key` 继续 exit 1
- test 环境缺注入 key、production 缺生产 key 继续 exit 2 readiness invariant
- 合法 test fixture：同时提供 manifest + dataset-manifest + 签名 + 测试 key → PASS
- P13-2-2-1 的 34 类 annotation mutation、task hash 重算、退化 κ、stage policy 不回退
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`、`production_blocked=true`

---

## Commander 反例复验

1. **P0-1 反例**：合法 manifest，省略 `--dataset-manifest` → `exit 1 / FAIL_MISSING_DATASET_MANIFEST / pack_trust.passed=false / store 不变`
2. **P0-2 反例**：fixture + test env + 缺 `--manifest` → `exit 1 / FAIL_MISSING_PACK_MANIFEST`（不再是 exit 2 特殊改写）
3. **P1-1 反例**：`p13_2_pack_trust_contract_metrics.py` 若有人手动写 21 → FAIL；mutation JSON 缺失 → exit 2；mutation 计数漂移 → FAIL

## 完成边界

本 fix 通过仅表示 pack 信任根工具可信。真实授权候选为 0，P13-2-2-2 与校准继续冻结。
