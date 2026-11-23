# P10-1 最终验收报告：PRD 路由回归修复

验收日期：2026-06-25

结论：通过。

## 验收依据

本次验收基于代码事实与本地命令结果，不以工作者交付报告作为放行依据。

## 代码核查

- `tests/test_prd_routes.py:121` 的 `test_post_generate_prd_success` 保留对路由层 `get_session_factory` 的 patch，用于验证需求存在性。
- `tests/test_prd_routes.py:135` 新增对 `signal_miner.pipeline.prd_generator.generate_prd_for_requirement` 的 `AsyncMock`，隔离 generator 内部 DB 与 audit log 调用。
- `signal_miner/routes/assets.py:526` 在 handler 内部动态导入 `generate_prd_for_requirement`，因此测试中的模块属性 patch 能在调用时生效。
- `signal_miner/routes/assets.py:541` 仍返回 `GeneratePRDResponse` 契约字段：`requirement_id`、`title`、`prd_length`、`status`、`message`。

## 验收命令

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py -q
```

结果：6 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py::test_post_generate_prd_success -q -vv
```

结果：1 passed。

```bash
ruff check signal_miner/routes/assets.py signal_miner/pipeline/prd_generator.py tests/test_prd_routes.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：41 passed，1 个 StarletteDeprecationWarning，非阻塞。

## 判定

P10-1 修复目标成立：`test_post_generate_prd_success` 不再因为未初始化数据库而返回 500，PRD 路由成功路径契约测试恢复通过。P9 数据来源点击、连接器响应字段、API response model、证据链相关回归组合未受影响。

## 注意事项

当前工作树仍包含 P9 遗留改动与未跟踪验收文档；本次 P10-1 判定只覆盖 PRD 路由回归修复，不代表整个工作树已清理或可直接发布。
