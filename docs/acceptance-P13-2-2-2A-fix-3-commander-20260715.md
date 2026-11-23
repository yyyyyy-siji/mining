# P13-2-2-2A fix-3 Commander 复验报告

验收日期：2026-07-15

结论：不通过，需要执行 fix-4。fix-3 修复了主要候选/任务绑定假绿，但仍未满足批次身份、group metadata 与交付证据契约。

## 已通过项

| 检查 | 结果 |
| --- | --- |
| `--verify-evidence` | PASS / exit 0 |
| focused ruff | PASS / exit 0 |
| `git diff --check` | PASS / exit 0 |
| 聚焦 pytest | 35 passed |
| 全量 pytest | 363 passed, 3 warnings |
| 正向生产 CLI | `READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true` |
| 候选行 dataset_id 错误反例 | exit1，`real_candidates=false` |
| ghost task 重算 hash + 重新签名反例 | exit1，`task_candidate_binding=false` |
| task content_hash 与 candidate 不一致反例 | exit1，`task_candidate_binding=false` |
| A/B 同 sample content_hash 不一致反例 | exit1，`task_candidate_binding=false` |
| 105候选但只有20双标反例 | exit1，`required_double_label=21` |
| cross-split session group 反例 | exit1，`group_isolation=false` |

实际 SHA：

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `67ff1452503080f178c446a44091f9a1143f02925d0f86519026068952c26603` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `e13ed79b76e9074eb7861a8f08f2e7559b7aaee65dd8863bf25ef1f3527b7c19` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `83ea2a7a5ffbd189c5369f0e6395c3e1e7f015d4e8cf5e9672f7927ea82ce46a` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256` | `96265d2c3bdd32eb650fd3e02ac5d37b668d2f244a62f8b03d74c510948bd382` |

## 阻断问题

### P0-1：deterministic batch_id 未绑定全部 launch 输入

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1425`

问题：

fix-3 已让 READY 输出非空 `batch_id`，但只使用 `dataset_manifest_sha256`、`pack_manifest_sha256`、`real_candidate_export_sha256` 三项生成：

```python
for sha_opt in (dm_sha, pm_sha, rc_sha):
```

未纳入 `real_rejections_path`、`roles_config_path`、`splits_config_path`、`governance_config_path`。这违反 fix-3 指令中“任一输入文件内容变化 batch_id 改变”的要求。

Commander 生产 CLI 反例：

```text
同一完整 launch config 第一次 READY:
batch_id = annbatch_2915c6a4c34c8774

仅修改 governance.annotation_window_end:
2026-09-01T00:00:00Z -> 2026-10-01T00:00:00Z

第二次仍 READY:
batch_id = annbatch_2915c6a4c34c8774
changed = false
```

影响：

同一批次身份无法反映治理窗口、角色、split 或 rejection 输入变化。后续人工标注批次审计、旧数据处理和数据生命周期追踪会误把不同输入视为同一批。

验收要求：

- READY 的 `batch_id` 必须至少绑定以下文件 SHA：dataset manifest、pack manifest、real candidate export、real rejections、roles、splits、governance。
- 相同输入重复运行 `batch_id` 必须相同。
- 任一上述输入文件内容变化且仍 READY 时，`batch_id` 必须变化。
- evidence 中应输出 `batch_id_components`，列出参与计算的组件名与 SHA。

### P0-2：单条候选缺失全部 group metadata 仍 READY

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1206`

问题：

`_check_group_isolation()` 只判断是否“任意候选、任意 group 字段存在”。只要其他候选有 group 字段，单条候选缺失所有 group metadata 不会失败。

Commander 生产 CLI 反例：

```text
删除 candidates[0] 的 session_id、conversation_id、near_duplicate_group_id
其余输入保持完整有效

结果:
READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true
group_isolation=true
missing_group_metadata=false
```

影响：

部分候选无法证明 session/conversation/near-duplicate 隔离，仍可进入人工标注启动。这是数据来源去重与 split 隔离的假绿。

验收要求：

- 必须逐 candidate 校验 required group metadata。
- 建议要求每条 candidate 至少具备非空 `session_id` 与 `conversation_id`；`near_duplicate_group_id` 若允许为空，必须以显式 sentinel 表示“无近重复组”，并纳入检查。
- 任一 candidate 缺失 required group metadata 必须 `FAILED_INVALID_INPUT / exit1 / group_isolation=false`，或按明确契约 `BLOCKED_INPUT_REQUIRED / exit2`。

### P1-1：fix-3 交付报告缺失

问题：

未发现 `docs/acceptance-P13-2-2-2A-delivery-fix-3-*.md` 或等价 fix-3 交付报告。当前无法由执行方报告对账：修改文件、生产 CLI 负例、READY 正例、SHA、测试数量、未覆盖风险。

验收要求：

- fix-4 必须提交独立交付报告，不得只修改代码后口头声明完成。
- 报告必须列出当前实际 SHA，并与 `shasum -a 256` 一致。

### P1-2：naive governance 时间走 unexpected TypeError，结构化 target 丢失

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:803`
- `scripts/p13_2_real_annotation_launch_readiness.py:817`

问题：

naive datetime 已追加 `annotation_governance` 错误，但函数继续比较 naive 与 aware datetime，触发 `TypeError`，最终被顶层 unexpected 捕获：

```json
{
  "status": "FAILED_INVALID_INPUT",
  "passed": false,
  "errors": [
    "[invalid] unexpected: TypeError: can't compare offset-naive and offset-aware datetimes"
  ],
  "check_passed": {},
  "blockers": []
}
```

影响：

虽然 exit1，但结构化证据丢失，不能证明 `annotation_governance=false`，也不利于后续机器门禁和报告对账。

验收要求：

- naive datetime 必须结构化失败：`annotation_governance=false`、`blockers=["annotation_governance"]`、无 unexpected exception。
- 测试必须断言 target check，而不只断言 exit1。

### P1-3：测试仍未覆盖 fix-3 契约

位置：

- `tests/test_p13_2_real_annotation_launch_readiness.py:1`
- `tests/test_p13_2_real_annotation_launch_readiness.py:310`

问题：

测试文件头仍标记 fix-2；聚焦测试数量仍为35。正向测试仍只断言：

```python
assert dl["double_label_actual_count"] >= 1
```

未断言：

- `batch_id` 非空；
- `batch_id` 稳定且输入变化时变化；
- `required_double_label == 21`；
- group metadata 逐 candidate 必填；
- naive governance 时间结构化失败；
- 新增生产 CLI 级反例。

验收要求：

- 将上述反例固化为测试或独立 evidence probe。
- 聚焦测试必须体现 fix-4 新增覆盖，不能继续只有35项且缺少关键断言。

## 非阻断观察项

- 正式 no-input evidence 仍为 `BLOCKED_INPUT_REQUIRED / exit2`，这部分符合当前真实输入为0的状态。
- `group_isolation` 在正式0候选 evidence 中显示 `true`，语义容易误导。建议在候选缺失时显示 `not_applicable` 或由 blocker 解释，而不是单独 true。

## 复验要求

fix-4 完成后必须提供：

- fix-4 交付报告；
- 生产 CLI 正例 evidence，含 `batch_id_components`；
- 生产 CLI 负例：governance 变化导致 batch_id 变化、单条候选缺 group metadata 失败、naive governance 时间结构化失败；
- focused pytest、full pytest、ruff、`--verify-evidence`、`git diff --check` 退出码；
- 当前实际 SHA 对账。

## 问题统计归类

- 验证脚本假阳性 / 关键契约未参与测试：新增 1 次 P0。
- 完成声明缺交付报告：新增 1 次 P1。
- 结构化机器证据缺失：新增 1 次 P1。

结论：P13-2-2-2A fix-3 不通过。不得进入 P13-2-2-2B、主动学习评测、置信度拟合、P13-3 或前端概率发布。
