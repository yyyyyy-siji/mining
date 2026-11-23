# P9-4 交付报告：API 响应模型契约固化

验收日期：2026-06-24

结论：通过。

## 1. 响应模型

| 路由 | response_model | 字段 |
|---|---|---|
| `GET /connectors` | `ConnectorListResponse` | `connectors: list[str]` |
| `POST /connectors/github/fetch` | `GitHubFetchResponse` | `repo: str`, `ingested_count: int`, `source_type: str` |

## 2. 修改内容

| 文件 | 修改 | 说明 |
|---|---|---|
| `signal_miner/routes/connectors.py` | 新增 `ConnectorListResponse`、`GitHubFetchResponse` 两个 Pydantic BaseModel | 固化字段契约，防止 drift |
| `signal_miner/routes/connectors.py` | 两个路由添加 `response_model=` 参数 | FastAPI 自动校验 + OpenAPI schema 生成 |
| `tests/test_connector_response_models.py` | 新增 8 项测试 | 详见下方 |
| `tests/test_source_clickthrough_contract.py` | 新增 4 项 P9-4 源码级契约断言 | 验证 response_model 存在 + 字段正确 |

### 测试覆盖（`test_connector_response_models.py`）

| 测试 | 类型 |
|---|---|
| `test_connector_list_response_model_shape` | Pydantic 序列化 — `{"connectors": [...]}` |
| `test_github_fetch_response_model_shape` | Pydantic 序列化 — `ingested_count` 存在，`ingested` 不存在 |
| `test_github_fetch_response_has_ingested_count_not_ingested_field` | 字段级 — `model_fields` 不含 `ingested` |
| `test_repo_pattern_valid` | 请求验证 — `owner/repo` 通过 |
| `test_repo_pattern_invalid` | 请求验证 — 非法格式抛出 |
| `test_defaults` | 请求模型 — 默认值正确 |
| `test_connectors_list_route` | 路由 smoke — 200 + `connectors` list |
| `test_github_fetch_validates_repo` | 路由 smoke — 非法 repo → 422 |

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | ✅ 通过 | 无语法错误 |
| `ruff check signal_miner/routes/connectors.py` | ✅ 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_source_clickthrough_contract.py tests/test_github_connector.py -q` | ✅ 33/33 通过 | 8 响应模型 + 18 契约 + 7 GitHub connector |

## 4. 兼容性确认

- GitHub connector 前端仍读取 `result.ingested_count` — 字段名未变。
- 批量导入仍读取 `result.ingested` — `BatchIngestResponse` 未受影响。
- `POST /connectors/github/fetch` 返回的 JSON 键名与 P9-3 完全一致：`repo`、`ingested_count`、`source_type`。
- 测试不访问真实 GitHub 网络。

## 5. 遗留风险

- 无。
