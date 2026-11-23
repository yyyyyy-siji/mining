# P13-2-2-2A fix-4 交付报告：批次身份与 group metadata 结构化门禁

交付日期：2026-07-15

## 结论：fix-4 完成，正式运行仍 `BLOCKED_INPUT_REQUIRED / exit 2`

## 修改文件 SHA

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `5e025d43a6ae6ff2ba9577e98d73e8244703bdc597096a09efa2f2c2a873706d` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `06eeb9c44028b225e82239d5d095cb506bf0a684a156c1c5cd180fcf92f974cf` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `b6e98961863df7c72fcbafb6b0d0aba21fe20f64138548b88d8f884354852031` |

Sidecar 对账：
```text
sidecar: 73c6030e... == shasum: 73c6030e... MATCH: YES
```

## 核心修复

| 修复 | 变更 |
| --- | --- |
| batch_id 绑定 7 组件 | `batch_id_components` 包含 dataset_manifest, pack_manifest, real_candidate_export, real_rejections, roles_config, splits_config, governance_config |
| 逐行 group metadata | `_check_group_isolation` 逐行检查 session_id (非空), conversation_id (非空), near_duplicate_group_id 存在 |
| naive datetime 结构化失败 | `_check_annotation_governance` 在发现 naive datetime 后 `return obs, errs`，不继续比较 |
| 交付报告 | `docs/acceptance-P13-2-2-2A-delivery-fix-4-20260715.md` |

## READY 正例 JSON 摘要

```json
{
  "status": "READY_FOR_HUMAN_ANNOTATION",
  "passed": true,
  "exit_code": 0,
  "dataset_id": "ds_prod_20260714",
  "batch_id": "annbatch_92d9c6be421d2aca",
  "batch_id_components": {
    "dataset_manifest": "5799aaaa...",
    "pack_manifest": "cd5010fa...",
    "real_candidate_export": "9ab247af...",
    "real_rejections": "4f53cda1...",
    "roles_config": "0b6f7937...",
    "splits_config": "eae593a4...",
    "governance_config": "147d72d1..."
  },
  "human_verified_count": 0,
  "calibration_allowed": false
}
```

## 生产 CLI 负例（fix-4 新增 7 项）

| 编号 | 场景 | exit | status | target check |
| --- | --- | --- | --- | --- |
| F4-B1 | READY batch_id 非 null 含 7 组件 | 0 | READY | batch_id != null |
| F4-B2 | governance 变更 batch_id 变化 | 0 | READY | batch_id 不同 |
| F4-B3 | roles 变更 batch_id 变化 | 0 | READY | batch_id 不同 |
| F4-G1 | 单条 candidate 缺失全部 group metadata | 1 | FAILED | group_isolation=false |
| F4-G2 | 单条 candidate session_id 缺失 | 1 | FAILED | group_isolation=false |
| F4-DT | naive datetime → 结构化 exit1 | 1 | FAILED | annotation_governance=false |
| F4-G3 | cross-split session group | 1 | FAILED | group_isolation=false |

## 验收命令退出码

| 命令 | 结果 |
| --- | --- |
| Ruff | All checks passed |
| 聚焦 pytest | **42 passed** |
| 全量 pytest | **370 passed, 3 warnings** |
| `--verify-evidence` | PASS / exit 0 |
| 正式 readiness | `BLOCKED_INPUT_REQUIRED / exit 2` |
| `git diff --check` | PASS |

## 回归保护

所有 fix-3 已关闭反例继续通过：
- candidate dataset_id 错误 → exit1
- COUNT_RECOMPUTE_MISMATCH → exit1
- test blind leakage → exit1
- signature/hash tamper → exit1
- task-candidate binding mismatch → exit1
- 零输入 → exit2 BLOCKED

P13-2-2-1A 信任链未受影响。

## 未覆盖风险

- near_duplicate_group_id cross-split leakage 测试需要多 candidate 共享 nd_group 值；当前测试 fixture 使用 None sentinel，视为"无近重复组"
- 批量子组件 SHA 未验证分拆后的独立重算（每个组件 SHA 由 `_file_sha` 直接计算）
