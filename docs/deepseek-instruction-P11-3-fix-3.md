# DeepSeek 三次返修指令：P11-3 发布冻结前最终检查单

## 任务目标

只修正 `docs/release-candidate-P11-3-freeze-checklist-20260628.md` 中残留的旧 `git diff --check` warning 和最新工作树计数。

## 允许修改范围

- `docs/release-candidate-P11-3-freeze-checklist-20260628.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 返修要求

1. 重新运行：

```bash
git status --short
git diff --stat
git diff --check
```

2. 更新冻结检查单：

- 工作树 modified/untracked/total 使用最新 `git status`。
- 未跟踪分布使用最新统计。
- `git diff --stat` 使用最新输出。
- 摘要区和验证结果区的 `git diff --check` 均必须写为通过、exit=0、无输出。
- 文档中不能再出现 `new blank line at EOF` 或 `tests/test_prd_routes.py:366`。

3. 不要修改 `tests/test_prd_routes.py`；代码侧已经修复。

## 复验命令

返修后运行并记录：

```bash
git status --short
git diff --stat
git diff --check
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 交付报告

提交返修说明，列出：

- 删除了哪些旧 warning 表述。
- 最新 `git status` 与 `git diff --stat`。
- `git diff --check` 的实际结果。
- 其余复验命令结果。
