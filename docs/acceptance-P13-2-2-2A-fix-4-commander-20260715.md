# P13-2-2-2A fix-4 Commander 复验报告

验收日期：2026-07-15

结论：不通过，需要执行 fix-5。fix-4 已修复批次身份、session/conversation group、naive governance 结构化错误，但 near-duplicate group 仍存在 READY 假绿。

## 已通过项

| 检查 | 结果 |
| --- | --- |
| fix-4 交付报告 | 存在：`docs/acceptance-P13-2-2-2A-delivery-fix-4-20260715.md` |
| 报告 SHA 对账 | 脚本、测试、正式 evidence SHA 与当前文件一致 |
| `--verify-evidence` | PASS / exit 0 |
| focused ruff | PASS / exit 0 |
| `git diff --check` | PASS / exit 0 |
| 聚焦 pytest | 42 passed |
| 全量 pytest | 370 passed, 3 warnings |
| READY 正例 | `READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true` |
| `batch_id` | 非空，含 7 个 component |
| governance 变化 | 仍 READY，`batch_id` 变化 |
| roles 变化 | 仍 READY，`batch_id` 变化 |
| rejections 变化 | 仍 READY，`batch_id` 变化 |
| 单条 candidate 缺 session/conversation | exit1，`group_isolation=false` |
| naive governance datetime | exit1，`annotation_governance=false`，无 unexpected |

实际 SHA：

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `5e025d43a6ae6ff2ba9577e98d73e8244703bdc597096a09efa2f2c2a873706d` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `06eeb9c44028b225e82239d5d095cb506bf0a684a156c1c5cd180fcf92f974cf` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `b6e98961863df7c72fcbafb6b0d0aba21fe20f64138548b88d8f884354852031` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256` | `73c6030e9ae6594c3532f9d1e855129c7360c95abd7f464358a1dc6c76c0a89e` |

## 阻断问题

### P0-1：candidate 源字段缺失 near_duplicate_group_id 仍 READY

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:314`
- `scripts/p13_2_real_annotation_launch_readiness.py:1249`

问题：

candidate index 使用 `cand.get("near_duplicate_group_id")` 构造字段：

```python
"near_duplicate_group_id": cand.get("near_duplicate_group_id"),
```

因此即使源 candidate 行完全没有 `near_duplicate_group_id` 字段，进入 `candidate_index` 后也会被补成 key 存在、value 为 `None`。后续检查：

```python
"near_duplicate_group_id" not in ci
```

永远无法识别源字段缺失。

Commander 生产 CLI 反例：

```text
删除 candidates[0].near_duplicate_group_id
其他输入保持完整有效

结果:
READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true
group_isolation=true
missing_group_rows=[]
```

影响：

readiness 无法区分“明确声明无近重复组”和“数据来源未提供近重复组字段”。这会让未完成近重复隔离的数据源进入人工标注启动。

验收要求：

- 必须保留源字段存在性，例如 `has_near_duplicate_group_id = "near_duplicate_group_id" in cand`。
- 源 candidate 缺失 `near_duplicate_group_id` 字段必须 `FAILED_INVALID_INPUT / exit1 / group_isolation=false`，或按明确契约 `BLOCKED_INPUT_REQUIRED / exit2`。
- 测试必须走生产 CLI 或唯一生产主路径，并断言 `missing_group_rows` 包含对应 sample。

### P0-2：非空 near_duplicate_group_id 跨 split 仍 READY

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1262`

问题：

`_check_group_isolation()` 对 `near_duplicate_group_id` 直接 `continue`：

```python
if group_field == "near_duplicate_group_id":
    continue
```

Commander 生产 CLI 反例：

```text
candidates[0] development.near_duplicate_group_id = "ndg_cross"
candidates[test_0000].near_duplicate_group_id = "ndg_cross"

结果:
READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true
group_isolation=true
cross_split_groups=[]
```

影响：

近重复样本可以同时进入 development 与 test，导致评测集污染。这直接违背“group 隔离只验证冻结 group 字段，不实现新聚类”的阶段契约。

验收要求：

- `near_duplicate_group_id` 为非空、非 null、非明确 none sentinel 时，必须作为 group key 参与跨 split 检查。
- 同一 near_duplicate_group_id 出现在多个 split 时必须 exit1，`group_isolation=false`。
- 若使用 sentinel 表示无近重复组，必须保证 sentinel 不会把所有无近重复样本误归为同一组；建议使用 `none:<sample_id>` 或显式 `near_duplicate_group_absent_reason`。

## 非阻断观察项

- 非 READY 状态下 `batch_id_components` 仍为空 `{}`。fix-4 指令中写的是“应能帮助定位已提供/缺失组件”，这项没有作为本轮 P0 阻断，但建议 fix-5 顺手补为可观测字段。
- 交付报告的“未覆盖风险”已经承认 near_duplicate cross-split 未覆盖；该风险在 Commander 生产 CLI 中被证实为实际假绿，因此升级为 P0。

## 复验要求

fix-5 只需收口 near-duplicate group：

- 源字段缺失 `near_duplicate_group_id` 必须失败；
- 非空 near_duplicate group 跨 split 必须失败；
- READY 正例必须使用明确 sentinel 或 absent reason；
- 保留 fix-4 已通过的 batch/session/conversation/timezone 反例；
- 提交 fix-5 交付报告和当前 SHA。

## 问题统计归类

- 验证脚本假阳性 / 关键契约未参与测试：新增 1 次 P0。
- 未覆盖风险被证实为实际假绿：新增 1 次 P0。

结论：P13-2-2-2A fix-4 不通过。不得进入 P13-2-2-2B、主动学习评测、置信度拟合、P13-3 或前端概率发布。
