# P11-2 返修复验报告：发布候选暂存计划

验收日期：2026-06-28

结论：不通过，需要二次返修。

## 已通过项

工作树快照主计数已修正并与验收时点一致：

```text
modified=9
untracked=58
total=67
```

未跟踪分布也已匹配：

```text
55 docs
1 signal_miner
2 tests
```

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

### P1-1：G5 文档分类表仍未与 55 个 docs 条目闭合

位置：`docs/release-candidate-P11-2-staging-plan-20260628.md:88` 至 `docs/release-candidate-P11-2-staging-plan-20260628.md:101`

问题：

文档主快照和摘要表已写明 G5 文档归档为 55 个 docs 条目，但 G5 分类表各行相加只覆盖 52 个文件/目录条目。当前实际 `docs/` 顶层文件为 54 个，另有 `docs/P9-2-screenshots/` 目录 1 个，共 55 个 docs 状态条目。

遗漏点包括：

- `docs/acceptance-P11-2-staging-plan.md`
- `docs/deepseek-instruction-P11-2-fix.md`

同时，`docs/deepseek-instruction-P11-*.md` 当前实际为 4 个，但文档第 99 行写的是 3 个。

证据：

```bash
find docs -maxdepth 1 -type f -name 'deepseek-instruction-P11-*-*.md' | wc -l
```

实际结果：4。

```bash
find docs -maxdepth 1 -type f | wc -l
find docs -maxdepth 1 -type d -name 'P9-2-screenshots' | wc -l
```

实际结果：54 个顶层文件 + 1 个截图目录。

影响：

P11-2 是发布候选暂存计划。G5 文档归档组如果分类不闭合，后续人工暂存文档时仍可能漏掉 P11-2 失败验收报告或返修指令。

验收要求：

修正 G5 分类表，使其能清晰回算到 55 个 docs 状态条目。建议至少调整：

- P11 验收报告行覆盖 `acceptance-P11-1-*.md` 与 `acceptance-P11-2-*.md`，数量应为 3。
- P11 指令文档行数量改为 4，覆盖 P11-1 release、P11-1 fix、P11-2 release、P11-2 fix。
- 保留 P11 发布候选清单/暂存计划 2 个文件。
- 明确 `docs/P9-2-screenshots/` 目录作为 1 个 docs 状态条目进入 G5，同时可在 G6 作为人工确认子项重复展示但不重复计数。

修正后 G5 分类表合计必须等于 55。

## 非阻断观察项

P9/P10 代码与测试分组、G1-G4 运行时必需部分、G6/G7 子项口径整体可接受。问题集中在 G5 文档分类明细的计数闭合。

## 复验要求

二次返修后复验：

```bash
git status --short
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```
