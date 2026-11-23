# DeepSeek 二次返修指令：P11-2 发布候选暂存计划

## 任务目标

只修正 `docs/release-candidate-P11-2-staging-plan-20260628.md` 的 G5 文档分类表，使它与最新 `git status --short` 的 docs 条目数闭合。

## 允许修改范围

- `docs/release-candidate-P11-2-staging-plan-20260628.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 返修要求

### 1. 重新读取最新状态

二次返修前先运行：

```bash
git status --short
```

注意：本次复验失败报告和本二次返修指令会新增 2 个 docs 条目，因此最新 docs 数会变化。不要复用旧的 `docs=55`，以返修时实际输出为准。

### 2. 修正 G5 文档分类表

当前问题是 G5 总数写 55，但分类表只覆盖 52 个条目。请让 G5 分类表各行相加等于最新 docs 状态条目数。

至少需要覆盖：

- P9 final-pass 与 P9 总结。
- P9 交付/验收范围报告。
- P9 指令文档。
- P10 final-pass 与 P10 总结。
- P10 交付/验收范围报告。
- P10 指令文档。
- P11 验收报告，包括 P11-1 和 P11-2 的失败/最终验收报告。
- P11 指令文档，包括 P11-1/P11-2 release 指令和 fix 指令。
- P11 release-candidate 文档。
- `docs/P9-2-screenshots/` 目录作为 1 个 docs 状态条目。

### 3. 保持 G6/G7 为子项

如果 G6 截图和 G7 可排除项已经包含在 G5 总数中，必须明确它们是 G5 的人工处理子项，不参与总数重复累加。

## 验收命令

返修后运行并记录：

```bash
git status --short
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

## 交付报告

提交返修说明，列出：

- 最新 `git status` 计数。
- G5 分类表各行数量及合计。
- G6/G7 是否为 G5 子项。
- 验收命令结果。
