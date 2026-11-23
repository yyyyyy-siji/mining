# P10-2 最终验收报告：PRD 路由契约硬化

验收日期：2026-06-25

结论：通过。

## 验收范围

本次验收覆盖 `tests/test_prd_routes.py` 中 PRD 路由契约硬化结果：

- `POST /requirements/{req_id}/generate-prd` 成功响应字段、类型和值。
- generator 抛 `ValueError` 时返回 404。
- generator 抛 `RuntimeError` 时返回 500，且 detail 包含 `PRD generation failed`。
- `GET /requirements/{req_id}/prd?format=markdown` 的顶层字段与 markdown 内容类型。
- `GET /requirements/{req_id}/prd?format=json` 的顶层字段、content 必需 key、主要字段类型与 `prd_content` 精确值。
- requirement 不存在与非法 format 的错误路径。

## 代码核查

- `tests/test_prd_routes.py:127` 的成功路径断言已从“有响应”升级为字段名、字段类型和关键值精确验证。
- `tests/test_prd_routes.py:165` 新增 generator `ValueError` 到 404 的路由契约测试。
- `tests/test_prd_routes.py:186` 新增 generator `RuntimeError` 到 500 的路由契约测试。
- `tests/test_prd_routes.py:238` 补强 markdown 响应的顶层字段与 `content: str` 契约。
- `tests/test_prd_routes.py:270` 补强 json 响应的 `content` 对象 key 集合与字段类型契约。
- 本阶段未发现 PRD 路由生产代码变更；工作树中的 `signal_miner/routes/assets.py` diff 属于 P9 数据来源点击遗留改动。

## 验证结果

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py -q
```

结果：8 passed。

```bash
ruff check tests/test_prd_routes.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py::test_post_generate_prd_value_error_returns_404 tests/test_prd_routes.py::test_post_generate_prd_runtime_error_returns_500 -q -vv
```

结果：2 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：43 passed，1 个 `StarletteDeprecationWarning`，非阻塞。

## 回归确认

P9 数据来源点击、连接器响应字段、GitHub connector、证据链保护集未受影响。P10-1 修复的 PRD 路由成功路径也仍然通过。

## 最终结论

P10-2 达成目标：PRD 路由的成功响应、格式分支和核心错误路径已经有更明确的契约测试保护。

## 后续建议

下一阶段建议覆盖 `generate_prd_for_requirement` 的 generator 层契约，重点验证 PRD 内容持久化、状态更新、LLM 调用参数和 audit log 行为，避免路由层 mock 掉 generator 后留下内部流程盲区。
