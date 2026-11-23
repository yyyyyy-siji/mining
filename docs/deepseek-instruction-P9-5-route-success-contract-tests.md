# DeepSeek 执行指令：P9-5 路由成功路径契约测试固化

## 任务目标

将 P9-4 commander 复验中的 ad-hoc ASGI 成功路径检查固化为仓库内自动化测试，减少连接器 API 响应契约后续漂移风险。

## 背景 / 当前问题

P9-4 已通过：

- `GET /connectors` 有 `ConnectorListResponse`。
- `POST /connectors/github/fetch` 有 `GitHubFetchResponse`。
- response model 和字段契约正确。

但当前仓库内测试主要覆盖：

- response model 序列化。
- 非法 repo → 422。
- 源码级字段断言。

尚未持久化覆盖：

- 有效 `POST /connectors/github/fetch` 请求。
- mock `GitHubConnector` 不访问真实网络。
- 成功响应实际经过 FastAPI 路由和 response model 后仍返回 `repo`、`ingested_count`、`source_type`，且不返回 `ingested`。

## 允许修改范围

- `tests/test_connector_response_models.py`
- 如确有必要，可新增一个聚焦测试文件：
  - `tests/test_connector_routes_contract.py`

## 禁止修改范围

- 不要修改业务代码。
- 不要修改 `signal_miner/routes/connectors.py`，除非测试暴露真实 bug。
- 不要真实访问 GitHub 网络。
- 不要修改前端。
- 不要做无关 ruff 清理。

## 实现要求

新增一个持久化测试，等价覆盖以下 ad-hoc 验证：

```python
class FakeConnector:
    source_type = "github"
    async def fetch(self):
        if False:
            yield None

with patch("signal_miner.connectors.github_connector.GitHubConnector", FakeConnector), \
     patch("signal_miner.routes.connectors.get_session_factory", return_value=fake_session_factory):
    response = await client.post(
        "/api/v1/connectors/github/fetch",
        json={"repo": "owner/repo", "state": "all"},
    )

assert response.status_code == 200
assert response.json() == {
    "repo": "owner/repo",
    "ingested_count": 0,
    "source_type": "github",
}
assert "ingested" not in response.json()
```

测试要求：

- 使用 ASGI `AsyncClient` 或 `TestClient` 均可。
- 必须 mock `GitHubConnector`，不得访问真实网络。
- 必须 mock 或绕开 DB session factory，避免依赖真实数据库。
- 测试名建议：
  - `test_github_fetch_success_route_returns_response_model_fields`

## 验收标准

```bash
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py -q
ruff check tests/test_connector_response_models.py
```

通过条件：

- 新增成功路径测试通过。
- GitHub connector 回归通过。
- ruff 对新增测试文件无错误。

## 交付报告模板

```markdown
# P9-5 交付报告：路由成功路径契约测试固化

## 1. 新增测试

| 测试名 | 覆盖内容 |
|---|---|

## 2. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 3. 网络/数据库隔离确认

- GitHubConnector 已 mock。
- DB session factory 已 mock 或未触发真实 DB。

## 4. 遗留风险

- 如无，写“无”。
```

