# P9-6 交付报告：契约测试硬化

验收日期：2026-06-25

结论：通过。

## 1. 调整摘要

| 测试/断言 | 处理方式 | 原因 |
|---|---|---|
| `test_github_fetch_backend_returns_ingested_count` | 删除 | 已由 `test_github_fetch_response_model_shape` + route 成功路径测试覆盖 |
| `test_github_fetch_contract_consistency` | 删除 | 完全冗余 — 两端字段已分别由 SPA 测试 + Pydantic 模型测试覆盖 |
| `test_connectors_list_contract_consistent` | 重写为 `test_connectors_list_spa_destructures_connectors` | 后端部分已由 `ConnectorListResponse.model_dump()` 测试覆盖，仅保留 SPA 解构检查 |
| `test_connector_routes_have_response_models` | 删除 | response_model 已接入且由 `test_connector_response_models.py` 行为测试覆盖 |
| `test_github_fetch_response_model_fields` | 删除 | 已由 `test_github_fetch_response_model_shape` + `test_github_fetch_response_has_ingested_count_not_ingested_field` 覆盖 |
| `test_connector_list_response_model_fields` | 删除 | 已由 `test_connector_list_response_model_shape` 覆盖 |
| `test_streamlit_imports_html_escape` + `test_streamlit_has_render_source_link_helper` | 合并为 `test_streamlit_has_safe_source_link_helper` | 两个测试验证同一语义；合并为包含 import + `quote=True` + 调用点检查的单个测试 |
| `test_streamlit_no_unsafe_href_with_user_url` | 简化 | 去掉 `_context_lines`/`_context_text` 辅助函数和逐行 regex，改为函数边界感知的线性扫描 |
| `test_evidence_trail_uses_resolve_source_url` | 合并入 `test_evidence_trail_includes_source_url_field` | 单行 `assert` 合并到字段检查中 |
| `test_spa_source_link_uses_target_blank` | 新增 | 补充对 `target="_blank" rel="noopener noreferrer"` 的显式保护 |

## 2. 覆盖保持情况

| 契约 | 覆盖测试 |
|---|---|
| `/feedback/batch` 前端发送数组 | `test_batch_import_sends_array_not_object` |
| `/feedback/batch` 前端读取 `result.ingested` | `test_batch_import_uses_ingested_field` |
| SPA 批量导入 URL 归一化 | `test_batch_import_normalizes_url_fields` |
| SPA escapeHtml 安全 helper | `test_spa_has_escape_html_helper` |
| SPA 链接 target/rel 属性 | `test_spa_source_link_uses_target_blank` |
| SPA GitHub connector 读取 `ingested_count` | `test_github_fetch_spa_reads_ingested_count` |
| SPA connectors list 解构 | `test_connectors_list_spa_destructures_connectors` |
| Streamlit `_render_source_link` 安全转义 | `test_streamlit_has_safe_source_link_helper` |
| Streamlit 无原始 f-string href 注入 | `test_streamlit_no_raw_href_fstring_injection` |
| evidence trail 返回 `source_url` | `test_evidence_trail_includes_source_url_field` |
| GitHubFetchResponse 模型字段 | `test_github_fetch_response_model_shape` + `test_github_fetch_response_has_ingested_count_not_ingested_field` (in `test_connector_response_models.py`) |
| ConnectorListResponse 模型字段 | `test_connector_list_response_model_shape` (in `test_connector_response_models.py`) |
| GitHub fetch 成功路径 route | `test_github_fetch_success_route_returns_response_model_fields` + `test_github_fetch_success_route_counts_ingested` (in `test_connector_response_models.py`) |

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py` | ✅ 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | ✅ 35/35 通过 | 10 contract + 10 model/route + 9 GitHub + 6 evidence chain |

## 4. 业务代码改动确认

- 无。

## 5. 遗留风险

- 无。SPA 源码级字符串断言在没有前端测试框架的前提下是合理的最小保护；一旦引入 jsdom/playwright 测试，这些可进一步升级为 DOM 级断言。
