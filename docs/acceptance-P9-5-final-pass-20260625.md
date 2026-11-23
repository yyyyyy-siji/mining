# P9-5 最终验收报告：路由成功路径契约测试固化

验收日期：2026-06-25

结论：通过。

## 验收范围

本次验收覆盖 P9-5 指令要求的连接器路由成功路径测试固化：

- 有效 `POST /connectors/github/fetch` 请求。
- mock `GitHubConnector`，不访问真实 GitHub 网络。
- mock DB session factory，不依赖真实数据库。
- 成功响应经过 FastAPI 路由和 response model 后仍返回 `repo`、`ingested_count`、`source_type`。
- 响应中不出现错误字段 `ingested`。

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| 成功路径 + GitHub connector 回归 | 通过 | `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py -q` → `19 passed` |
| 新增测试 ruff | 通过 | `ruff check tests/test_connector_response_models.py` → `All checks passed!` |
| 新增测试语法检查 | 通过 | `.venv/bin/python -m compileall tests/test_connector_response_models.py` |

## 新增测试确认

| 测试 | 覆盖内容 |
|---|---|
| `test_github_fetch_success_route_returns_response_model_fields` | mock connector 无 yield，验证完整路由返回 `{"repo", "ingested_count", "source_type"}` 且无 `ingested` |
| `test_github_fetch_success_route_counts_ingested` | mock connector yield 1 条反馈，验证 `ingested_count=1`，并确认 `session.add` / `session.commit` 各调用一次 |

## 隔离确认

- `GitHubConnector` 已通过 `patch("signal_miner.connectors.github_connector.GitHubConnector")` mock。
- `get_session_factory` 已通过 `patch("signal_miner.routes.connectors.get_session_factory")` mock。
- 测试不访问真实网络。
- 测试不连接真实数据库。

## 非阻断观察

- 当前 `tests/test_source_clickthrough_contract.py` 仍包含若干源码级字符串断言；P9-5 已补上最关键的路由成功路径行为测试，但未来仍可继续把脆弱源码断言替换为行为测试。

## 最终结论

P9-5 通过。P9-4 中的 ad-hoc ASGI 成功路径验证已经固化为仓库测试，连接器响应契约的成功路径、计数字段和隔离要求均已覆盖。

## 后续建议

下一阶段建议整理 P9 系列测试结构，逐步减少源码级字符串断言，保留行为测试、response model 测试和路由级契约测试作为主要保障。

