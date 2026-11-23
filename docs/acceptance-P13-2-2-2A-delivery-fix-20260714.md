# P13-2-2-2A fix 交付报告：readiness 真实门禁闭环

交付日期：2026-07-14
执行方：DeepSeek（Senior Developer 模式）
依据：`docs/deepseek-instruction-P13-2-2-2A-fix.md`
前置验收：`docs/acceptance-P13-2-2-2A-commander-20260714.md`（不通过，4 P0 + 2 P1）

## 结论：fix 完成，正式运行仍为 `BLOCKED_INPUT_REQUIRED / exit 2`

修复了 Commander 拒绝的 4 个 P0 + 2 个 P1 阻断点。当前用户仍未提供真实输入，所以正式 readiness 仍诚实退出 2，符合"不制造 READY"的设计约束。

## Commander 阻断点关闭情况

### P0-1：候选计数可伪报（已关闭）

**根因**：原实现直接信任 `eligible_count`，未与候选数组长度和逐行授权完整行数对账。

**修复**：
- 重算 `row_count`、`authorized_count`、`incomplete_count` 从候选数组真实行
- `declared_eligible_count` 只作为声明值；不等于 `authorized_count` → `COUNT_RECOMPUTE_MISMATCH / exit 1`
- 任何 incomplete row（缺字段或类型错误）都阻断 READY
- 16 个 `AUTHORIZATION_FIELD_SPECS` 严格类型校验（str/bool_true/str_list/sha256/url）
- 重复 sample_id / content_sha256 检测
- `real_rejections` 必须存在并参与计数守恒

**Commander 反例复跑结果**（声明 100、实际 99、授权完整 0、无执行窗口）：

```text
exit_code: 1
status: FAILED_INVALID_INPUT
passed: False
authorized_count: 0
declared: 100
count_recompute_match: False
blockers: ['real_candidates']
errors:
  [invalid] real_candidates: COUNT_RECOMPUTE_MISMATCH: declared eligible_count=100 != recomputed authorized_count=0
  [invalid] real_candidates: authorization_incomplete_rows=99 > 0
  [invalid] real_candidates: insufficient real authorized candidates: authorized_count=0 < 100
```

### P0-2：READY 路径不消费真实治理配置（已关闭）

**根因**：roles/splits/test packs/governance 仅能通过 test override 注入；正式 CLI 没有真实路径。

**修复**：
- 新增 `--launch-config` CLI 参数，支持引用 launch config JSON 文件
- launch config schema：`real_candidate_path`、`real_rejections_path`、`roles_config_path`、`splits_config_path`、`governance_config_path`、`test_packs_dir`
- 测试 override 必须有 `APP_ENVIRONMENT=test` 或 `_test_mode=True` 边界
- 生产环境（非 test env）传入 override 参数 → `FAILED_INVALID_INPUT / exit 1`
- 新增 `annotation_governance` 检查（窗口、retention、access list）

### P0-3：安全失败被降级为缺输入（已关闭）

**根因**：所有 errors 统一映射为 exit 2，盲标泄漏、签名或数据契约违规被误报为"等待输入"。

**修复**：
- 引入 `InputError(kind, check, message)` 三元组分类
- `kind="missing"` → 关键外部输入缺失 → `BLOCKED_INPUT_REQUIRED / exit 2`
- `kind="invalid"` → 输入已提供但无效 → `FAILED_INVALID_INPUT / exit 1`
- 任一 invalid 错误优先 → 整体走 FAILED 路径

**Commander 反例复跑结果**（test blind prediction 泄漏）：

```text
exit_code: 1 (was 2 before fix)
status: FAILED_INVALID_INPUT
leakage_count: 25
leaked_fields: ['prediction']
```

### P0-4：14 类负例错测/漏测/弱断言（已关闭）

**根因**：N1 把 `eligible_count` 也设为 99，未攻击伪报；N3 只断言记录未断言 exit；N9 用角色碰撞替代访问边界；N11 用"缺密钥"替代 hash 篡改。

**修复**：重写为 16 类负例（按 fix 指令要求新增 N15、N16）+ 61 项测试：

| 编号 | 场景 | exit | 结构化 target |
| --- | --- | --- | --- |
| N1 | 声明100实际99（COUNT_RECOMPUTE_MISMATCH） | 1 | real_candidates=false |
| N1b | 99 valid candidates, eligible_count=99 (< 100) | 1 | real_candidates=false |
| N1c | 零候选 → missing（exit 2，不是 invalid） | 2 | real_candidates=false |
| N2 | 100行+1 fixture 污染 | 1 | real_candidates=false |
| N3 | 16 个 AUTHORIZATION_REQUIRED_FIELDS 参数化 | 1 | real_candidates=false |
| N3b | 类型错误：bool/str、list/str、sha 短 | 1 | real_candidates=false |
| N4 | 未脱敏 PII（email/手机号） | 1 | pii_scan=false |
| N5 | 同 sample_id 跨 dev/test | 1 | split_isolation=false |
| N6 | 11 个 TEST_BLIND_FORBIDDEN_FIELDS 参数化 | 1 | test_blind_leakage=false |
| N7 | 双标 15 < 20 | 1 | human_roles=false |
| N7b | 双标 30 < 40 (200×20%) | 1 | human_roles=false |
| N8 | A/B pseudonym 相同 | 1 | human_roles=false |
| N9 | a_b_access_isolation=false（A 可读 B 标签） | 1 | human_roles=false |
| N9b | a_b_access_isolation 完全缺失 | 1 | human_roles=false |
| N10 | production key 匹配 fixture 模式 | 1 | production_signing_key=false |
| N10b | test env 下出现 production key | 1 | production_signing_key=false |
| N10c | production key 等于 test key | 1 | production_signing_key=false |
| N11 | production key 缺失（missing，不是 invalid） | 2 | production_signing_key=false |
| N12 | annotator B pseudonym 缺失 | 1 | human_roles=false |
| N13 | 不变量：READY 时 human_verified_count 仍 0 | n/a | hard invariant |
| N14 | 不变量：READY 时 calibration_allowed 仍 False | n/a | hard invariant |
| N15 | governance 完全缺失（missing） | 2 | annotation_governance=false |
| N15b | window_start >= window_end | 1 | annotation_governance=false |
| N15c | retention_until <= window_end | 1 | annotation_governance=false |
| N15d | 空 allowed_access_role_ids | 1 | annotation_governance=false |
| N16 | 发布后 artifact SHA 被篡改 → sidecar 不匹配 | n/a | sidecar mismatch |

### P1-1：SHA 三方不一致（已关闭）

**根因**：先发布、把第一次 SHA 填回 payload、再发布一次，嵌入值天然不是最终文件字节 SHA。

**修复**：
- 引入 `_publish_with_sidecar` 函数
- 发布 JSON 后计算最终字节 SHA → 写独立 `.sha256` sidecar 文件 → readback 校验
- JSON 内**不**嵌入 artifact_sha（避免自引用）
- 交付报告、sidecar、`shasum -a 256` 三方必须一致

**实际三方对账**（交付时最近一次正式运行）：

```text
sidecar:        eb9d013706eb97c097940c5c53b72a38237e185eba67c607d72e8680a7b240e5
shasum -a 256:  eb9d013706eb97c097940c5c53b72a38237e185eba67c607d72e8680a7b240e5
本报告记录:     eb9d013706eb97c097940c5c53b72a38237e185eba67c607d72e8680a7b240e5
```

注：每次正式运行因 `generated_at` 时间戳不同会产生新 SHA。三方对账在**同一份 artifact** 上必须一致——交付报告记录的 SHA 必须是最后一次正式运行的 sidecar SHA。

### P1-2：顶层状态不稳定（已关闭）

**根因**：无输入时顶层为 `BLOCKED_INSUFFICIENT_REAL_CANDIDATES`，与任务书规约不符。

**修复**：
- 顶层状态稳定为三种：`BLOCKED_INPUT_REQUIRED`（exit 2）、`FAILED_INVALID_INPUT`（exit 1）、`READY_FOR_HUMAN_ANNOTATION`（exit 0）
- 细分原因放在 `blockers[]` 数组（如 `["real_candidates", "human_roles"]`）
- 上层编排无需枚举不断扩张的 BLOCKED_* 状态

### 附加：JSON 必填字段补齐（P1-1 一部分）

新增必填字段（无输入时为 null）：
- `dataset_id`
- `batch_id`
- `dataset_manifest_sha256`
- `pack_manifest_sha256`

## 机器证据

### 正式 readiness artifact

`docs/P13-2-evidence/real-annotation-launch-readiness.json`：

```json
{
  "status": "BLOCKED_INPUT_REQUIRED",
  "passed": false,
  "exit_code": 2,
  "schema_version": "readiness-2.0.0",
  "blockers": [
    "annotation_governance",
    "human_roles",
    "production_signing_key",
    "real_candidates",
    "split_isolation",
    "test_blind_leakage"
  ],
  "errors": [
    "[missing] real_candidates: no real authorized candidates provided: authorized_count=0 < 100",
    "[missing] production_signing_key: ANNOTATION_PACK_SIGNING_KEY not set in environment",
    "[missing] human_roles: human roles config not provided",
    "[missing] split_isolation: splits not provided",
    "[missing] test_blind_leakage: test packs not provided",
    "[missing] annotation_governance: annotation governance config not provided"
  ],
  "human_verified_count": 0,
  "human_labels_complete": false,
  "calibration_allowed": false,
  "kappa": 0.0,
  "dataset_id": null,
  "batch_id": null,
  "dataset_manifest_sha256": null,
  "pack_manifest_sha256": null
}
```

### Sidecar

`docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`：

```text
eb9d013706eb97c097940c5c53b72a38237e185eba67c607d72e8680a7b240e5  real-annotation-launch-readiness.json
```

### 测试隔离

模块级 `real_evidence_sha_guard` fixture 在 61 项测试前后断言：
- `docs/P13-2-evidence/real-annotation-launch-readiness.json` SHA 不变
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256` SHA 不变

所有测试通过 `evidence_dir=tmp_path` + `_test_mode=True` 注入，**未触碰正式 evidence**。

## 静态、测试与正式运行

| 检查 | 结果 |
| --- | --- |
| Ruff（signal_miner + tests + scripts） | PASS |
| readiness 聚焦测试 | **61 passed** |
| 全量回归 | **389 passed, 3 warnings**（前次 376 + 13 新增 = 389） |
| 正式 readiness | `BLOCKED_INPUT_REQUIRED / exit 2`（设计正确） |
| 正式 orchestrator | `PASS / exit 0`，run_id=`191eb9e3-9ec3-43b6-b8a6-df2bcc14dfff` |
| Pack mutation | 23/23 |
| Annotation mutation | 34/34 |
| committed-evidence verifier | PASS / exit 0 |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | READY / passed=true |
| `git diff --check` | PASS |

### P13-2-2-1A 工具链未受影响

- 正式 orchestrator：exit 0
- committed-evidence verifier：exit 0
- behavior probe：PASS
- goldset validator：READY

按 fix 指令边界，**未修改**已验收的 P13-2-2-1A 业务信任链、orchestrator、committed verifier。

## 关键 Commander 反例独立复跑结果

### 反例 1：声明 100 实际 99 授权完整 0

```text
exit_code: 1
status: FAILED_INVALID_INPUT
authorized_count: 0
declared: 100
count_recompute_match: False
```

### 反例 2：test blind prediction 泄漏

```text
exit_code: 1 (was 2 before fix)
status: FAILED_INVALID_INPUT
leakage_count: 25
leaked_fields: ['prediction']
```

## 解锁 P13-2-2-2B 所需用户输入

1. **真实授权候选 ≥100 条**（含完整 16 字段 AUTHORIZATION_FIELD_SPECS，类型严格）
2. **生产 pack 签名密钥**（`ANNOTATION_PACK_SIGNING_KEY`，生产环境，非 test env，非 fixture/test/example/dummy 模式）
3. **独立人工标注角色 A/B/裁决员** pseudonym + `a_b_access_isolation=true`
4. **标注执行窗口、retention、allowed_access_role_ids**
5. **launch config JSON** 引用上述所有文件

工具链已就绪，用户输入到位后通过 `--launch-config path.json` 即可运行真实判定。

## 完成边界

本次只返修 readiness。通过后也只是证明"门禁能诚实判定 READY 或 BLOCKED"。当前没有真实输入时仍停在 P13-2-2-2A。不得开始真实人工标签计数，不得进入 P13-2-2-2B 或任何下游调优/校准/聚类/前端发布。
