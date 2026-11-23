# DeepSeek 二次返修指令：P11-3 发布冻结前最终检查单

## 任务目标

彻底修复 P11-3 的唯一阻断项：`git diff --check` 报告的 `tests/test_prd_routes.py` 文件末尾多余空行，并同步更新冻结检查单。

## 允许修改范围

- `tests/test_prd_routes.py`
- `docs/release-candidate-P11-3-freeze-checklist-20260628.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改除 `tests/test_prd_routes.py` 之外的测试文件。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 必修项

1. 删除 `tests/test_prd_routes.py` 末尾多余空行。
   - 修复后文件最后一行必须是 `assert response.status_code == 404`。
   - 不改变任何测试逻辑。

2. 运行：

```bash
git diff --check
```

必须无输出且退出码为 0。

3. 重新运行：

```bash
git status --short
git diff --stat
```

并更新 `docs/release-candidate-P11-3-freeze-checklist-20260628.md` 中的：

- modified/untracked/total。
- 未跟踪分布。
- `git diff --stat`。
- `git diff --check` 状态。
- 遗留风险表，移除 trailing newline 风险。

注意：P11-3 返修复验失败报告和本二次返修指令会新增文档条目，因此最新计数会变化，必须以返修时重新运行的命令为准。

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

- `tests/test_prd_routes.py` 文件末尾已如何修正。
- `git diff --check` 的实际结果。
- 最新 `git status` 与 `git diff --stat`。
- 冻结检查单更新了哪些字段。
- 其余复验命令结果。
