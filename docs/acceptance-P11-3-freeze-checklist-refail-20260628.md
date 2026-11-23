# P11-3 返修复验报告：发布冻结前最终检查单

验收日期：2026-06-28

结论：不通过，需要二次返修。

## 已通过项

除 `git diff --check` 外，其余门禁仍通过：

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

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
```

结果：通过。

```bash
node --check frontend/static/app.js
```

结果：通过。

## 阻断问题

### P1-1：原 whitespace 阻断仍未修复

位置：`tests/test_prd_routes.py:366`

问题：

返修后重新运行：

```bash
git diff --check
```

仍返回失败：

```text
tests/test_prd_routes.py:366: new blank line at EOF.
```

文件尾部仍存在多余空行：

```text
365    assert response.status_code == 404
366
```

影响：

P11-3 发布冻结检查要求 `git diff --check` 无 whitespace error。该命令仍失败，因此不能放行冻结检查单。

验收要求：

只删除 `tests/test_prd_routes.py` 末尾多余空行，确保文件最后一行是：

```python
    assert response.status_code == 404
```

并确保：

```bash
git diff --check
```

退出码为 0 且无输出。

### P1-2：冻结检查单仍记录阻断状态，且工作树计数已过期

位置：`docs/release-candidate-P11-3-freeze-checklist-20260628.md:13` 至 `docs/release-candidate-P11-3-freeze-checklist-20260628.md:18`、`docs/release-candidate-P11-3-freeze-checklist-20260628.md:72`

问题：

冻结检查单仍记录 `git diff --check` 为不通过，并仍保留旧的工作树计数。返修时必须在 whitespace 修复后重新运行 `git status --short`、`git diff --stat`、`git diff --check`，并更新文档。

验收要求：

更新冻结检查单：

- 最新 modified/untracked/total。
- 最新未跟踪分布。
- 最新 `git diff --stat`。
- `git diff --check` 记录为通过且无输出。
- 移除“trailing newline”遗留风险。

## 复验要求

二次返修后复验：

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
