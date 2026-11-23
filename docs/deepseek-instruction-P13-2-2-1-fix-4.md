# DeepSeek 执行指令：P13-2-2-1 fix-4 冻结 task hash 消费端闭环

## 任务目标

让 importer 独立重算冻结 task hash，阻断 pack/task fixture 整体翻转后继续沿用旧 hash 的来源伪造。补齐 pack 顶层 fixture 缺失/类型错误门禁。

## 背景 / 当前问题

`compute_task_hash()` 已包含 fixture，但 importer 只比较 annotation 与 task 文件中携带的同一个 hash，没有独立重算。Commander 已证明：把某个 pack 顶层及全部 task 的 fixture 一起改为 false、保留旧 hashes，普通 ID 的 `fixture=false` annotation 仍可 exit 0 并写入真实标签。

## 允许修改范围

- `scripts/p13_2_import_human_annotations.py`
- `scripts/p13_2_annotation_mutation_gate.py`
- `tests/test_p13_2_human_annotation_contract.py`
- `signal_miner/evaluation/human_annotation.py` 仅限 task hash 辅助接口必要调整
- 本阶段 evidence、操作说明和 fix-4 交付报告

## 禁止修改范围

- 生产 pipeline、LLM、Embedding、去重、聚类、数据库、API、前端
- ID/路径/文件名启发式
- 用“pack fixture 与 task fixture 相等”代替 hash 重算
- 重新生成 hash 来掩盖 importer 不验证的问题
- 真实人工标签、校准和 P13-2-2-2

## 实现要求

### 1. Importer 独立重算 task hash

对每条命中的 task，使用正式 `compute_task_hash()` 和 task 自身规范字段重算：

```python
expected = compute_task_hash(
    task["dataset_id"],
    task["sample_id"],
    task["annotator_slot"],
    task["content_hash"],
    fixture=task["fixture"],
)
```

必须同时满足：

- `task.task_hash == expected`
- `annotation.task_hash == expected`
- annotation 的 dataset/sample/slot/content/fixture 与 task 相应字段一致

任一不一致必须 exit 1，并进入明确的 `task_integrity` check；若沿用 `dataset_identity`，须在 observations 中给出 `task_hash_recompute_mismatch`。

### 2. Pack fixture schema完整性

- pack 顶层 `fixture` 必须存在且类型严格为 bool。
- 每条 task 的 `fixture` 必须存在且为 bool。
- pack fixture 必须等于每条 task fixture。
- 缺失、字符串、数字、null、冲突均须正式 CLI exit 1。

### 3. 必须增加的正式 mutation

至少覆盖：

1. 整个 pack 顶层及全部 task fixture 从 true 翻为 false，保留旧 task hashes。
2. 单条 task fixture 翻转，pack fixture同步翻转或构造单任务 pack，保留旧 hash。
3. pack 顶层 fixture 缺失。
4. pack 顶层 fixture 为字符串。
5. task hash 任意改写但 annotation 同步为同一个错误 hash。

每条必须运行正式 importer CLI，并满足：

- child exit 1
- 真实 target check 存在
- target passed=false
- store before/after SHA一致

### 4. Commander 反例回归

将以下流程固化为测试，不得简化为函数单测：

- 复制真实 fixture task dir 到临时目录。
- 修改目标 pack 顶层及全部 task `fixture=false`。
- 不更新 task hashes。
- annotation 使用普通 ID、`fixture=false` 和旧 task hash。
- 调用正式 importer CLI。

预期：exit 1，`task_integrity=false`（或 `dataset_identity=false` 且有重算错误码），`fixture_provenance`不得成为唯一保护，store不变。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/human-annotation-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/human-annotation-mutation-gate.json >/dev/null
git diff --check
```

通过条件：

- Commander 整包翻转+旧 hash 反例必须 exit 1。
- task hash 必须在 importer 消费端独立复算。
- pack/task/annotation 三层 fixture 与 hash形成一致性闭环。
- 新 mutation 从同次正式 CLI 报告读取 target，不从退出码推导。
- fixture 工具链仍为 `FIXTURE_PASS`；真实计数仍为0。
- 既有 importer meta-negative、普通 ID/UUID、退化 κ、stage policy、readiness invariant 不回退。

## 交付前质量门禁

- 交付报告列出 expected/task/annotation hash 的实际值和比较结果。
- Commander 反例提供 exit、target check、错误码、store before/after SHA。
- evidence JSON 顶层 passed 必须包含新增 mutation。
- 测试使用临时目录，不污染冻结 artifacts。

## 交付报告模板

```markdown
# P13-2-2-1 fix-4 交付报告

## 结论
## 修改文件
## Task hash 三方一致性契约
## Pack fixture schema契约
## Commander整包翻转反例
## 新增mutation与store SHA
## 全量回归和状态不变量
## 外部信任根剩余风险
```

交付文件：`docs/acceptance-P13-2-2-1-delivery-fix-4-20260713.md`。

## 完成边界

本 fix-4 通过只说明本地冻结 task 的消费端完整性闭环可信。真实候选为0时，P13-2-2-2、P13-2-3、P13-2-4继续冻结。
