# P13-2-2-2B 输入阻塞报告

日期：2026-07-15
状态：**INPUT-GATED / BLOCKED**

P13-2-2-2B 当前无法执行。这不是代码缺陷或实现失败——readiness 工具链（P13-2-2-2A）已通过 Commander 验收，能诚实判定启动条件。阻塞源于缺少真实外部输入。

## Readiness 实际状态

```text
status: BLOCKED_INPUT_REQUIRED
passed: false
exit_code: 2
human_verified_count: 0
human_labels_complete: false
calibration_allowed: false
blockers (9):
  - annotation_governance
  - human_roles
  - pack_trust
  - production_signing_key
  - real_candidates
  - split_isolation
  - task_candidate_binding
  - task_identity
  - test_blind_leakage
```

## 缺失输入清单

| 输入 | 状态 | 说明 |
| --- | --- | --- |
| 真实授权候选数据 | 缺失 | `eligible_count=0`，`rejected_count=1257`（全部因缺授权被拒） |
| 真实 rejection 记录 | 缺失 | — |
| dataset manifest | 缺失 | — |
| 四类 task pack + pack manifest + 生产签名 | 缺失 | — |
| 冻结 dev/cal/test split | 缺失 | — |
| annotator A pseudonym | 缺失 | 必须为真实独立人类，非 LLM/fixture/规则 |
| annotator B pseudonym | 缺失 | 必须为真实独立人类，必须 ≠ A |
| adjudicator pseudonym | 缺失 | 必须为真实独立人类，必须 ≠ A 且 ≠ B |
| annotation governance（窗口/retention/access） | 缺失 | — |
| 生产签名密钥 | 缺失 | 必须通过环境安全注入，不得写入仓库或报告 |

## 启动前置条件（全部满足才可分发任务）

1. ≥100 条真实授权脱敏候选
2. ≥25 条冻结 test 盲标
3. A/B/adjudicator 三个互不相同的人类 pseudonym
4. 时区完整的 governance 配置
5. 生产签名密钥（非 test/fixture key）
6. P13-2-2-2A readiness 返回 `READY_FOR_HUMAN_ANNOTATION / exit 0 / passed=true`，且 batch_id 非空、7 组件全部非空

## 未执行操作

- 未生成任何真实人工标签
- 未导入 fixture 标签
- 未生成 real human annotation store
- 未执行 adjudication
- 未生成 human annotation contract metrics
- 未进入校准（calibration_allowed=false）
- 未修改已验收 readiness、信任链、导入器或 validator

## 当前可执行的安全操作

仅以下操作可在无真实数据时执行：

```bash
# 确认 readiness 正确阻塞
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish

# 确认 evidence 完整
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence

# 确认信任链未退化
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
.venv/bin/python -m pytest -o addopts= -q
```

以上命令均已在 2026-07-15 验证通过（372 passed, 3 warnings）。

## 下一项用户输入

需要用户或授权外部流程提供：**真实授权候选数据（≥100 条，含完整授权元数据）、生产签名密钥、独立人类标注角色**。

输入到位后通过 `--launch-config <real.json>` 运行 readiness，若 READY 则可分发人工任务并进入正式 2B 执行。
