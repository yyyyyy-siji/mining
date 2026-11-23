# DeepSeek 执行指令：P13-2-2-1 fix-2 importer target-check 真值化

## 任务目标

消除 importer mutation 通过退出码伪造 target check 的假阳性，并修正 contract metrics 与交付报告的职责漂移。本次不得扩展到 P13-2-2-2。

## 背景 / 当前问题

`run_importer_mutation()` 当前没有读取 importer 的结构化检查结果，而是用 `returncode == 1` 推导：

```python
"check_exists": True
"target_passed": not detected
```

这不满足“指定 target check 来自正式 CLI 同次报告且为 false”的硬契约。一个无关错误也能让 mutation 假绿。

## 允许修改范围

- `scripts/p13_2_import_human_annotations.py`
- `scripts/p13_2_annotation_mutation_gate.py`
- `tests/test_p13_2_human_annotation_contract.py`
- `docs/P13-2-evidence/` 的本阶段机器证据
- P13-2-2-1 fix-2 交付报告与必要操作说明

## 禁止修改范围

- 生产 pipeline、LLM、Embedding、去重、聚类、数据库、API、前端
- 已通过的退化 κ 和 stage-policy 行为
- P13-1、P13-2-1 契约
- 真实授权数据、真实人工标签、校准和后续阶段

## 实现要求

### 1. Importer 输出真实结构化 checks

`--out` 报告必须包含 `checks` 对象。至少为当前 importer mutation 提供可区分目标，例如：

- `schema_strict`
- `task_exists`
- `dataset_identity`
- `annotation_id_conflict`
- `fixture_provenance` 或能明确阻断 LLM/fixture 冒充真实标签的等价目标

每个 check 必须包含：

```json
{
  "passed": false,
  "observations": {
    "error_codes": ["..."]
  }
}
```

顶层 `passed` 必须由所有适用 checks 复算。不能只把所有错误合并成一个 exit 1。

### 2. Mutation runner 只读取同次真实报告

`run_importer_mutation()` 必须：

1. 读取本次临时 `import_report.json`。
2. 在 `checks[target_check]` 中查找目标。
3. 仅当 `child_exit==1`、目标真实存在、`target.passed is false` 时 detected=true。
4. 报告缺失/损坏、目标缺失、目标仍 true、exit 0/2/其他时 detected=false。

禁止：

- 硬编码 `check_exists=True`。
- 用退出码反推 `target_passed`。
- 用错误字符串包含关系在 mutation runner 内临时构造 check。
- mutation 结束后覆盖 detected。

### 3. 防止“无关错误也能通过”

每条 importer mutation 必须只断言与目标规则对应的 check。新增元负例证明：

- 子进程 exit 1，但指定 target check=true → gate FAIL。
- 子进程 exit 1，但指定 target check缺失 → gate FAIL。
- 子进程 exit 1，仅另一个无关 check=false → gate FAIL。
- 报告损坏/缺失 → gate FAIL。

### 4. 证据职责一致

二选一并固定：

- 方案 A：`human-annotation-contract-metrics.json` 成为聚合证据，包含 validator、mutation、readiness invariant；或
- 方案 B：它只保留 validator 结果，但交付报告必须明确 mutation 明细只在 `human-annotation-mutation-gate.json`，并增加机器一致性检查。

无论选择哪种，交付报告不得声称某文件包含实际不存在的字段。机器聚合门禁需检查所声明路径和关键字段。

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

额外机器断言：

```bash
rg -n 'target_check field is used for reporting only|"check_exists": True|"target_passed": not detected' scripts/p13_2_annotation_mutation_gate.py
```

上述命令必须无命中。所有 importer mutation 的 target check 必须能在其同次临时 importer 报告中定位。

## 回归验证

- 全 true / 全 false κ 继续非 READY。
- calibration policy=true/缺失/类型错误继续 exit 1 且目标 false。
- 零真实候选继续独立 exit 2/BLOCKED，不计 mutation 分母。
- fixture 为 `FIXTURE_PASS`；`human_verified_count=0`；`human_labels_complete=false`；`calibration_allowed=false`。

## 交付前质量门禁

- 每个 child command 检查真实 exit status。
- 每个关键 JSON 字段参与顶层 passed。
- Markdown 数值与同次 JSON 对齐。
- 测试使用临时目录，不污染冻结 evidence。
- 禁止把“单元测试全绿”描述为真实人工数据 READY。

## 交付报告模板

```markdown
# P13-2-2-1 fix-2 交付报告

## 结论
## 修改文件
## Importer checks 契约表
## Mutation target 真实读取证据
## 四类元负例
## 退化 κ / stage policy / readiness invariant 回归
## Evidence 文件职责与一致性
## 验收命令及真实退出码
## 状态不变量与未覆盖风险
```

交付文件：`docs/acceptance-P13-2-2-1-delivery-fix-2-20260713.md`。

## 完成边界

本 fix-2 通过也只代表 P13-2-2-1 工具可信。真实候选仍为 0 时，P13-2-2-2、P13-2-3、P13-2-4继续冻结。
