# P9-3 交付报告：连接器响应字段契约验收

验收日期：2026-06-24

结论：通过（字段契约已一致，无需修复）。

## 1. 字段契约结论

| 接口 | 后端字段 | 前端读取字段 | 是否一致 |
|---|---|---|---|
| `POST /connectors/github/fetch` | `ingested_count` | `result.ingested_count` | ✅ 一致 |
| `GET /connectors` | `connectors` | `const { connectors }` | ✅ 一致 |
| `POST /feedback/batch` | `ingested` | `result.ingested` | ✅ 一致（P9-1-fix 已修） |
| `GET /feedback` | `source_url`, `external_url` | `fb.source_url`, `fb.external_url` | ✅ 一致 |
| `GET /signals` | `source_url`, `source_type` | `sig.source_url`, `sig.source_type` | ✅ 一致 |
| `GET /requirements/{id}/evidence-trail` | `source_url`, `external_url` | `link.source_url`, `link.external_url` | ✅ 一致 |

### 关键发现

`POST /connectors/github/fetch` 与 `POST /feedback/batch` 使用**不同的**计数字段名：
- 连接器返回 `ingested_count`
- 批量导入返回 `ingested`

这是两个独立 API 的不同设计选择，各自前后端契约一致，无需强制统一。

## 2. 修复内容

无代码修复。字段契约已经匹配，无需修改业务代码。

新增契约测试（`tests/test_source_clickthrough_contract.py`）：

| 测试 | 目的 |
|---|---|
| `test_github_fetch_backend_returns_ingested_count` | 后端必须返回 `ingested_count` 字段 |
| `test_github_fetch_frontend_reads_ingested_count` | 前端必须读取 `result.ingested_count` |
| `test_github_fetch_contract_consistency` | 两端字段名一致，防止未来无意识破坏 |
| `test_connectors_list_contract_consistent` | `GET /connectors` 响应 `{connectors: [...]}` 前后端一致 |

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | ✅ 通过 | 无语法错误 |
| `node --check frontend/static/app.js` | ✅ 通过 | 无语法错误 |
| `ruff check signal_miner/routes/connectors.py frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils` | ✅ 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_github_connector.py -q` | ✅ 22/22 通过 | 13 源级契约 + 9 GitHub connector 单元测试 |

## 4. 遗留风险

- 无。所有连接器响应字段契约已验证一致。
- GitHub connector 单元测试已使用 mock，不访问真实网络。
