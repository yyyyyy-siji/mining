# P13-2-2-1A 交付报告：外部 Pack 信任根返修（fix-1A）

交付日期：2026-07-13
返修依据：`docs/acceptance-P13-2-2-1A-commander-20260713.md`、`docs/deepseek-instruction-P13-2-2-1A-fix.md`
质量指标基线：`docs/commander-executor-quality-metrics-20260710.md`

## 结论

**四个 Commander 阻断（P0-1 / P0-2 / P0-3 / P1-1）全部关闭。全量质量门禁通过。**

返修只改动与外部信任根强相关的文件，未引入新功能、未扩张任务书范围。所有"扩大文档说明保留可选绕过"路径均被拒绝——manifest 对所有导入强制必需。

## 阻断关闭映射

### P0-1 关闭：test-only 密钥双重约束

**Commander 反例**：`APP_ENVIRONMENT=production` 下 `--fixture` + 公开测试密钥得到 `exit 0 / SIGNED / signer_key_id=fixture-test-key-v1`。

**根因**：`resolve_signing_key(fixture, test_key)` 只看 `fixture` 参数，不检查运行环境。代码中还存在硬编码默认测试密钥常量 `FIXTURE_TEST_KEY`。

**修复**（四重约束，缺一即 BLOCKED 或 FAIL）：
1. `APP_ENVIRONMENT` 必须为 `test`（`ALLOWED_TEST_ENVIRONMENTS = ("test",)`）
2. CLI 必须传 `--fixture`
3. `ANNOTATION_PACK_TEST_SIGNING_KEY` 必须由测试进程显式注入（不再有内置默认值）
4. manifest 的 `fixture` 字段必须为 `true`

**改造点**：
- `signal_miner/evaluation/pack_trust.py::resolve_signing_key()` 完全重写，返回三元组 `(key, error_message, error_kind)`。`error_kind` 区分：
  - `test_key_environment_boundary`（exit 1，环境不在 test 白名单）
  - `BLOCKED_MISSING_TEST_KEY`（exit 2，test 环境但未注入 key）
  - `BLOCKED_MISSING_PACK_SIGNING_KEY`（exit 2，production 无 key）
- `scripts/p13_2_sign_human_task_pack.py` 删除 `FIXTURE_TEST_KEY = "fixture-test-signing-key-not-for-production-use"` 常量。按 `error_kind` 分流 exit code。
- `scripts/p13_2_import_human_annotations.py` 同步删除硬编码 `_FIXTURE_TEST_KEY`，按 trust_error_kind 分流。

**验证**：契约测试 `TestSignatureAndEnvBoundary` 覆盖 production / development / empty / unknown / staging 全部环境被拒绝；mutation gate 环境边界 mutation 1-4 用真实子进程 env（`subprocess.run(env=...)`）证明失败仅由环境触发，manifest 仍保持有效签名。

---

### P0-2 关闭：manifest 强制必需

**Commander 反例**：`APP_ENVIRONMENT=production` + `--fixture` + 无 `--manifest` → `exit 0 / IMPORTED / pack_trust.passed=true / added=120 / store_created=true`。

**根因**：`_verify_pack_trust(is_fixture=True, manifest_path=None)` 直接返回空错误列表，把"未验证"写成"通过"。

**修复**：`_verify_pack_trust()` 第一行即 `if manifest_path is None: return ([], "BLOCKED_MISSING_MANIFEST")`。store 不创建、pack_trust 不 passed、exit 2。删除 fixture 路径的 manifest optional 分支。

**验证**：
- 契约测试 `TestManifestMandatory::test_fixture_import_without_manifest_blocked`
- Mutation gate mutation 6（`test_env_fixture_no_manifest_rejected`）：test 环境 + fixture + 无 manifest → `child_exit=2 / store_created=false / detected=true`
- 全量 annotation 测试和 mutation gate 均改为强制走签名 manifest 路径

---

### P0-3 关闭：真实子进程环境边界 mutation

**Commander 反例**：`dev_mode_test_key_flag` mutation 只往 manifest 追加 `environment=development / allow_test_key=true` 字段制造陈旧签名，并未真正测试环境边界——任何字段改动都会因签名失效而 exit 1。

**根因**：mutation 没有改变子进程运行环境，而是篡改了签名载荷。

**修复**：mutation gate 环境边界 mutation（1-4）改为：
- mutation 函数体 `lambda _d, _mp, _dm: None`（不篡改任何文件，保持签名有效）
- `run_mutation(env_override={...}, replace_env=True)` 通过 `subprocess.run(env=...)` 真实注入 `APP_ENVIRONMENT`
- 失败信号是 signer/importer 报 `test_key_environment_boundary` 命中，exit 1

**新增 readiness invariant**：`_run_test_no_invariant()` 验证 test 环境未注入 `ANNOTATION_PACK_TEST_SIGNING_KEY` 时正确 BLOCKED exit 2，而非降级使用内置 key（因为已经没有内置 key 了）。

---

### P1-1 关闭：dataset manifest hash 绑定

**Commander 要求**：pack manifest 必须绑定产生这些任务的冻结授权 dataset manifest。

**修复**：
- `SCHEMA_VERSION` 从 `1.0.0` 升级到 `1.1.0`
- `generate_pack_manifest(task_dir, dataset_manifest_path, ...)` 新增必需参数。计算 `dataset_manifest_sha256` 并嵌入 manifest
- `validate_manifest_structure()` 校验 `dataset_manifest_path` 和 `dataset_manifest_sha256` 字段
- `verify_manifest_file()` 第 4 步独立重读 dataset manifest 重算 SHA-256，比较 manifest 内嵌 hash 和 dataset_id

**manifest schema 字段**：
```json
{
  "schema_version": "1.1.0",
  "dataset_id": "ddcfad9b574bb579",
  "dataset_manifest_path": "sample_data/p13_2/manifest.json",
  "dataset_manifest_sha256": "f3a2...e91c",
  ...
}
```

**验证**：契约测试 `TestManifestGeneration::test_dataset_manifest_hash_embedded`；mutation gate 4 类 dataset 篡改 mutation（content / sha_mismatch / path_traversal / dataset_id_mismatch）全部 detected=true。

---

## 质量门禁全量执行结果

| 门禁 | 命令 | 结果 |
|------|------|------|
| Ruff（全范围） | `.venv/bin/ruff check signal_miner tests scripts` | **All checks passed!** |
| Pack trust 契约测试 | `pytest tests/test_p13_2_pack_trust_contract.py` | **22/22 PASS** |
| Annotation 契约测试 | `pytest tests/test_p13_2_human_annotation_contract.py` | **43/43 PASS** |
| 全量回归 | `pytest -q` | **289 passed, 3 warnings** |
| Pack trust mutation gate | `python scripts/p13_2_pack_trust_mutation_gate.py` | **PASS (20/20 mutations, 2/2 invariants)** |
| Annotation mutation gate | `python scripts/p13_2_annotation_mutation_gate.py` | **PASS (34/34 mutations, 1/1 invariants, 5/5 meta-negatives)** |
| 行为探针 | `python scripts/p13_1_behavior_probe.py` | **PASS** |
| Goldset 验证 | `python scripts/p13_2_validate_goldset.py` | **READY / passed=true** |
| Evidence JSON | `python3 -m json.tool docs/P13-2-evidence/*.json` | **VALID** |
| 密钥泄露扫描 | grep `FIXTURE_TEST_KEY / fixture-test-signing-key` 在 runtime 文件 | **未命中**（仅存在于测试/mutation gate 脚本作为 CI 测试常量） |
| Git diff --check | `git diff --check` | **PASS**（无 whitespace error） |

注：测试常量 `TEST_KEY = "test-key-for-ci-pipeline"` 仅出现在 `tests/*` 和 `scripts/p13_2_*_mutation_gate.py` 中，由测试进程通过 env 注入到子进程；runtime 模块（`pack_trust.py`、`signer`、`importer`）零硬编码密钥。`TestKeySafety` 契约测试（3 项）专门验证这一点。

---

## 文件变更清单

| 文件 | 类型 | 变更摘要 |
|------|------|----------|
| `signal_miner/evaluation/pack_trust.py` | 核心重写 | `SCHEMA_VERSION=1.1.0`；`resolve_signing_key` 四重约束 + 三元组返回；`generate_pack_manifest` 新增 `dataset_manifest_path`；`verify_manifest_file` 独立重算 dataset manifest SHA |
| `scripts/p13_2_sign_human_task_pack.py` | 重写 | 删除硬编码 test key；`--dataset-manifest` 必需；按 error_kind 分流 exit 1/2 |
| `scripts/p13_2_import_human_annotations.py` | 关键改造 | `_verify_pack_trust` manifest 强制必需，返回 `(errors, error_kind)`；删除硬编码 key；按 trust_error_kind 分流 |
| `scripts/p13_2_pack_trust_mutation_gate.py` | 完全重写 | 20 mutation + 2 invariants；环境边界 mutation 用真实子进程 env；replace_env 机制 |
| `scripts/p13_2_annotation_mutation_gate.py` | 关键改造 | _setup 加签名步骤；_run_import 传 manifest + dataset_manifest + test env |
| `tests/test_p13_2_pack_trust_contract.py` | 完全重写 | 22 项，新增 dataset hash、环境边界、manifest mandatory、tamper detection |
| `tests/test_p13_2_human_annotation_contract.py` | 关键改造 | 新增 `_sign`、`_prepare_genfix_sign` helper；`_import` 强制走签名 manifest |
| `sample_data/p13_2/manifest.json` | 只读引用 | 冻结 dataset manifest（`dataset_id=ddcfad9b574bb579`） |

---

## 待 Commander 复验项

1. **P0-1 复验**：在 `APP_ENVIRONMENT=production` 下运行 `--fixture` → 预期 `exit 1 / FAIL_TEST_KEY_ENVIRONMENT_BOUNDARY`（无论是否注入 test key）
2. **P0-2 复验**：在 `APP_ENVIRONMENT=test` 下 `--fixture` 不传 `--manifest` → 预期 `exit 2 / BLOCKED_MISSING_MANIFEST / store 未创建`
3. **P0-3 复验**：mutation gate 4 类环境边界 mutation 全部 detected=true，child_exit=1；readiness invariant `_run_test_no_invariant()` 验证 test 环境缺注入 key 时 exit 2
4. **P1-1 复验**：篡改 dataset manifest 内容 / SHA / 路径穿越 / dataset_id 全部 detected=true，exit 1

## 安全状态保持

- `human_verified_count=0`
- `human_labels_complete=false`
- `calibration_allowed=false`
- `production_blocked=true`

返修未改变任何信任状态字段。P13-2-2-2 仍保持冻结，等待本次 fix 通过 Commander 独立复验后解冻。
