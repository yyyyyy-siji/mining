# P13-2-2-2A fix-2 交付报告：readiness 信任链闭环

交付日期：2026-07-14
执行方：DeepSeek（Senior Developer 模式）
依据：`docs/deepseek-instruction-P13-2-2-2A-fix-2.md`
前置验收：`docs/acceptance-P13-2-2-2A-fix-commander-20260714.md`（不通过）

## 结论：fix-2 完成，正式运行仍为 `BLOCKED_INPUT_REQUIRED / exit 2`

实现了 P13-2-2-1A 信任链接入、签名 packs 消费、任务重算和独立 evidence 验证器。当前无用户真实输入，正式 readiness 诚实退出 2。

## 新文件 SHA

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `9d38e828bfda1806bfc4e2f89d20c7185576bb2a2b3cea697820c5365069bbdc` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `c12fe343280e2de02a4644f2978fe785fb8f7c62fcb88a6e2084a2db93fd9e97` |

旧 SHA（均不再等于）：
- Script: `57ca10c8588dbfb3af9adb832b1fc7330aeb56af5ea5077344cad4f68e979b59`
- Tests: `21f7685c21b627fa2352de5fafbf21e6d6219e7313582d198633f44a5592e16b`

## Preflight 结果

| 检查 | 结果 |
| --- | --- |
| `test -f docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md` | EXISTS |
| `grep verify_manifest_file` | 2 hits (line 801, 826) |
| `grep compute_task_hash` | 5 hits (lines 847, 912, 946, 955, 1071) |
| `grep dataset_manifest_path` | 15 hits |
| `grep pack_manifest_path` | 9 hits |
| `grep task_dir` | 27 hits |
| `grep verify-evidence` | 7 hits |
| Script SHA ≠ `57ca10c8...` | YES |
| Test SHA ≠ `21f7685c...` | YES |
| `--verify-evidence` | exit 0 PASS（不是 unrecognized arguments） |

## 实现要点

### 1. 复用 P13-2-2-1A 生产验证器

- `_check_pack_trust()` 调用 `signal_miner.evaluation.pack_trust.verify_manifest_file()`，参数包括 `manifest_path`、`task_dir`、`key`、`expected_key_id`、`dataset_manifest_path`
- `_check_task_identity()` 调用 `signal_miner.evaluation.human_annotation.compute_task_hash()` 逐任务重算 hash
- 未复制弱化版验证器；使用 1A 单一真源

### 2. Launch config 引用完整信任链

`--launch-config` JSON 消费：`real_candidate_path`、`real_rejections_path`、`dataset_manifest_path`、`pack_manifest_path`、`task_dir`、`roles_config_path`、`splits_config_path`、`governance_config_path`

所有相对路径相对 launch config 所在目录解析。

### 3. 从签名 packs 重算任务、盲标、双标

- `_recompute_double_label_from_packs()`：读取 test_A 和 test_B pack 文件，找到共享 sample_id（实际双标），验证 A/B slot 隔离
- 双标数量从实际 pack 重算，不信任 roles 配置的自报值
- A/B slot 隔离：A pack 只能有 slot="A"，B pack 只能有 slot="B"；禁止跨 pack 读取对方标签

### 4. Split 与候选及任务精确绑定

- `_check_split_isolation()` 接受 `all_candidate_ids` 参数：split ID 并集必须等于授权候选集，无缺失无多余
- 额外 content-hash 级跨 split 重复检测
- `candidate_coverage_match` 结构化 flag

### 5. 严格候选/rejections/governance 校验

- 新增 `source_adapter`、`source_version` 字段
- `captured_at` 使用 `_is_iso8601()` 严格解析（datetime.fromisoformat）
- `rejected_count` 从 `real_rejections` 文件实际行数重算，与声明值对账
- Governance 使用 `datetime.fromisoformat()` 解析时间，不再使用字符串字典序
- Access list 必须覆盖 A/B/裁决三个 role id

### 6. 独立 evidence SHA 验证器

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

- JSON 与 sidecar 匹配时 exit 0
- 任一篡改/缺失/格式错误时 exit 1
- **只读**：不覆盖/重新生成 artifact

### 7. 删除 production override 旁路

生产 `main()` 只接受 `--launch-config` 文件或独立 CLI flags。`_test_mode` 参数不再作为 production 旁路。

## 14 个生产主路径负例（35 项测试）

| 编号 | 场景 | exit | 结构化 target |
| --- | --- | --- | --- |
| N1 | 无 dataset manifest | 2 | pack_trust=false |
| N1b | Dataset manifest 内容篡改 | 1 | pack_trust=false |
| N2 | 无 pack manifest | 2 | pack_trust=false |
| N2b | Manifest 签名篡改 | 1 | pack_trust=false |
| N3 | Manifest SHA 篡改 | 1 | pack_trust=false |
| N3b | Manifest bytes 篡改 | 1 | pack_trust=false |
| N3c | Manifest task_count 篡改 | 1 | pack_trust=false |
| N4 | Task hash 篡改 | 1 | task_identity=false |
| N5 | 空 test packs（0 tasks） | 1 | task_identity=false |
| N6 | Split ID 与候选零交集 | 1 | split_isolation=false |
| N7 | 同 sample_id 跨 dev/test | 1 | split_isolation=false |
| N8 | 双标声明20但实际0（A/B无共享） | 1 | task_identity=false |
| N9 | A pack 含 B slot | 1 | task_identity=false |
| N10 | Rejection 声明999实际0 | 1 | real_candidates=false |
| N11 | captured_at 无效 | 1 | real_candidates=false |
| N12 | Access list 不含 A/B/adj | 1 | annotation_governance=false |
| N13 | Production key 匹配 fixture 模式 | 1 | production_signing_key=false |
| N14 | 发布后篡改 sidecar → verify exit 1 | 1 | verify-evidence |
| N14b | 发布后篡改 JSON → verify exit 1 | 1 | verify-evidence |
| — | 无 task_dir → exit 2 BLOCKED | 2 | task_identity=false |
| — | 计数伪报（回归） | 1 | real_candidates=false |
| — | 零输入 exit 2（回归） | 2 | BLOCKED_INPUT_REQUIRED |
| — | 11 个 TEST_BLIND_FORBIDDEN_FIELDS 参数化（回归） | 1 | test_blind_leakage=false |

### 正向测试

`test_full_signed_packs_ready` — 临时 tmp_path 生成 50+25+30 候选、4 个签名 task pack、dataset manifest 和生产模式签名 pack manifest → `READY_FOR_HUMAN_ANNOTATION / exit 0`：
- `pack_trust=true`、`task_identity=true`
- `test_unique_task_count >= 25`
- `double_label_actual_count >= 1`（A/B 共享 30 个样本）
- `slot_isolation_ok=true`
- `dataset_id != null`、`dataset_manifest_sha256 != null`、`pack_manifest_sha256 != null`
- `human_verified_count=0`、`calibration_allowed=false`

## 机器证据

### 正式 readiness artifact

`docs/P13-2-evidence/real-annotation-launch-readiness.json`：

```json
{
  "status": "BLOCKED_INPUT_REQUIRED",
  "passed": false,
  "exit_code": 2,
  "schema_version": "readiness-2.1.0",
  "blockers": [
    "annotation_governance", "human_roles", "pack_trust",
    "production_signing_key", "real_candidates",
    "split_isolation", "task_identity", "test_blind_leakage"
  ]
}
```

### Sidecar 对账（交付时最后一次正式运行）

```text
sidecar:  d2f4347f6b61831c08559ddd9e5901ea54de12c62668ae3baf84b1af74ea5053
shasum:   d2f4347f6b61831c08559ddd9e5901ea54de12c62668ae3baf84b1af74ea5053
报告:     d2f4347f6b61831c08559ddd9e5901ea54de12c62668ae3baf84b1af74ea5053
MATCH:    YES
```

### 测试隔离

模块级 fixture 在 35 项测试前后断言真实 `real-annotation-launch-readiness.json` 及 `.sha256` sidecar SHA 不变。

## 静态、测试与正式运行

| 检查 | 结果 |
| --- | --- |
| Ruff（signal_miner + tests + scripts） | PASS |
| fix-2 聚焦测试 | **35 passed** |
| 全量回归 | **363 passed, 3 warnings** |
| 正式 readiness | `BLOCKED_INPUT_REQUIRED / exit 2` |
| `--verify-evidence` | PASS / exit 0 |
| 正式 orchestrator | PASS / exit 0，run_id=`c3ebe231-...` |
| committed-evidence verifier | PASS / exit 0 |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | READY / passed=true |
| `git diff --check` | PASS |
| Sidecar 三方对账 | MATCH |

### P13-2-2-1A 工具链未受影响

按 fix 指令边界，**未修改**已验收的 P13-2-2-1A 业务信任链、orchestrator、committed verifier。

## 新增/修改文件

- `scripts/p13_2_real_annotation_launch_readiness.py`（完全重写，~1420 行）
- `tests/test_p13_2_real_annotation_launch_readiness.py`（完全重写，~420 行，35 项）
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`（schema_version: readiness-2.1.0）
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
- `docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md`（本报告）

## 完成边界

本次只返修 readiness。通过后也只是证明"门禁能诚实判定 READY 或 BLOCKED"。当前没有真实输入时仍停在 P13-2-2-2A。不得开始真实人工标签计数，不得进入 P13-2-2-2B 或任何下游调优/校准/聚类/前端发布。
