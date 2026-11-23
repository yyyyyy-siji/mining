# DeepSeek 返修指令：P13-2-2-2A fix-3 候选-任务绑定与批次身份闭环

## 任务目标

关闭 P13-2-2-2A fix-2 仍存在的 READY 假绿：

- 候选行 `dataset_id` 错误时仍 READY；
- READY artifact 的 `batch_id` 为 `null`；
- task、split、candidate 没有形成逐任务绑定门禁；
- 双标阈值、group 隔离、timezone 治理仍未按任务书严格验证。

当前无真实用户输入时，正式默认运行仍必须 `BLOCKED_INPUT_REQUIRED / exit2`。不得为追求 READY 伪造真实人工标注。

## 允许修改范围

- `scripts/p13_2_real_annotation_launch_readiness.py`
- `tests/test_p13_2_real_annotation_launch_readiness.py`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
- P13-2-2-2A fix-3 交付报告

如确实需要新增 readiness 专用小 helper，必须保持范围局限，不得修改已验收的 P13-2-2-1A 信任链实现。

## 禁止修改范围

- 不得修改或弱化 `signal_miner/evaluation/pack_trust.py`、`human_annotation.py`、1A importer、mutation gate、orchestrator 或 committed-evidence verifier。
- 不得复制简化版签名/hash verifier 替代 1A 单一真源。
- 不得生成真实人工 label、LLM label、规则 label 来冒充人工完成。
- 不得进入 P13-2-2-2B、P13-2-3、P13-2-4、P13-3 或前端发布。
- 不得删除既有已关闭回归测试；如合并测试，交付报告必须列明替代关系。

## 实现要求

### 1. 候选 dataset identity 必须逐行校验

构建 canonical authorized candidate index：

```text
candidate_index[sample_id] = {
  dataset_id,
  content_sha256,
  split,
  source_adapter,
  source_version,
  captured_at,
  authorization fields,
  group metadata
}
```

要求：

- 每条 candidate 必须有 `dataset_id`；
- 所有 candidate 的 `dataset_id` 必须唯一一致；
- candidate `dataset_id` 必须等于 dataset manifest `dataset_id`；
- `sample_id` 必须唯一；
- `content_sha256` 必须为 64 hex；
- 任一错误必须 `FAILED_INVALID_INPUT / exit1 / passed=false`；
- 不允许 `checks.real_candidates.dataset_id_match=false` 时顶层仍 `passed=true`。

### 2. task / split / candidate 必须逐任务绑定

新增或扩展一个必选 check，例如 `task_candidate_binding`，并纳入顶层 `passed`。

每个 task 必须满足：

```text
task.dataset_id == dataset_manifest.dataset_id
task.sample_id in candidate_index
task.content_hash == candidate_index[task.sample_id].content_sha256
task.split == frozen_split_assignment[task.sample_id]
task.sample_id 不得出现在错误 split pack
```

A/B 同一 test sample 必须满足：

```text
A.content_hash == B.content_hash == candidate.content_sha256
A.sample_id == B.sample_id
A.annotator_slot == "A"
B.annotator_slot == "B"
```

生产 CLI 负例必须覆盖：

- candidate 行 dataset_id 被改为 `ds_attacker_wrong`；
- task sample_id 改为候选集中不存在的 ghost id，并重算 task_hash、重新签名 pack manifest；
- task content_hash 改成与 candidate 不一致，并重算 task_hash、重新签名 pack manifest；
- task split 与 frozen split 不一致，并重算 task_hash、重新签名 pack manifest；
- A/B 同一 sample_id 但 content_hash 不同。

以上全部必须 exit1。

### 3. READY 必须有 deterministic batch_id

READY artifact 必须输出非空 `batch_id`。

建议生成方式：

```text
batch_id = "annbatch_" + sha256(
  dataset_manifest_sha256 + "\n" +
  pack_manifest_sha256 + "\n" +
  real_candidate_export_sha256 + "\n" +
  splits_config_sha256 + "\n" +
  roles_config_sha256 + "\n" +
  governance_config_sha256
)[:16]
```

要求：

- 相同输入重复运行 batch_id 相同；
- 任一输入文件内容变化 batch_id 改变；
- 非 READY 状态可为 null；
- 正向测试必须断言 `batch_id is not None` 和稳定性。

### 4. 双标阈值必须按授权候选总数计算

双标要求：

```text
required_double_label = max(20, ceil(authorized_candidate_count * 0.2))
```

要求：

- 105 个授权候选时要求 21；
- 20 个双标样本必须 exit1；
- 21 个双标样本才可通过此项；
- 同一 sample_id 在 A/B 中 content_hash 不同必须 exit1；
- 修正 evidence 字段拼写，不能保留 `double_label_ample_ids` 这类错误字段作为正式字段。

### 5. group 隔离必须有明确策略

本阶段不实现新聚类，只验证输入中的冻结 group 字段。

要求：

- 明确定义 required group metadata，例如 `session_id`、`conversation_id`、`near_duplicate_group_id`；
- 缺失 required group metadata 时必须 `BLOCKED_INPUT_REQUIRED` 或 `FAILED_INVALID_INPUT`，不得 READY；
- 同一 group 不得跨 development/calibration/test；
- 生产 CLI 负例覆盖缺字段与跨 split group 泄漏。

### 6. 治理时间必须 timezone-aware

要求：

- `annotation_window_start`、`annotation_window_end`、`retention_until` 必须可解析且带 timezone；
- naive datetime 例如 `2026-08-01T00:00:00` 必须 exit1；
- end 必须晚于 start，retention 必须晚于 end。

### 7. 测试不得只证明 helper 路径

必须新增生产 CLI 级别测试或命令证据，至少覆盖：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py \
  --launch-config <tmp>/launch.json \
  --environment production \
  --no-publish \
  --evidence-dir <tmp>/ev
```

测试中可生成 tmp_path fixture，但必须通过正式 CLI/唯一生产主路径进入，不得只调用 `main(... env_override=...)` 作为反例证据。

## 验收标准

### 语法 / 静态检查

```bash
.venv/bin/ruff check scripts/p13_2_real_annotation_launch_readiness.py tests/test_p13_2_real_annotation_launch_readiness.py
git diff --check
```

全部 exit 0。

### 功能验证

必须通过：

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

并在交付报告列出：

- focused pytest 数量；
- full pytest 数量；
- warnings；
- 每条新增生产 CLI 负例的 exit、status、passed、target check；
- READY 正例的 `dataset_id`、`batch_id`、`dataset_manifest_sha256`、`pack_manifest_sha256`、`double_label_actual_count`、`required_double_label`。

### 回归验证

必须保留并证明：

- no-input 正式运行仍 `BLOCKED_INPUT_REQUIRED / exit2`；
- count 伪报、授权缺字段、test blind 泄漏、签名/hash 篡改、空 test pack、split 与候选零交集等已关闭负例不复发；
- P13-2-2-1A 信任链文件未被修改或弱化。

### 交付前质量门禁

交付报告必须由当前工作区实际命令生成：

```bash
shasum -a 256 scripts/p13_2_real_annotation_launch_readiness.py \
  tests/test_p13_2_real_annotation_launch_readiness.py \
  docs/P13-2-evidence/real-annotation-launch-readiness.json \
  docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256
```

报告中的 SHA 不得手写漂移。若正式 evidence 未因本次运行变化，也必须说明原因。

## 交付报告模板

````markdown
# P13-2-2-2A fix-3 交付报告：候选-任务绑定与批次身份闭环

## 结论

## 修改文件清单与 SHA

## 核心修复

## 生产 CLI 负例证据

| 反例 | 命令入口 | exit | status | passed | target check |
| --- | --- | ---: | --- | --- | --- |

## READY 正例证据

```json
{
  "status": "READY_FOR_HUMAN_ANNOTATION",
  "passed": true,
  "exit_code": 0,
  "dataset_id": "...",
  "batch_id": "annbatch_...",
  "double_label_actual_count": 21,
  "required_double_label": 21
}
```

## 验收命令退出码

## 回归保护

## 未覆盖风险
````

## 完成边界

fix-3 通过只表示 readiness 工具能正确判定“是否可以启动真实人工标注”。当前真实人工标注仍未完成，不得进入 P13-2-2-2B 或任何下游模型校准/聚类/前端发布阶段。
