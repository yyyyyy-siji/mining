# P9-5 交付报告：路由成功路径契约测试固化

验收日期：2026-06-25

结论：通过。

## 1. 新增测试

| 测试名 | 覆盖内容 |
|---|---|
| `test_github_fetch_success_route_returns_response_model_fields` | 完整路由 → response_model → JSON 路径，mock connector 无 yield，验证 `ingested_count=0`，不泄漏 `ingested` |
| `test_github_fetch_success_route_counts_ingested` | Mock connector yield 1 条反馈，验证 `ingested_count=1`，`session.add` 和 `session.commit` 各调用一次 |

## 2. 修改内容

| 文件 | 修改 | 说明 |
|---|---|---|
| `tests/test_connector_response_models.py` | 新增 2 个 P9-5 成功路径测试 + 辅助类 `_FakeSessionFactory` / `_FakeAsyncSessionCtx` | 模拟 `async_sessionmaker` / `AsyncSession` 协议 |
| `tests/test_connector_response_models.py` | 修复 B017 ruff 警告 | `# noqa: B017` + exc_info 断言 |

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py -q` | ✅ 19/19 通过 | 10 响应模型/路由 + 9 GitHub connector |
| `ruff check tests/test_connector_response_models.py` | ✅ 通过 | All checks passed |

## 4. 网络/数据库隔离确认

- `GitHubConnector` 已 mock（`signal_miner.connectors.github_connector.GitHubConnector`）。
- `get_session_factory` 已 mock（`signal_miner.routes.connectors.get_session_factory`），返回 `_FakeSessionFactory` 实例。
- 无真实网络请求，无真实数据库连接。
- `async with session_factory() as session:` 通过 `_FakeSessionFactory.__call__()` → `_FakeAsyncSessionCtx` 正确模拟。

## 5. 遗留风险

- 无。
