# P10-7 验收报告：PRD 链路总回归与归档

验收日期：2026-06-27

结论：不通过，需要返修。

## 已通过项

总回归命令本地复验通过：

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

### P1-1：生产代码修改归属不符合代码事实

位置：`docs/acceptance-P10-final-summary-20260627.md:55`

问题：

文档写道 P10 生产代码修改集中在 `signal_miner/routes/assets.py`，并标注为“P10-1 回归修复”。这不符合 P10-1 代码事实。P10-1 的修复是测试层 patch `signal_miner.pipeline.prd_generator.generate_prd_for_requirement`，交付报告和最终验收报告均说明业务代码零改动；`signal_miner/routes/assets.py` 的 `source_url` 相关变更属于 P9 来源点击链路遗留改动。

证据：

- `docs/acceptance-P10-1-prd-route-regression.md` 明确写明“业务代码零改动”。
- `docs/acceptance-P10-1-final-pass-20260625.md` 的代码核查只确认 route 动态 import 与测试 patch 生效，没有记录 P10-1 修改 `assets.py`。
- 当前 `git diff -- signal_miner/routes/assets.py` 显示的是 evidence trail 的 `source_url` 解析逻辑，与 P10-1 PRD 路由 500 回归修复不是同一事项。

影响：

最终归档会误导后续发布、回滚和审计判断，把 P9 变更误归因到 P10-1。

验收要求：

修正文档归档说明，明确：

- P10 生产代码修改集中在 `signal_miner/pipeline/prd_generator.py`（P10-4/P10-5/P10-6）。
- P10 测试代码修改集中在 `tests/test_prd_routes.py`（P10-1/P10-2）和 `tests/test_prd_generator.py`（P10-3/P10-4/P10-5/P10-6）。
- `signal_miner/routes/assets.py` 的 `source_url` 变更属于 P9 来源点击链路，不应标为 P10-1 生产修复。

### P1-2：warning 描述不准确

位置：`docs/acceptance-P10-final-summary-20260627.md:48`、`docs/acceptance-P10-final-summary-20260627.md:61`

问题：

文档把 `StarletteDeprecationWarning` 描述为“HTMX 兼容”或“FastAPI test client 仍使用 HTMX”。实际 warning 来自 `fastapi/testclient.py`，内容是 Starlette 使用 `httpx` 的兼容性弃用提示，并建议安装 `httpx2`。

证据：

本地 pytest 输出：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

影响：

会让维护者误判 warning 来源，以为它与 HTMX 前端能力相关。

验收要求：

将相关描述修正为 `StarletteDeprecationWarning: Starlette TestClient/httpx 兼容性提示，非阻塞`，不要再写 HTMX。

### P2-1：语法检查命令记录不完整

位置：`docs/acceptance-P10-final-summary-20260627.md:49`

问题：

P10-7 指令要求运行：

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
```

汇总文档只记录了：

```bash
.venv/bin/python -m compileall signal_miner
```

本次验收已补跑完整命令并通过，但文档需要记录实际要求的完整命令。

验收要求：

将总回归结果中的 compileall 命令修正为 `.venv/bin/python -m compileall signal_miner frontend/app.py`。

## 非阻断观察项

当前代码和测试事实本身通过。问题集中在 P10 最终汇总文档的归档准确性，不需要修改生产代码或测试代码。

## 复验要求

修正文档后复验：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```
