# DeepSeek 返修指令：P11-3 发布冻结前最终检查单

## 任务目标

修复 P11-3 冻结检查阻断项：清理 `git diff --check` 报告的 EOF 多余空行，并更新冻结检查单为最新工作树状态。

## 允许修改范围

- `tests/test_prd_routes.py`
- `docs/release-candidate-P11-3-freeze-checklist-20260628.md`

## 禁止修改范围

- 不修改除 `tests/test_prd_routes.py` 之外的测试文件。
- 不修改生产代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 返修要求

### 1. 清理 whitespace 阻断项

当前阻断：

```bash
git diff --check
```

输出：

```text
tests/test_prd_routes.py:366: new blank line at EOF.
```

只删除 `tests/test_prd_routes.py` 末尾多余空行，不改测试逻辑。

### 2. 重新读取最新工作树状态

清理后重新运行：

```bash
git status --short
git diff --stat
git diff --check
```

用最新结果更新 `docs/release-candidate-P11-3-freeze-checklist-20260628.md`：

- modified/untracked/total。
- 未跟踪分布。
- `git diff --stat`。
- `git diff --check` 必须记录为通过，且无输出。
- 文档/提交顺序中的文档数量需要同步最新状态。

注意：P11-3 初验失败报告和本返修指令会新增文档条目，所以最新计数会比初验时变化。

### 3. 复跑冻结检查命令

运行并记录：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 交付报告

提交返修说明，列出：

- `git diff --check` 是否已无输出且退出码为 0。
- 最新 `git status` 计数。
- 冻结检查单更新了哪些字段。
- 验收命令结果。
