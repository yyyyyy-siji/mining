# P13-2-2-2A fix-2 Commander 复验报告

验收日期：2026-07-15

结论：不通过，需要执行 fix-3。常规测试为绿，但生产 CLI 仍存在 READY 假绿。

## 已通过项

| 检查 | 结果 |
| --- | --- |
| `--verify-evidence` | PASS / exit 0 |
| focused ruff | PASS / exit 0 |
| `git diff --check` | PASS / exit 0 |
| 聚焦 pytest | 35 passed |
| 全量 pytest | 363 passed, 3 warnings |
| 正式 no-input evidence | `BLOCKED_INPUT_REQUIRED / exit2`，sidecar SHA 匹配 |

实际 SHA：

| 文件 | SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `9d38e828bfda1806bfc4e2f89d20c7185576bb2a2b3cea697820c5365069bbdc` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `24155c73df23def4bb6feaae8b4235576901ede78ff8ede4efd8d3d8542ddac8` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `d2f4347f6b61831c08559ddd9e5901ea54de12c62668ae3baf84b1af74ea5053` |

## 阻断问题

### P0-1：候选行 dataset_id 错误仍进入 READY

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:275`

问题：

`_check_real_candidates()` 只读取导出顶层 `dataset_id`，没有逐行校验 `candidates[*].dataset_id`。实际代码为：

```python
candidate_ds_id = data.get("dataset_id") or data.get("dataset_id") or ""
```

因此只要导出文件没有顶层 `dataset_id`，逐行候选即使混入错误 dataset，也不会阻断 READY。

Commander 生产 CLI 反例：

```text
受控正例 fixture 生成完整 signed packs + launch config
将 real-candidate-export.json 第一条 candidates[0].dataset_id 改为 ds_attacker_wrong
使用 ANNOTATION_PACK_SIGNING_KEY 走正式 CLI:
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py \
  --launch-config <tmp>/launch.json \
  --environment production \
  --no-publish \
  --evidence-dir <tmp>/ev
```

实际结果：

```text
P13-2-2-2A readiness: READY_FOR_HUMAN_ANNOTATION
passed: True
exit_code: 0
```

影响：

真实授权候选集身份可被混入错误 dataset，readiness 仍宣告可启动人工标注。这是数据来源信任链的核心假绿。

验收要求：

- 每条 candidate 的 `dataset_id` 必须存在、唯一一致，并等于 dataset manifest 的 `dataset_id`。
- 任一行 dataset_id 缺失、混杂、错误，必须 `FAILED_INVALID_INPUT / exit1 / passed=false`。
- `checks.real_candidates.dataset_id_match=false` 不得与顶层 `passed=true` 同时出现。

### P0-2：READY artifact 的 batch_id 仍为 null

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1182`

问题：

READY 输出中 `batch_id` 被硬编码为 `None`。

Commander 生产 CLI 正例证据：

```json
{
  "exit_code": 0,
  "status": "READY_FOR_HUMAN_ANNOTATION",
  "passed": true,
  "dataset_id": "ds_prod_20260714",
  "batch_id": null,
  "double_label_actual_count": 30
}
```

影响：

人工标注启动批次没有稳定身份，后续数据生命周期、审计、重跑去重、旧数据处理和 evidence 追溯都会失去锚点。

验收要求：

- READY 时 `batch_id` 必须为非空、稳定、可重算的批次身份。
- 建议从 dataset manifest SHA、pack manifest SHA、候选 export SHA、splits SHA、roles/governance SHA 生成 deterministic batch id。
- 正向测试必须断言 `batch_id != null` 且相同输入重复运行 batch_id 相同。

### P0-3：任务包与授权候选缺少逐任务绑定门禁

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1071`
- `scripts/p13_2_real_annotation_launch_readiness.py:1095`

问题：

当前 `_check_task_identity()` 只验证 task 自身字段能重算出 `task_hash`；`_check_split_isolation()` 主要验证 split ID 集合与候选 ID 集合关系。缺少“每个 task 必须绑定到授权 candidate 行”的统一索引校验：

- `task.dataset_id == dataset_manifest.dataset_id == candidate.dataset_id`
- `task.sample_id` 在候选集中存在且唯一
- `task.content_hash == candidate.content_sha256`
- `task.split` 与冻结 split assignment 一致
- A/B 同一 sample 的 content_hash 必须一致

影响：

当前 pack verifier 可以拦住部分重签名篡改，但 readiness 自身仍没有形成候选、split、task 三者的闭环契约。后续代码变动或 manifest 生成器行为变化时，此类假绿会再次出现。

验收要求：

- 构建 canonical authorized candidate index，并由一个必选 check 参与 `passed`。
- 新增生产 CLI 负例：task sample_id/content_hash/split 与候选或 split 不一致，即使 task_hash 重算且 pack manifest 重新签名，也必须 exit1。

## P1 问题

### P1-1：双标阈值按 test unique 计算，不按授权候选总数计算

位置：

- `scripts/p13_2_real_annotation_launch_readiness.py:1006`
- `tests/test_p13_2_real_annotation_launch_readiness.py:300`

问题：

当前 required 使用 `total_unique_test`，不是授权候选总数。正向测试只断言 `double_label_actual_count >= 1`，而任务书要求 `max(20, ceil(n_authorized_candidates * 20%))`。

验收要求：

- 105 个授权候选时，双标要求必须为 21。
- 只有 20 个 A/B 共同样本时必须 exit1。
- 同一 sample_id 在 A/B 中 content_hash 不同必须 exit1。

### P1-2：报告 SHA 漂移

交付报告记录的测试 SHA 为：

```text
c12fe343280e2de02a4644f2978fe785fb8f7c62fcb88a6e2084a2db93fd9e97
```

实际测试文件 SHA 为：

```text
24155c73df23def4bb6feaae8b4235576901ede78ff8ede4efd8d3d8542ddac8
```

验收要求：

- 交付报告必须由当前工作区实际 `shasum -a 256` 生成。
- 报告中的所有 SHA 必须与当前文件一致。

### P1-3：近重复 / session / conversation group 隔离仍未证明

fix-2 任务书要求“没有必要字段时不得假装近重复门禁已通过，应 BLOCKED 或 INVALID”。当前正向 fixture 没有提供 group 字段，仍 READY。

验收要求：

- 明确定义 required group metadata。
- 缺字段时 BLOCKED 或 INVALID；跨 split group 泄漏时 exit1。
- 本阶段只需验证冻结 group 字段，不要求实现新聚类算法。

### P1-4：治理时间未要求 timezone-aware

当前使用 `datetime.fromisoformat()` 解析即可通过部分无时区时间。人工标注窗口、retention 均应要求带时区 datetime。

验收要求：

- 无时区 timestamp 必须 exit1。
- 测试覆盖 `2026-08-01T00:00:00` 这类 naive datetime。

## 复验要求

fix-3 交付后必须至少提供：

- 新交付报告；
- 当前脚本、测试、正式 evidence SHA；
- 生产 CLI 反例证据，不得只用测试 helper；
- focused pytest、full pytest、ruff、`--verify-evidence`、`git diff --check` 退出码；
- READY 正例 JSON 摘要，必须包含非空 `batch_id`。

## 问题统计归类

- 验证脚本假阳性 / 关键 check 未参与 `passed`：新增 1 次 P0。
- 报告 / SHA 漂移：新增 1 次 P1。
- 测试覆盖不足导致契约未被断言：新增 1 次 P1。

结论：P13-2-2-2A fix-2 不通过。不得进入 P13-2-2-2B、主动学习评测、置信度拟合、P13-3 或前端概率发布。
