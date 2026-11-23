# P10-2 交付报告：PRD 路由契约硬化

验收日期：2026-06-25

结论：通过。

## 1. 根因

无 bug。P10-1 已修复 500 回归，P10-2 在此基础上将路由契约断言从"确认有字段"升级为"确认字段名、类型、值均正确"。同时补充了 P10-2 指令中要求的错误路径测试。

## 2. 修改内容

| 测试 | 修改 |
|---|---|
| `test_post_generate_prd_success` | 新增：`isinstance` 类型检查、`prd_length == len(MOCK_PRD_CONTENT)` 精确匹配、`message` 字段存在且类型为 str |
| `test_post_generate_prd_value_error_returns_404` | **新增** — mock generator 抛 `ValueError`，验证路由返回 404 + detail 含 `not found` |
| `test_post_generate_prd_runtime_error_returns_500` | **新增** — mock generator 抛 `RuntimeError`，验证路由返回 500 + detail 含 `PRD generation failed` |
| `test_get_prd_markdown_format` | 新增：`requirement_id` / `title` 字段 + `isinstance(content, str)` |
| `test_get_prd_json_format` | 新增：`requirement_id` + `title` 顶层字段、完整的 12 个 content key 枚举断言、类型断言（`user_stories: list`、`impact: dict` 等）、`prd_content == MOCK_PRD_CONTENT` 精确匹配、`created_at` / `updated_at` 非空 |
| `mock_session` fixture | 新增 `created_at` / `updated_at` 固定时间戳 |

| 文件 | 修改 | 原因 |
|---|---|---|
| `tests/test_prd_routes.py` | 8 个测试中 5 个增强 + 2 个新增 + 1 个保持不变 | 补齐 P10-2 指令要求的全部契约断言 |

业务代码零改动。

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `.venv/bin/python -m pytest tests/test_prd_routes.py -q` | ✅ 8/8 通过 | 覆盖 generate-prd 成功/404/500 + prd markdown/json/400/404 |
| `ruff check tests/test_prd_routes.py` | ✅ 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | ✅ 43/43 通过 | 8 PRD + 10 contract + 10 model/route + 9 GitHub + 6 evidence chain |

## 4. P9 回归确认

P9 全部测试通过（35 个受保护）。本次仅修改测试文件，不涉及任何 P9 业务代码。

## 5. 遗留风险

- 无。
