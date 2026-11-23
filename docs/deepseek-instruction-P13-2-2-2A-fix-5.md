# DeepSeek 返修指令：P13-2-2-2A fix-5 near-duplicate group 闭环

## 任务目标

只修复 fix-4 剩余的 near-duplicate group 假绿：

- 源 candidate 缺失 `near_duplicate_group_id` 字段仍 READY；
- 非空 `near_duplicate_group_id` 跨 split 仍 READY。

fix-4 已通过的 batch identity、session/conversation group、naive governance 结构化错误不得回退。

## 允许修改范围

- `scripts/p13_2_real_annotation_launch_readiness.py`
- `tests/test_p13_2_real_annotation_launch_readiness.py`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
- `docs/acceptance-P13-2-2-2A-delivery-fix-5-20260715.md`

## 禁止修改范围

- 不得修改或弱化 P13-2-2-1A 信任链文件。
- 不得扩大到 P13-2-2-2B 或生成真实人工标注结果。
- 不得删除 fix-4 已通过测试；只能补充或重命名。

## 实现要求

### 1. 保留源字段存在性

当前 `candidate_index` 通过 `cand.get("near_duplicate_group_id")` 丢失了“源字段是否存在”的信息。

必须在 candidate index 中记录：

```python
has_near_duplicate_group_id = "near_duplicate_group_id" in cand
```

或等价结构。

要求：

- 源 candidate 行缺失 `near_duplicate_group_id` 字段时，不得 READY；
- 输出 `checks.group_isolation.missing_group_rows`，包含缺失行 sample_id；
- 结构化结果必须为 `FAILED_INVALID_INPUT / exit1 / group_isolation=false`，或如选择缺输入语义，则为 `BLOCKED_INPUT_REQUIRED / exit2`，但必须在交付报告中说明。

### 2. 非空 near_duplicate_group_id 必须参与跨 split 检查

要求：

- `near_duplicate_group_id` 为非空字符串且不是 none sentinel 时，必须作为 group key 检查跨 split；
- 同一 `near_duplicate_group_id` 出现在 development/calibration/test 任意两个 split 时，必须 exit1，`group_isolation=false`；
- 如果使用 sentinel 表示无近重复组，必须避免所有无近重复样本共享同一个 sentinel。建议：
  - `near_duplicate_group_id = null` 且 `near_duplicate_group_absent_reason` 非空；或
  - `near_duplicate_group_id = "none:<sample_id>"`。

### 3. 测试要求

必须新增或修正测试：

- 删除单条 candidate 的 `near_duplicate_group_id` 字段 -> 失败；
- development 与 test 共享非空 `near_duplicate_group_id` -> 失败；
- READY 正例仍通过，且每条 candidate 的 near duplicate contract 明确；
- fix-4 已通过反例继续通过：batch 7组件、governance/roles/rejections 变化、session/conversation 缺失、naive governance。

新增关键反例必须走生产 CLI 或与生产 CLI 共用的唯一生产主路径。

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
docs/acceptance-P13-2-2-2A-delivery-fix-5-20260715.md
```

报告必须列出：

- 修改文件与 SHA；
- READY 正例 near duplicate contract；
- 两个 near duplicate 生产 CLI 负例；
- fix-4 回归保护；
- focused/full pytest 数量。

## 完成边界

fix-5 通过只表示 readiness 可安全判断“是否可启动真实人工标注”。真实人工标注仍未完成，不得进入 P13-2-2-2B 或后续模型/前端阶段。
