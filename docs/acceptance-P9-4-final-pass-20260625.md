# P9-4 最终验收报告：API 响应模型契约固化

验收日期：2026-06-25

结论：通过。

## 验收范围

本次验收覆盖 P9-4 指令要求的连接器 API 响应模型固化：

- `ConnectorListResponse`
- `GitHubFetchResponse`
- `GET /connectors` 的 `response_model`
- `POST /connectors/github/fetch` 的 `response_model`
- 前端字段兼容性
- 连接器契约测试与 GitHub connector 回归

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| Python 语法检查 | 通过 | `.venv/bin/python -m compileall signal_miner frontend/app.py` |
| JS 语法检查 | 通过 | `node --check frontend/static/app.js` |
| 连接器路由 ruff | 通过 | `ruff check signal_miner/routes/connectors.py` → `All checks passed!` |
| 响应模型 + 契约 + GitHub connector 测试 | 通过 | `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_source_clickthrough_contract.py tests/test_github_connector.py -q` → `33 passed` |
| ASGI 成功路径 mock 验证 | 通过 | `POST /api/v1/connectors/github/fetch` 返回 `{'repo': 'owner/repo', 'ingested_count': 0, 'source_type': 'github'}` |

## 代码核对

- `signal_miner/routes/connectors.py` 已定义 `ConnectorListResponse(connectors: list[str])`。
- `signal_miner/routes/connectors.py` 已定义 `GitHubFetchResponse(repo, ingested_count, source_type)`。
- `GET /connectors` 已声明 `response_model=ConnectorListResponse`。
- `POST /connectors/github/fetch` 已声明 `response_model=GitHubFetchResponse`。
- `frontend/static/app.js` 仍读取 `result.ingested_count`，与 GitHub fetch 响应一致。
- `/feedback/batch` 仍独立使用 `result.ingested`，未被 P9-4 影响。

## 回归确认

- GitHub connector 单元测试通过，未访问真实 GitHub 网络。
- 响应模型序列化测试确认 `GitHubFetchResponse` 不包含裸 `ingested` 字段。
- `GET /connectors` 路由 smoke 测试通过。
- 非法 repo 仍在请求验证阶段返回 422。

## 非阻断观察

- 新增测试中没有持久化“有效 GitHub fetch + mock connector”的成功路径测试；该路径由 commander 本次用 ASGI ad-hoc 脚本补验通过。建议下一阶段将这个 ad-hoc 验证固化为测试，减少后续回归风险。

## 最终结论

P9-4 通过。关键连接器 API 响应字段已由 Pydantic response model 固化，前端消费字段保持兼容，现有测试与补充路由验证均确认契约正确。

## 后续建议

下一阶段建议将 commander 的 ASGI 成功路径 mock 验证固化为仓库内测试，并清理源码级字符串断言中较脆弱的部分。

