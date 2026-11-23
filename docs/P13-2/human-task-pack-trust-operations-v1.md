# Human Task Pack Trust Operations v1

> **fix-1A (2026-07-13)**：关闭 Commander 四个阻断。test-only 密钥改为四重约束；manifest 强制必需；dataset manifest hash 绑定。Schema 升级到 1.1.0。

## 概述

P13-2-2-1A 为人工任务包建立了独立于 pack 内容的外部信任根。通过 HMAC-SHA256 签名的 manifest 文件，即使改包者同时修改 task 字段并重新计算所有 hash，仍可被检测拒绝。

manifest 还绑定产生这些 task packs 的冻结授权 dataset manifest（SHA-256 + dataset_id），形成 dataset → pack → annotation 完整来源链。

## 组件

### 1. Pack Trust 模块 (`signal_miner/evaluation/pack_trust.py`)

核心 API：
- `generate_pack_manifest(task_dir, dataset_manifest_path, dataset_id, fixture, signer_key_id)` — 从四个 pack 文件 + dataset manifest 生成规范化 manifest
- `canonicalize_manifest(manifest)` — 确定性 JSON 序列化（排序键、分隔符）
- `sign_manifest(manifest, key)` — HMAC-SHA256 签名
- `verify_manifest_file(manifest_path, task_dir, key, expected_key_id, dataset_manifest_path)` — 完整验证（schema + 文件级 + 签名 + dataset manifest hash 重算）
- `resolve_signing_key(fixture, test_key, environment)` → `(key, error_message, error_kind)` — 三元组返回，按 error_kind 区分 FAIL exit 1 vs BLOCKED exit 2

**常量**：
```python
SCHEMA_VERSION = "1.1.0"
PROD_KEY_ID = "production-key"
FIXTURE_KEY_ID = "fixture-test-key-v1"  # key_id label only；实际 key 必须由 env 注入
ENV_VAR_TEST_KEY = "ANNOTATION_PACK_TEST_SIGNING_KEY"
ENV_VAR_PROD_KEY = "ANNOTATION_PACK_SIGNING_KEY"
ENV_VAR_ENVIRONMENT = "APP_ENVIRONMENT"
ALLOWED_TEST_ENVIRONMENTS = ("test",)
```

### 2. 签名 CLI (`scripts/p13_2_sign_human_task_pack.py`)

```bash
# Fixture 模式（仅 test 环境）
APP_ENVIRONMENT=test \
ANNOTATION_PACK_TEST_SIGNING_KEY="test-key-for-ci-pipeline" \
.venv/bin/python scripts/p13_2_sign_human_task_pack.py \
  --tasks sample_data/p13_2/human_tasks \
  --dataset-manifest sample_data/p13_2/manifest.json \
  --fixture \
  --out /tmp/sign_report.json

# 生产模式（需要环境变量密钥）
ANNOTATION_PACK_SIGNING_KEY="your-secret-key" \
.venv/bin/python scripts/p13_2_sign_human_task_pack.py \
  --tasks sample_data/p13_2/human_tasks \
  --dataset-manifest sample_data/p13_2/manifest.json \
  --out /tmp/sign_report.json
```

`--dataset-manifest` 现在是 `required=True`。

### 3. Importer 先验验证

Importer 在处理任何 annotation 之前会：
1. 检查 `manifest_path` 非空（否则 `BLOCKED_MISSING_MANIFEST`，exit 2，store 不创建）
2. 读取签名 manifest，验证 schema 结构（含 `dataset_manifest_path`、`dataset_manifest_sha256` 字段）
3. 逐 pack 验证 SHA-256、bytes、task_count
4. 验证 HMAC-SHA256 签名
5. 独立重读 `dataset_manifest_path`，重算 SHA-256 并与 manifest 内嵌 hash 比较；比较 dataset_id
6. 验证 fixture 标志匹配导入模式

## 密钥管理规则（四重约束）

测试密钥路径必须**同时满足**以下四个条件，缺一即 FAIL 或 BLOCKED：

| 约束 | 来源 | 不满足时的错误 |
|------|------|---------------|
| `APP_ENVIRONMENT=test` | 运行环境变量 | `test_key_environment_boundary`（exit 1） |
| `--fixture` | CLI 参数 | 走 production 路径 |
| `ANNOTATION_PACK_TEST_SIGNING_KEY` 显式注入 | 测试进程环境变量 | `BLOCKED_MISSING_TEST_KEY`（exit 2） |
| manifest `fixture=true` | manifest 字段 | schema 校验失败 |

**关键**：代码中不再有内置默认测试密钥常量。`FIXTURE_KEY_ID = "fixture-test-key-v1"` 只是写入 manifest 的 key_id label，实际签名 key 必须由测试进程通过环境变量注入。

| 模式 | 密钥来源 | key_id | fixture_only | APP_ENVIRONMENT |
|------|---------|--------|-------------|-----------------|
| Fixture/Test | `ANNOTATION_PACK_TEST_SIGNING_KEY`（必须显式注入） | `fixture-test-key-v1` | `true` | `test` |
| Production | `ANNOTATION_PACK_SIGNING_KEY` | `production-key` | `false` | 任意非 test |
| Production 无密钥 | N/A | N/A | N/A | exit 2 `BLOCKED_MISSING_PACK_SIGNING_KEY` |

### 禁止事项（强制）
- 在仓库、报告、日志中写入真实签名密钥
- 在 runtime 模块（`pack_trust.py`、`signer`、`importer`）中硬编码任何测试或生产密钥常量
- 生产模式或 development 模式使用 `--fixture`
- 无 manifest 时降级为普通 SHA 仍标 PASS
- 修改 manifest 任何字段后不重新签名
- 篡改 dataset manifest 内容后不更新 pack manifest 中的 `dataset_manifest_sha256`

## Manifest Schema (v1.1.0)

```json
{
  "schema_version": "1.1.0",
  "dataset_id": "ddcfad9b574bb579",
  "dataset_manifest_path": "sample_data/p13_2/manifest.json",
  "dataset_manifest_sha256": "f3a2e1b4c5d6...e91c",
  "fixture": true,
  "fixture_only": true,
  "signer_key_id": "fixture-test-key-v1",
  "generated_at": "2026-07-13T14:30:00+00:00",
  "canonicalization_version": "1",
  "total_task_count": 120,
  "packs": [
    {
      "path": "human_tasks_development.json",
      "sha256": "b17da9ba54952e49...",
      "bytes": 55076,
      "task_count": 50,
      "annotation_mode": "assisted_review",
      "annotator_slot": "assisted",
      "split": "development",
      "fixture": true
    }
  ],
  "signature": "a3f2e1b4c5d6..."
}
```

### v1.1.0 vs v1.0.0 变更
- 新增 `dataset_manifest_path`：必填
- 新增 `dataset_manifest_sha256`：必填，由 `generate_pack_manifest` 自动计算嵌入
- 验证流程新增第 5 步：独立重读 dataset manifest 重算 SHA-256 比较

## 操作流程

### Fixture 标注测试流程

```bash
# 1. 准备 fixture task packs
.venv/bin/python scripts/p13_2_prepare_human_tasks.py --fixture --out-dir sample_data/p13_2/human_tasks

# 2. 签名 manifest（必须在 test 环境，必须注入测试 key）
APP_ENVIRONMENT=test \
ANNOTATION_PACK_TEST_SIGNING_KEY="test-key-for-ci-pipeline" \
.venv/bin/python scripts/p13_2_sign_human_task_pack.py \
  --tasks sample_data/p13_2/human_tasks \
  --dataset-manifest sample_data/p13_2/manifest.json \
  --fixture

# 3. 导入 annotations（manifest 强制必需）
APP_ENVIRONMENT=test \
ANNOTATION_PACK_TEST_SIGNING_KEY="test-key-for-ci-pipeline" \
.venv/bin/python scripts/p13_2_import_human_annotations.py \
  --input annotations.json \
  --tasks sample_data/p13_2/human_tasks \
  --manifest sample_data/p13_2/human_tasks/human-task-pack-manifest.json \
  --dataset-manifest sample_data/p13_2/manifest.json \
  --fixture
```

### 生产标注流程（BLOCKED — 无授权数据）

```bash
# 无 ANNOTATION_PACK_SIGNING_KEY → exit 2 BLOCKED_MISSING_PACK_SIGNING_KEY
.venv/bin/python scripts/p13_2_sign_human_task_pack.py --tasks ... --dataset-manifest ...  # BLOCKED
```

## 安全边界

- `pack_trust` 是 importer 的第 0 个结构化 check，在任何 annotation 处理之前执行
- **manifest 强制必需**：fixture 和 production 路径都必须提供签名 manifest，不存在 optional 分支
- **环境边界真实生效**：mutation gate 4 类环境边界 mutation（production / development / empty / unknown）通过 `subprocess.run(env=...)` 真实注入 APP_ENVIRONMENT，manifest 保持有效签名，失败仅由环境触发
- **dataset manifest hash 绑定**：篡改 dataset manifest 内容 / SHA / 路径 / dataset_id 4 类 mutation 全部被 detected=true
- 20 类 pack trust mutation + 2 类 readiness invariant 全部通过
- 生产模式无密钥 = exit 2 BLOCKED（正确安全行为）
- Fixture 签名不会计入 `human_verified_count`
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`、`production_blocked=true` 保持不变
