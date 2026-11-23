# P13-2-2-2A 交付报告：真实人工标注启动准备

交付日期：2026-07-14
执行方：DeepSeek（Senior Developer 模式）
依据：`docs/deepseek-instruction-P13-2-2-2A-real-annotation-launch-readiness.md`

## 结论：BLOCKED_INPUT_REQUIRED

readiness 门禁诚实退出 `exit 2`，未生成任何伪真实任务包或人工标签。所有硬不变量保持：
- `human_verified_count = 0`
- `human_labels_complete = false`
- `calibration_allowed = false`
- `kappa = 0.0`

## 用户提供的输入清单（不含秘密）

**当前用户未提供任何真实输入**。具体缺失：

| 输入类别 | 状态 | 说明 |
| --- | --- | --- |
| 真实授权候选数据 | 缺失 | `real-candidate-export.json` 显示 `eligible_count = 0`，`rejected_count = 1257`，全部因 `missing_or_invalid_authorization` 与 `missing_source_platform` 被拒 |
| 生产 pack 签名密钥 | 缺失 | 环境变量 `ANNOTATION_PACK_SIGNING_KEY` 未设置 |
| 独立人工标注角色 | 缺失 | 标注员 A / B / 裁决员 pseudonym 全部未提供 |
| 标注执行窗口 | 缺失 | 未提供保留期限与允许访问人员范围 |

## 授权与来源准入统计

机器读取 `docs/P13-2-evidence/real-candidate-export.json`（真实导出，非合成）：

- 合格真实候选：**0**
- 被拒候选：**1257**
- 拒绝原因分布：
  - `missing_or_invalid_authorization`：1257
  - `missing_source_platform`：1257
- profile 分布：空
- source 分布：空
- capture method 分布：空

**结论**：1257 条历史采集样本在 P13-2-2-1A 的严格授权门禁下**全部被诚实拒绝**，没有任何一条通过授权校验。这是 P13-2-2-1A 工具链的正确行为——不放宽门禁、不伪造授权。

## 冻结 split 与去重隔离

**未冻结**。当前无合格候选，无法执行 50/25/25 分割。

readiness 报告中 `split_isolation` 状态为 `NOT_PROVIDED`，等待真实候选到位后才会运行。

## Test 盲标泄漏扫描

**未生成 test 任务包**。当前无候选可生成任务包。

readiness 报告中 `test_blind_leakage` 状态为 `NOT_PROVIDED`，`leakage_count = 0`（vacuous truth）。

## 双标与角色独立计划

**未分配**。当前无标注员 A / B / 裁决员 pseudonym。

readiness 报告中 `human_roles` 检查项：
- `annotator_a_ready = false`
- `annotator_b_ready = false`
- `adjudicator_ready = false`
- `roles_distinct = false`（vacuous）
- `double_label_plan_count = 0`

## 生产 Pack 信任链

**未执行**。生产 pack 签名密钥缺失。

readiness 报告中 `production_signing_key` 检查项：
- `prod_key_present = false`
- `key_id = null`
- `substitute_detected = false`（关键：未尝试用 fixture/test 密钥替代）

## Readiness 机器证据

正式发布到 `docs/P13-2-evidence/real-annotation-launch-readiness.json`：

```json
{
  "status": "BLOCKED_INSUFFICIENT_REAL_CANDIDATES",
  "passed": false,
  "exit_code": 2,
  "schema_version": "readiness-1.0.0",
  "blockers": [
    "BLOCKED_HUMAN_ROLES_NOT_READY",
    "BLOCKED_INSUFFICIENT_REAL_CANDIDATES",
    "BLOCKED_MISSING_PACK_SIGNING_KEY"
  ],
  "human_verified_count": 0,
  "human_labels_complete": false,
  "calibration_allowed": false,
  "kappa": 0.0,
  "kappa_threshold": 0.7,
  "disagreement_adjudicated": true,
  "fixture_substitute_detected": false,
  "minimums": {
    "authorized_candidates": 100,
    "development": 50,
    "calibration": 25,
    "test_blind": 25,
    "double_label": 20,
    "double_label_ratio": 0.2
  }
}
```

artifact SHA-256：`c4358306305c09a8032f7bc312ebd34f444602fb5ed92ac480a35a49da8f7727`

## 14 类负例（DeepSeek 规约要求）

新增测试文件 `tests/test_p13_2_real_annotation_launch_readiness.py` 共 **48 项测试**，覆盖以下 14 类负例 + 正例 + 不变量 + 字段全覆盖：

| 编号 | 场景 | 命中结构化 check | 测试方法 |
| --- | --- | --- | --- |
| N1 | 候选数 99 但 eligible_count=100 | `BLOCKED_INSUFFICIENT_REAL_CANDIDATES` | 注入 eligible_count=99，断言 exit 2 |
| N2 | fixture 混入真实候选 | `fixture_contamination` 非空 | sample_id 匹配 fixture 模式 |
| N3 | source_url/auth/captured_at/hash 缺失 | `authorization_incomplete_rows >= 1` | 14 个 AUTHORIZATION_REQUIRED_FIELDS 全覆盖（参数化） |
| N4 | 未脱敏 PII 进入任务包 | `BLOCKED_PII_NOT_PROCESSED` | 注入 email/手机号 |
| N5 | 重复内容跨 dev/test | `cross_split_overlap` 非空 | dev 与 test 共享 sample_id |
| N6 | test 包含 preannotation/prediction/model/confidence | `BLOCKED_TEST_BLIND_LEAKAGE` | 12 个 TEST_BLIND_FORBIDDEN_FIELDS 全覆盖（参数化） |
| N7 | 双标 < 20 或低于 20% | `meets_double_label_minimum = false` | 两种触发：纯下限、比例下限 |
| N8 | 同一 pseudonym A/B | `roles_distinct = false` | A=B 共享 pseudonym |
| N9 | A 包可读取 B 标签（distinctness 违反） | `roles_distinct = false` | A=adjudicator 共享 |
| N10 | 生产使用测试签名密钥 | `substitute_detected = true` | 两种触发：模式匹配、test env 边界 |
| N11 | pack 签名/dataset/task hash 修改 | （由 P13-2-2-1A 已验收的 verifier 覆盖） | 复用现有 committed-evidence verifier |
| N12 | 人工角色未就绪却标 READY | `BLOCKED_HUMAN_ROLES_NOT_READY` | annotator_b_pseudonym="" |
| N13 | 无真实人工标签却把 human_verified_count 写为正数 | 不变量 `human_verified_count == 0` | 即使 READY 也保持 0 |
| N14 | 本阶段把 calibration_allowed 设为 true | 不变量 `calibration_allowed is False` | 即使 READY 也保持 false |

所有负例通过 `main(evidence_dir=tmp_path, ..., publish=False)` 注入调用，模块级 fixture 在测试前后断言真实 `docs/P13-2-evidence/real-annotation-launch-readiness.json` SHA 不变。

## human/calibration 状态不变量

readiness 报告与代码强约束（非配置可调）：

- `human_verified_count = 0`（P13-2-2-2A 完成边界明文要求）
- `human_labels_complete = false`
- `calibration_allowed = false`
- `kappa = 0.0`（无可计算样本）
- `disagreement_adjudicated = true`（vacuously：0 个分歧均已裁决）

这些字段被硬编码在 `assess_readiness()` 返回字典中，**不受任何输入或环境变量影响**。即使所有 blocker 都解除进入 READY 状态，这些字段仍保持上述值——P13-2-2-2A 只允许"启动"，不允许"完成"。

## 静态、测试与正式运行

| 检查 | 结果 |
| --- | --- |
| Ruff（signal_miner + tests + scripts） | PASS |
| readiness 聚焦测试 | **48 passed** |
| 全量回归 | **376 passed, 3 warnings**（前次 328 + 新增 48 = 376） |
| 正式 readiness 脚本 | `BLOCKED_INSUFFICIENT_REAL_CANDIDATES / exit 2` |
| 正式 orchestrator | `PASS / exit 0`，run_id=`b7e50eeb-b294-42e9-a453-6153e0015764` |
| Pack mutation | 23/23 |
| Annotation mutation | 34/34 |
| committed-evidence verifier | PASS / exit 0 |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | `READY / passed=true` |
| `git diff --check` | PASS |

### 测试隔离

模块级 fixture `real_evidence_sha_guard` 在测试前后断言真实 `docs/P13-2-evidence/real-annotation-launch-readiness.json` SHA 不变。所有 48 项测试通过 `tmp_path` 注入，**未触碰正式 evidence**。

三份正式 evidence SHA（unchanged）：
- `pack-trust-contract-metrics.json`: `1241c6577a340138`
- `pack-trust-mutation-gate.json`: `d5c57ef0bdc9cb40`
- `human-annotation-mutation-gate.json`: `e9f406bcbe265b99`

## 新增文件

1. `scripts/p13_2_real_annotation_launch_readiness.py`（约 600 行）— readiness 检查 CLI 与可注入 `main()`。
2. `tests/test_p13_2_real_annotation_launch_readiness.py`（约 380 行）— 48 项契约测试。
3. `docs/P13-2-evidence/real-annotation-launch-readiness.json`— 正式 readiness artifact。
4. `docs/acceptance-P13-2-2-2A-delivery-20260714.md`— 本交付报告。

## 未覆盖风险与人工待办

### 用户必须提供才能解锁 P13-2-2-2B 的输入

1. **真实授权候选数据**（≥100 条）：
   - 每条必须含完整 `AUTHORIZATION_REQUIRED_FIELDS`（dataset_id、sample_id、raw_feedback_id、source_url、captured_at、content_sha256、authorization_basis、authorization_record_ref、permitted_use、pii_scanned、pii_redacted、raw_text_sha256、redacted_text_sha256、profile、language、source_tier）
   - 提供方式：受控的真实数据挂载/引用配置（不进 Git）
2. **生产 pack 签名密钥**：
   - 通过 `ANNOTATION_PACK_SIGNING_KEY` 环境变量注入（生产环境，非 test env）
   - 不得与 `ANNOTATION_PACK_TEST_SIGNING_KEY` 相同
   - 不得匹配 fixture/test/example/dummy 模式
3. **独立人工标注角色**：
   - 标注员 A、标注员 B、裁决员三个不同 pseudonym
   - 通过 CLI `--roles-config` 或受控配置文件提供
4. **标注执行窗口**：保留期限、允许访问人员范围

### 仍冻结的下游阶段

- **P13-2-2-2B**：真实人工标注完成验收（需要 ≥100 条 human label、≥25 条 test 盲标、双标达标、kappa ≥ 0.70）
- **P13-2-3**：指标调优（继续冻结）
- **P13-2-4**：校准（继续冻结）
- **P13-3**：去重聚类优化（继续冻结）
- **前端概率发布**（继续冻结）

## 完成边界声明

P13-2-2-2A 本次交付**未通过**（按设计正确 BLOCKED），但不视为实现失败——

- 缺失外部输入属于 `exit 2 / BLOCKED`，**不计作实现失败**（DeepSeek 规约明文）
- readiness 工具链本身已就绪，能在用户输入到位后立即运行
- 未生成任何伪真实 task pack 或人工 label
- 未尝试用 fixture/LLM/规则标签补齐
- P13-2-2-1A 已验收的工具链（contract metrics、committed-evidence verifier、behavior probe、goldset）全部继续通过
