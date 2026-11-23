# P13-2-2-1A 交付报告：人工任务包外部信任根

## 结论

**PASS** — Pack trust 外部信任根已建立。21/21 pack trust mutation 检测通过，34/34 annotation mutation 无回退，295 项全量测试通过。真实授权候选仍为 0，P13-2-2-2 继续冻结。

## 修改文件

### 新增
- `signal_miner/evaluation/pack_trust.py` — Pack trust 核心模块（manifest 生成/签名/验证/密钥解析）
- `scripts/p13_2_sign_human_task_pack.py` — Pack 签名 CLI（fixture/production 双路径）
- `scripts/p13_2_pack_trust_mutation_gate.py` — 21 类 pack trust mutation gate
- `tests/test_p13_2_pack_trust_contract.py` — 28 项 pack trust 契约测试
- `docs/P13-2/human-task-pack-trust-operations-v1.md` — 操作文档
- `docs/P13-2-evidence/pack-trust-contract-metrics.json` — 契约指标
- `docs/P13-2-evidence/pack-trust-mutation-gate.json` — Mutation gate 证据

### 修改
- `scripts/p13_2_import_human_annotations.py` — 增加 `--manifest`/`--fixture` 参数，`pack_trust` 作为第 0 个结构化 check
- `scripts/p13_2_annotation_mutation_gate.py` — Importer 调用增加 `--fixture` 标志
- `tests/test_p13_2_human_annotation_contract.py` — Importer 调用增加 `--fixture` 标志

## Pack manifest 契约

Manifest schema version 1.0.0，包含：
- `schema_version`、`canonicalization_version`
- `dataset_id`、`fixture`、`fixture_only`
- `signer_key_id`（只存标识，不存密钥）
- `generated_at`
- 4 个 pack 的相对路径、SHA-256、bytes、task_count、annotation_mode、annotator_slot、split、fixture
- `total_task_count`
- `signature`（HMAC-SHA256 hex）

路径安全：所有路径为受控相对路径，禁止绝对路径和 `..`。

## 签名/HMAC 与密钥边界

| 维度 | Fixture 模式 | 生产模式 |
|------|-------------|---------|
| 密钥来源 | 内置 test-only key | `ANNOTATION_PACK_SIGNING_KEY` env |
| key_id | `fixture-test-key-v1` | `production-key` |
| fixture_only | `true` | `false` |
| 无密钥行为 | N/A（内置 key） | exit 2 BLOCKED |
| 密钥泄露 | 密钥不出现在 manifest/report/stdout | 同左 |

密钥泄露扫描：CLEAN — 仓库、docs、evidence JSON 中无生产密钥明文。

## Importer 先验验证

Importer 在处理任何 annotation 前执行 `pack_trust` check：
1. 读取 manifest
2. 验证 schema（version、dataset_id、fixture bool、packs 非空等）
3. 验证路径安全（无 `..`、无绝对路径）
4. 逐 pack 验证 SHA-256、bytes、task_count
5. 验证 HMAC-SHA256 签名
6. 验证 key_id 匹配
7. 验证 manifest fixture 标志与导入模式一致
8. 验证 dataset_id 与 pack 一致

生产模式无 `--manifest` → exit 2 BLOCKED。
Fixture 模式无 `--manifest` → pack_trust passed=true（manifest 可选）。

## Fixture test-only 与真实 BLOCKED

- **Fixture 工具链 PASS**：`fixture_only=true`、`signer_key_id=fixture-test-key-v1`
- **真实 BLOCKED**：无 `ANNOTATION_PACK_SIGNING_KEY` 时 sign CLI exit 2、importer exit 2
- 生产模式不接受 fixture 密钥签名的 manifest
- `development + test_key_flag` 企图启用测试密钥 → 被 mutation m12 检测

## Mutation target 证据

### Pack trust mutation gate：21/21

| # | Mutation | Target Check | Detected |
|---|---------|-------------|----------|
| 1 | task_fixture_recomputed_no_manifest | pack_trust | ✓ |
| 2 | manifest_sha_updated_no_signature | pack_trust | ✓ |
| 3 | manifest_forged_passed_field | pack_trust | ✓ |
| 4 | pack_replaced_with_another | pack_trust | ✓ |
| 5a | extra_pack_added | pack_trust | ✓ |
| 5b | pack_removed | pack_trust | ✓ |
| 6a | path_traversal_manifest | pack_trust | ✓ |
| 6b | absolute_path_manifest | pack_trust | ✓ |
| 7 | bytes_count_mismatch | pack_trust | ✓ |
| 8 | dataset_id_mismatch | pack_trust | ✓ |
| 9 | signer_key_id_mismatch | pack_trust | ✓ |
| 10a | signature_truncated | pack_trust | ✓ |
| 10b | signature_wrong_algorithm | pack_trust | ✓ |
| 10c | signature_wrong_key | pack_trust | ✓ |
| 10d | signature_missing | pack_trust | ✓ |
| 12 | dev_mode_test_key_flag | pack_trust | ✓ |
| 14 | manifest_corrupt_json | pack_trust | ✓ |
| 15 | manifest_not_found | pack_trust | ✓ |
| 16 | schema_version_wrong | pack_trust | ✓ |
| 17 | total_task_count_wrong | pack_trust | ✓ |
| 18 | fixture_false_in_manifest_for_fixture_import | pack_trust | ✓ |

Readiness invariant: production_no_key_blocked_exit2 → exit 2 PASS

### Annotation mutation gate：34/34（无回退）

所有 fix-4 的 mutation 继续通过。

## 密钥泄露扫描

扫描范围：`docs/` 目录下所有 `.md` 和 `.json` 文件。
检查模式：`ANNOTATION_PACK_SIGNING_KEY=<value>` 赋值。
结果：**CLEAN** — 无生产密钥明文。

Fixture 测试密钥 `fixture-test-signing-key-not-for-production-use` 是故意公开的，不构成泄露。

## P13-2-2-1 回归

- 43 项聚焦测试：43/43 PASS
- 34 类 annotation mutation：34/34 PASS
- 5 类 meta-negative：5/5 PASS
- 1 readiness invariant：1/1 PASS
- 全量回归 295 项：295 PASS

## 状态不变量与人工前置动作

| 状态 | 值 | 说明 |
|------|-----|------|
| `human_verified_count` | 0 | 无真实人工标注 |
| `human_labels_complete` | false | 未完成 |
| `calibration_allowed` | false | 校准未开放 |
| `fixture_only` | true | 当前为 fixture 模式 |
| `production_blocked` | true | 生产路径无密钥 → BLOCKED |
| P13-2-2-2 READY | false | 继续冻结 |

## 验收门禁汇总

| 门禁 | 结果 |
|------|------|
| ruff check signal_miner tests scripts | PASS |
| pytest test_p13_2_pack_trust_contract.py | 28/28 PASS |
| pytest test_p13_2_human_annotation_contract.py | 43/43 PASS |
| pytest full suite | 295/295 PASS |
| pack_trust_mutation_gate | 21/21 PASS |
| annotation_mutation_gate | 34/34 PASS |
| p13_1_behavior_probe | PASS |
| p13_2_validate_goldset | READY |
| key leak scan | CLEAN |
