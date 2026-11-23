# P9-6 最终验收报告：契约测试硬化

验收日期：2026-06-25

结论：通过。

## 验收范围

本次验收覆盖 P9-6 指令要求的测试硬化：

- 减少后端契约的源码级字符串断言。
- 保留前端在缺少前端测试框架时必要的最小源码断言。
- 保持 P9-1 到 P9-5 的核心契约覆盖不降低。
- 确认本阶段不修改业务代码。

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| 测试文件 ruff | 通过 | `ruff check tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py` → `All checks passed!` |
| P9 契约 + GitHub + evidence 回归 | 通过 | `.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` → `35 passed` |
| 测试语法检查 | 通过 | `.venv/bin/python -m compileall tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py` |

## 覆盖确认

- `/feedback/batch` 前端数组请求体和 `result.ingested` 读取仍被覆盖。
- SPA URL 字段归一化、`escapeHtml`、`target="_blank"` / `rel="noopener noreferrer"` 仍被覆盖。
- Streamlit `_render_source_link` 的 `html.escape(..., quote=True)` 与调用点仍被覆盖。
- evidence trail 的 `source_url` 和 `resolve_source_url` 仍被覆盖。
- GitHub connector 的 `ingested_count` 已主要由 response model 和 ASGI route 测试覆盖。
- `ConnectorListResponse`、`GitHubFetchResponse` 的模型字段和成功路径仍被覆盖。

## 业务代码改动确认

本阶段检查范围内没有发现新的业务代码修改；P9-6 的实质变化集中在测试文件与验收文档。

## 非阻断观察

- `TestClient` 触发 `StarletteDeprecationWarning: install httpx2 instead`，不影响当前测试结果。后续依赖升级时可以单独处理。
- 前端静态 SPA 仍依赖源码级断言保护；在未引入 jsdom/Playwright 前，这是合理的低成本保护。

## 最终结论

P9-6 通过。P9 系列契约测试已经从“主要依赖源码字符串检查”向“模型测试 + 路由成功路径测试 + 必要前端源码保护”收敛，覆盖没有降低。

## 后续建议

下一阶段建议做 P9 系列最终回归和归档：集中运行 P9 相关测试、整理所有 P9 验收报告和指令，列出仍未处理的非阻断技术债。

