# P11-3 二次返修复验报告：发布冻结前最终检查单

验收日期：2026-06-28

结论：不通过，需要三次返修。

## 已通过项

原代码侧阻断已经解除：

```bash
git diff --check
```

结果：通过，无输出。

`tests/test_prd_routes.py` 文件末尾已清理，最后一行为：

```python
    assert response.status_code == 404
```

其他门禁也通过：

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

### P1-1：冻结检查单摘要仍残留旧的 `git diff --check` warning

位置：`docs/release-candidate-P11-3-freeze-checklist-20260628.md:18`

问题：

冻结检查单第 72 行已记录 `git diff --check` 通过、exit=0、无输出，但第 18 行仍写：

```text
Warning: tests/test_prd_routes.py:366: new blank line at EOF
```

这与当前命令结果和同一文档后文互相矛盾。

证据：

```bash
git diff --check
```

实际结果：退出码 0，无输出。

影响：

发布冻结检查单是最终人工核对依据。摘要区仍残留已修复的阻断 warning，会误导人工认为工作树仍存在 whitespace 问题。

验收要求：

只修改 `docs/release-candidate-P11-3-freeze-checklist-20260628.md`：

- 将第 18 行更新为 `git diff --check` 通过、exit=0、无输出。
- 确认文档中不再出现 `new blank line at EOF` 或 `tests/test_prd_routes.py:366`。
- 重新运行 `git status --short` 并按最新状态更新工作树计数。
- 不修改生产代码或测试代码。

## 复验要求

三次返修后复验：

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
