# P13-2-2-1 fix Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- Ruff：PASS。
- 聚焦测试：25 passed。
- 全量回归：249 passed，3 warnings。
- P13-1 behavior probe：PASS。
- P13-2 goldset validator：PASS / READY（fixture）。
- `git diff --check`：PASS。
- `human-annotation-contract-metrics.json` 已存在且为合法 JSON。
- 退化 κ 已修复：全 true、全 false 均返回 `DEGENERATE_KAPPA=-1.0`，validator 有 `kappa_non_degenerate` 检查。
- stage policy 已成为 validator 的真实输入；true、缺失、错误类型均可使 `calibration_not_allowed=false`。
- 零真实候选已从 mutation 分母移出，独立验证为 exit 2/BLOCKED。

## 阻断问题

### P0-1：importer mutation 的 target check 仍为伪造字段

位置：`scripts/p13_2_annotation_mutation_gate.py` 的 `run_importer_mutation()`。

问题：函数没有读取 importer 的报告检查项。源码注释明确说明 `target_check field is used for reporting only`；实际只判断 `returncode == 1`，随后无条件写入：

```python
"check_exists": True,
"target_passed": not detected,
```

因此下列 6 条 evidence 中的 `check_exists=true` 和 `target_passed=false` 不是子 CLI 产出的观测，而是由退出码推导出来的：

- `same_id_different_content_conflict`
- `nonexistent_dataset_id`
- `nonexistent_sample_id`
- `unknown_schema_field`
- `llm_copy_as_gold_blind`
- 以及所有经 `run_importer_mutation()` 增加的后续案例

证据：importer 的真实报告只有 `status`、`passed`、`error_count`、`per_item_errors`，不存在名为 `import_conflict` 或 `import_reject` 的 checks 字典。

影响：mutation gate 仍可能让“因无关错误 exit 1”的 importer 负例冒充目标规则被捕获，`26/26 PASS` 仍是假阳性风险。这与原任务书及 fix 指令要求的“target check 真实存在且 false”直接冲突。

验收要求：importer 必须输出结构化 `checks`，mutation runner 必须从同次 `--out` 报告读取指定 target；不得从退出码、mutation 名称或预设常量生成 `check_exists/target_passed`。

### P1-1：交付报告对 contract metrics 的描述与实际文件不一致

交付报告称：`human-annotation-contract-metrics.json`“记录每条 mutation 的 exit、target check、target passed、detected，以及独立 readiness invariant”。

实际该文件是 fixture validator 输出，只包含人工标注 checks 和计数；逐条 mutation 与 readiness invariant 位于 `human-annotation-mutation-gate.json`。

影响：同次机器证据虽已存在，但报告仍有确定性 artifact/内容漂移，无法按报告定位数据。

验收要求：要么建立真正的聚合 contract metrics 并包含声明字段，要么修正报告，明确两个 JSON 的职责；最终交付聚合器需验证二者一致性。

## 问题统计归类

- 验证脚本假阳性 / 退出码推导目标行为：再次复发，P0。
- 交付报告与机器 artifact 漂移：再次复发，P1。

## 复验要求

只修复 importer 结构化 checks、mutation 真实读取和证据职责一致性。已通过的退化 κ、stage policy、readiness invariant 不得回退；真实人工标签仍不得伪造。
