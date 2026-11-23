# DeepSeek 执行指令：P13-2-2-1 fix-3 fixture 来源强绑定

## 任务目标

修复 fixture annotation 通过重命名 ID 并设置 `fixture=false` 冒充真实人工标签的 P0 漏洞。来源身份必须绑定冻结 task pack 的结构化真值，不得依赖名称关键词。

## 背景 / 当前问题

当前 task pack 顶层和每条 task 都有 `fixture=true`，但 importer 只检查 annotation ID 是否包含 `fixann/test/mock/...`。Commander 已证明：将 fixture annotation 改为普通 ID 且 `fixture=false` 后，正式 importer exit 0 并把它存为真实标签。

## 允许修改范围

- `scripts/p13_2_import_human_annotations.py`
- `scripts/p13_2_annotation_mutation_gate.py`
- `tests/test_p13_2_human_annotation_contract.py`
- 若 task hash 契约必须纳入 fixture 字段，可修改 P13-2 task 生成/验证脚本及 fixture artifacts
- 本阶段 evidence、操作说明与 fix-3 交付报告

## 禁止修改范围

- 生产 pipeline、LLM、Embedding、去重、聚类、数据库、API、前端
- 用扩大 `_FIXTURE_ID_TAGS` 列表作为修复
- 根据 ID、文件名、路径或文本内容推导 fixture/real
- 伪造真实授权数据或人工标签
- P13-2-2-2、校准及后续阶段

## 实现要求

### 1. 结构化 provenance 单一真源

- Importer 从命中的冻结 task 读取 `task.fixture`。
- `annotation.fixture` 必须与 `task.fixture` 严格相等，否则 `fixture_provenance=false`。
- task pack 顶层 `fixture` 必须与每条 task 的 `fixture` 一致。
- `fixture` 缺失、非 bool、包/任务冲突、annotation/task 冲突均须 exit 1。
- 若任务身份 hash 当前未覆盖 fixture，必须将 fixture 纳入冻结 task hash 的规范化输入，并同步生成器、validator 和 fixture artifact；不得留下可翻转但 hash 不变的来源字段。

### 2. 删除命名启发式作为安全边界

- `_FIXTURE_ID_TAGS` 可以仅作为非安全提示，但不得决定真实/fixture 身份。
- 普通 ID、随机 UUID、`human_*`、不含任何关键词的 ID 都必须被结构化 fixture 对比阻断。
- 真实任务即使 ID 含 `test` 等普通词，也不得仅因名称被判 fixture；身份只能来自冻结结构化字段。

### 3. 正式 mutation

至少增加以下正式 CLI mutation，并指定真实 `fixture_provenance` target：

1. fixture task + annotation普通 ID + `fixture=false`。
2. fixture task + annotation随机 UUID + `fixture=false`。
3. task逐条 fixture 与包顶层 fixture 冲突。
4. task fixture 缺失。
5. task fixture 类型为字符串。
6. 若 hash 覆盖 fixture：翻转 task fixture 但保留旧 task hash。

每条必须满足：`child_exit=1`、target check真实存在、`target_passed=false`。不得由退出码推导。

### 4. Commander 反例必须转为回归测试

使用正式 importer 证明以下输入失败：

```python
ann = fixture_annotations[0]
ann["annotation_id"] = "ann_human_20260713_0001"
ann["fixture"] = False
```

预期：

```json
{
  "status": "FAIL_VALIDATION",
  "passed": false,
  "checks": {
    "fixture_provenance": {"passed": false}
  }
}
```

store 必须不存在或保持原 SHA/内容不变。

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

- Commander 普通 ID 绕过反例变为 exit 1、`fixture_provenance=false`。
- fixture/real 来源由冻结 task 结构化字段决定，不由 ID 决定。
- 所有新增 provenance mutation 读取同次 CLI target check。
- fixture 正常工具链仍为 `FIXTURE_PASS`。
- 真实候选仍为 0；`human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。
- 既有 5 类 target 元负例、退化 κ、stage policy 和 exit 2 readiness invariant 不回退。

## 回归验证

- 清洁 fixture annotation 可正常导入，但始终保留 `fixture=true`。
- 真实 task + `fixture=false` 是允许路径；必须使用测试构造的冻结真实 task，不得伪装项目当前真实数据已存在。
- annotation ID 改名不影响 provenance 判定。
- 导入失败不修改 store。

## 交付前质量门禁

- 交付报告必须给出 Commander 普通 ID 反例的正式 CLI JSON 和 store before/after SHA。
- 报告数值与同次 evidence JSON 对齐。
- 每个关键 check 参与顶层 passed。
- 所有测试和 mutation 使用临时目录，不污染冻结 artifacts。

## 交付报告模板

```markdown
# P13-2-2-1 fix-3 交付报告

## 结论
## 修改文件
## Fixture provenance 单一真源
## Task hash / pack一致性契约
## Commander普通ID反例
## 新增mutation与target证据
## Store SHA守恒
## 全量回归与状态不变量
## 未覆盖风险
```

交付文件：`docs/acceptance-P13-2-2-1-delivery-fix-3-20260713.md`。

## 完成边界

本 fix-3 通过仍只代表 P13-2-2-1 工具可信。真实授权候选为0时，P13-2-2-2、P13-2-3、P13-2-4继续冻结。
