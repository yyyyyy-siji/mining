# DeepSeek 返修指令：P11-1 发布候选变更清单与工作树整理

## 任务目标

只修正 `docs/release-candidate-P11-1-change-inventory-20260627.md` 的工作树计数和未跟踪文件表述。不要修改生产代码、测试代码或其他验收文档。

## 允许修改范围

- `docs/release-candidate-P11-1-change-inventory-20260627.md`

## 禁止修改范围

- 不修改 `signal_miner/` 下任何生产代码。
- 不修改 `tests/` 下任何测试代码。
- 不移动、删除或重命名已有 P9/P10/P11 文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 返修项

### 1. 修正工作树概览计数

当前事实：

```text
modified=9
untracked=51
```

未跟踪条目分布：

```text
48 docs
1 signal_miner
2 tests
```

将文档中的“8 个修改文件（` M`）和 48 个未跟踪条目”修正为以上事实。

### 2. 修正发布候选建议中的未跟踪文件表述

当前 `??` 包含未跟踪生产代码目录和测试文件：

```text
?? signal_miner/utils/
?? tests/test_connector_response_models.py
?? tests/test_source_clickthrough_contract.py
```

请明确说明它们属于 P9 预期范围，但发布提交时仍需要人工确认纳入。不要再写“未发现未跟踪的生产代码或测试文件”。

### 3. 修正变更分组摘要的统计口径

如果保留当前按逻辑归属统计的表格，必须明确说明：

- 该表不是 `git status --short` 条目数。
- `signal_miner/utils/` 在 git status 中显示为 1 个目录条目，但逻辑上包含 `url_templates.py` 与 `__init__.py` 两个文件。

也可以改成按 `git status --short` 条目统计，只要与当前事实一致。

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

- 修正了哪些文档行。
- 新的 `git status` 计数。
- 未跟踪生产/测试文件如何归类。
- 验收命令结果。
