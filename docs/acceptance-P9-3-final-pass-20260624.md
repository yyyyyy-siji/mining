# P9-3 最终验收报告：连接器响应字段契约验收

验收日期：2026-06-24

结论：通过。

## 验收范围

本次验收覆盖连接器页面与后端连接器接口的字段契约：

- `POST /connectors/github/fetch`
- `GET /connectors`
- 静态 SPA 数据源页面 GitHub connector 成功提示
- P9-1/P9-2 已触达的批量导入与来源链接字段回归

## 字段契约结论

| 接口 | 后端字段 | 前端读取字段 | 结论 |
|---|---|---|---|
| `POST /connectors/github/fetch` | `ingested_count` | `result.ingested_count` | 一致 |
| `GET /connectors` | `connectors` | `const { connectors }` | 一致 |
| `POST /feedback/batch` | `ingested` | `result.ingested` | 一致 |
| `GET /feedback` | `source_url`, `external_url` | `fb.source_url`, `fb.external_url` | 一致 |
| `GET /signals` | `source_url`, `source_type` | `sig.source_url`, `sig.source_type` | 一致 |
| `GET /requirements/{id}/evidence-trail` | `source_url`, `external_url` | `link.source_url`, `link.external_url` | 一致 |

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| Python 语法检查 | 通过 | `.venv/bin/python -m compileall signal_miner frontend/app.py` |
| 静态 SPA JS 语法检查 | 通过 | `node --check frontend/static/app.js` |
| 限定范围 ruff | 通过 | `ruff check signal_miner/routes/connectors.py frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils` → `All checks passed!` |
| 契约 + GitHub connector 测试 | 通过 | `.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_github_connector.py -q` → `22 passed` |
| ASGI 路由级 mock 验证 | 通过 | `POST /api/v1/connectors/github/fetch` 返回 `{'repo': 'owner/repo', 'ingested_count': 0, 'source_type': 'github'}` |

## 回归确认

- GitHub connector UI 继续读取 `result.ingested_count`，与后端返回一致。
- 批量反馈导入 UI 继续读取 `result.ingested`，与 P9-1-fix 后端契约一致。
- GitHub connector 单元测试使用 mock，不访问真实网络。
- 本次未启动临时服务。

## 非阻断观察

- `POST /connectors/github/fetch` 当前直接返回裸 `dict`，没有 Pydantic response model；字段契约依赖源码测试和路由级 mock 验证。当前可接受，但后续建议显式建模。
- `tests/test_source_clickthrough_contract.py` 中 P9-3 测试主要是源码级断言，能防止常见字段误改，但不如 API response model 测试稳固。

## 最终结论

P9-3 连接器响应字段契约验收通过。此前观察到的 `result.ingested_count` 不是错误，它与 GitHub connector 后端响应字段一致；与 `/feedback/batch` 的 `ingested` 是两个独立接口的不同字段设计。

## 后续建议

下一阶段建议将关键 API 响应结构显式建模为 Pydantic response model，减少裸 `dict` 返回造成的契约漂移风险。

