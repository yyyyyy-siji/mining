# DeepSeek 返修指令：P13-2-2-2A fix-4 批次身份与 group metadata 结构化门禁

## 任务目标

在不扩大阶段范围的前提下，修复 fix-3 复验剩余阻断：

- `batch_id` 未绑定全部 launch 输入；
- 单条候选缺失全部 group metadata 仍 READY；
- naive governance 时间触发 unexpected TypeError，结构化 target 丢失；
- fix-3 没有交付报告，测试没有覆盖新增契约。

当前真实输入仍为0，正式默认运行必须继续 `BLOCKED_INPUT_REQUIRED / exit2`。

## 允许修改范围

- `scripts/p13_2_real_annotation_launch_readiness.py`
- `tests/test_p13_2_real_annotation_launch_readiness.py`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
- `docs/acceptance-P13-2-2-2A-delivery-fix-4-20260715.md`

## 禁止修改范围

- 不得修改或弱化 P13-2-2-1A 信任链：`signal_miner/evaluation/pack_trust.py`、`human_annotation.py`、importer、mutation gate、committed verifier。
- 不得进入 P13-2-2-2B 或生成任何真实人工标注结果。
- 不得删除已关闭的生产 CLI 反例；只能补充或重命名。

## 实现要求

### 1. batch_id 必须绑定全部 launch 输入

READY 时必须输出：

```json
{
  "batch_id": "annbatch_<16hex>",
  "batch_id_components": {
    "dataset_manifest_sha256": "...",
    "pack_manifest_sha256": "...",
    "real_candidate_export_sha256": "...",
    "real_rejections_sha256": "...",
    "roles_config_sha256": "...",
    "splits_config_sha256": "...",
    "governance_config_sha256": "..."
  }
}
```

要求：

- 相同输入重复运行 `batch_id` 相同；
- 任一 component 文件内容变化且仍 READY 时，`batch_id` 必须变化；
- 任一 required component 缺失时不得 READY；
- 非 READY 状态 `batch_id` 可以为 null，但 `batch_id_components` 应能帮助定位已提供/缺失组件。

必须新增生产 CLI 测试或 evidence probe：

- baseline READY；
- 仅修改 governance 的有效字段，仍 READY，但 batch_id 改变；
- 仅修改 roles 的有效字段，仍 READY，但 batch_id 改变；
- 仅修改 splits 且仍满足约束的情况下，batch_id 改变；如不存在合法变更，报告说明并至少覆盖 governance/roles/rejections。

### 2. group metadata 必须逐 candidate 校验

定义并实现明确契约：

- 每条 candidate 必须有非空 `session_id`；
- 每条 candidate 必须有非空 `conversation_id`；
- 每条 candidate 必须包含 `near_duplicate_group_id` 字段；若无近重复组，使用明确 sentinel，例如 `"none:<sample_id>"` 或 `null` 加 `near_duplicate_group_absent_reason`。选择一种并写入交付报告。

要求：

- 任一 candidate 缺失 required group metadata，必须 `FAILED_INVALID_INPUT / exit1 / group_isolation=false`，或明确作为缺输入 `BLOCKED_INPUT_REQUIRED / exit2`；不能 READY。
- `checks.group_isolation` 必须包含 `missing_group_rows` 或等价字段，列出前20个缺失样本。
- cross-split group 泄漏必须继续 exit1。

必须新增生产 CLI 负例：

- 删除单条 candidate 的全部 group metadata；
- 删除单条 candidate 的 `session_id`；
- 删除单条 candidate 的 `conversation_id`;
- cross-split session group。

### 3. governance 时间必须结构化失败，不得 unexpected

修复 naive datetime 分支：

- 发现 naive datetime 后，记录 `InputError("invalid", "annotation_governance", ...)`；
- 不得继续执行 naive 与 aware 的比较；
- 最终输出必须包含：

```json
{
  "status": "FAILED_INVALID_INPUT",
  "passed": false,
  "exit_code": 1,
  "blockers": ["annotation_governance"],
  "check_passed": {"annotation_governance": false}
}
```

必须新增测试：

- `annotation_window_start="2026-08-01T00:00:00"` -> exit1，`annotation_governance=false`，无 `unexpected`。

### 4. 测试与报告必须反映 fix-4

要求：

- 测试文件标题更新为 fix-4 或当前阶段，不得继续写 fix-2。
- 正向测试必须断言：
  - `batch_id is not None`;
  - `batch_id_components` 包含全部 required keys；
  - `required_double_label == 21`；
  - `double_label_actual_count >= required_double_label`。
- 聚焦测试必须新增覆盖项；如果测试数量仍为35，交付报告必须解释合并了哪些测试，否则视为覆盖不足。
- 所有新增关键反例必须走生产 CLI 或与生产 CLI 共用的唯一路径。

## 验收命令

```bash
.venv/bin/ruff check scripts/p13_2_real_annotation_launch_readiness.py tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
git diff --check
```

全部必须 exit 0。

## 交付报告要求

必须新增：

```text
docs/acceptance-P13-2-2-2A-delivery-fix-4-20260715.md
```

报告必须包含：

- 修改文件清单与实际 SHA；
- 正式 no-input evidence 状态；
- READY 正例 JSON 摘要；
- batch_id component 表；
- 每条生产 CLI 负例的 exit/status/passed/target check；
- focused/full pytest 数量与 warnings；
- 未覆盖风险。

## 完成边界

fix-4 通过只表示 readiness 可以安全判断“是否可启动真实人工标注”。真实人工标注尚未完成，不得进入 P13-2-2-2B、模型校准、聚类优化或前端发布。
