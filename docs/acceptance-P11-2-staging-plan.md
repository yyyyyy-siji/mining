# P11-2 验收报告：发布候选暂存计划

验收日期：2026-06-28

结论：不通过，需要返修。

## 已通过项

质量门禁本地复验通过：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

结果：18 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：43 passed，1 个 `StarletteDeprecationWarning`，非阻塞。

## 阻断问题

### P1-1：工作树快照计数不符合验收时点代码事实

位置：`docs/release-candidate-P11-2-staging-plan-20260628.md:9`

问题：

文档记录：

```text
modified = 9
untracked = 55
total = 64 条目
```

但验收时点实际 `git status --short` 统计为：

```text
modified=9
untracked=56
total=65
```

未跟踪条目分布实际为：

```text
53 docs
1 signal_miner
2 tests
```

影响：

P11-2 的交付物是发布候选暂存计划。工作树快照不准会直接影响后续人工 `git add` 范围判断，属于发布准备阶段的核心事实错误。

验收要求：

返修时必须重新运行 `git status --short`，不要复用旧计数。注意：本失败验收报告和返修指令会新增文档条目，因此返修时的最新计数会继续变化；文档必须以返修时重新运行的结果为准。

### P1-2：暂存分组摘要与工作树快照存在口径冲突

位置：`docs/release-candidate-P11-2-staging-plan-20260628.md:63` 至 `docs/release-candidate-P11-2-staging-plan-20260628.md:74`

问题：

暂存计划的摘要表与工作树快照没有形成可核对的闭环。当前文档同时出现：

- G5 文档归档 52 条。
- G6 截图资产 1 目录。
- G7 可排除项 2 条。
- 工作树快照写 untracked=55。

但验收时点实际 `??` 条目为 56，其中 docs 相关状态条目为 53。若 G7 的 2 条已包含在 G5 的 52 个文档条目中，文档需要明确“G7 是从 G5 中单独挑出的处理建议，不是额外计数”；若不包含，则总数无法和 `git status` 对齐。

影响：

发布计划中同一文件可能被重复计数或漏计，影响暂存分组准确性。

验收要求：

修正摘要表口径，必须满足：

- 每个 `git status --short` 条目在计划中有且只有一个主归属分组。
- 如需在“可排除项”重复列出某些文档，必须明确它是从文档归档组中抽出的人工处理子集，不参与总数累加。
- 表格总数必须能回算到最新 `git status` 的 modified/untracked/total。

## 非阻断观察项

P9/P10 代码与测试的分组思路基本正确；问题集中在 P11-2 文档的快照计数和摘要口径。

## 复验要求

返修后复验：

```bash
git status --short
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```
