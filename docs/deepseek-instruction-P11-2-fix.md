# DeepSeek 返修指令：P11-2 发布候选暂存计划

## 任务目标

只修正 `docs/release-candidate-P11-2-staging-plan-20260628.md` 的工作树快照计数和暂存分组统计口径。不要修改生产代码、测试代码或其他文档。

## 允许修改范围

- `docs/release-candidate-P11-2-staging-plan-20260628.md`

## 禁止修改范围

- 不修改 `signal_miner/` 下任何生产代码。
- 不修改 `tests/` 下任何测试代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 返修要求

### 1. 重新读取最新工作树状态

返修时重新运行：

```bash
git status --short
```

并用命令结果更新文档中的：

- modified 数。
- untracked 数。
- total 数。
- 未跟踪条目分布。

不要复用旧的 `modified=9, untracked=55, total=64`。注意：P11-2 初验失败报告和本返修指令已经新增文档条目，所以最新计数会比初验时变化。

### 2. 修正暂存分组摘要口径

摘要表必须能回算到最新 `git status --short`：

- 每个 status 条目只能有一个主归属分组。
- 如果某些文档既在“文档归档”中，又在“可排除项”中出现，必须明确“可排除项是文档归档组中的人工处理子集，不参与总数重复累加”。
- 表格总计必须与最新 `modified + untracked` 一致。

建议改法：

- 将 G7 改成“G5 文档归档中的人工处理子集”，不参与总计。
- 或者从 G5 计数中扣除 G7 条目，并把 G7 作为独立主分组。

任选一种，但必须保证总数闭环。

### 3. 保留已正确内容

保留以下内容：

- P9/P10 代码与测试分组。
- 不执行 git 操作的声明。
- 质量门禁命令与结果。
- 截图目录需人工确认的提示。

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
- 暂存分组摘要如何与该计数闭合。
- 是否仍有人工确认项。
- 验收命令结果。
