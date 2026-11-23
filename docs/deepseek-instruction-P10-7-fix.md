# DeepSeek 返修指令：P10-7 PRD 链路总回归与归档

## 任务目标

只修正 `docs/acceptance-P10-final-summary-20260627.md` 的归档事实错误。不要修改生产代码和测试代码。

## 允许修改范围

- `docs/acceptance-P10-final-summary-20260627.md`

## 禁止修改范围

- 不修改 `signal_miner/` 下任何生产代码。
- 不修改 `tests/` 下任何测试代码。
- 不修改 P9/P10 已通过的最终验收报告。

## 返修项

### 1. 修正生产代码修改归属

当前文档把 `signal_miner/routes/assets.py` 标为“P10-1 回归修复”的生产代码修改，这是错误的。

应改为：

- P10 生产代码修改集中在 `signal_miner/pipeline/prd_generator.py`（P10-4/P10-5/P10-6）。
- P10 测试代码修改集中在 `tests/test_prd_routes.py`（P10-1/P10-2）和 `tests/test_prd_generator.py`（P10-3/P10-4/P10-5/P10-6）。
- `signal_miner/routes/assets.py` 的 `source_url` 变更属于 P9 来源点击链路遗留变更，不应归因到 P10-1。

### 2. 修正 warning 描述

把所有 “HTMX 兼容” 或 “FastAPI test client 仍使用 HTMX” 的描述改为：

`Starlette TestClient/httpx 兼容性弃用提示，非阻塞。`

不要再提 HTMX。

### 3. 修正 compileall 命令记录

将总回归结果中的：

```bash
.venv/bin/python -m compileall signal_miner
```

改为：

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
```

## 验收命令

返修后运行并记录结果：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 交付报告

提交返修说明，列出：

- 修改了哪些文档行。
- 每个返修项如何对应。
- 上述验收命令实际输出。
