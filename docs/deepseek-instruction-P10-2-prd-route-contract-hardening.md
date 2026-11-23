# P10-2 优化指令：PRD 路由契约硬化

## 背景

P10-1 已修复 `POST /requirements/{req_id}/generate-prd` 成功路径测试中因 generator 内部数据库调用未 mock 导致的 500 回归。当前 PRD 路由测试可通过，但契约保护仍主要集中在成功状态与少量响应字段。

## 目标

在不改业务行为的前提下，补强 PRD 路由的响应契约测试，确保未来修改不会破坏 API 字段、错误码和格式分支。

## 范围

只允许修改测试与必要的测试辅助代码。除非发现真实 bug，不修改生产代码。

重点覆盖：

1. `POST /requirements/{req_id}/generate-prd`
   - 成功时返回 200。
   - 响应必须包含且类型正确：`requirement_id: str`、`title: str`、`prd_length: int`、`status: str`、`message: str`。
   - `prd_length` 必须等于 mocked PRD 内容长度。
   - generator 抛 `ValueError` 时返回 404。
   - generator 抛 `RuntimeError` 时返回 500，detail 包含 `PRD generation failed`。

2. `GET /requirements/{req_id}/prd?format=markdown`
   - 成功时返回 200。
   - 响应必须包含：`requirement_id`、`title`、`format`、`content`。
   - `format` 必须为 `markdown`。
   - `content` 必须为字符串。

3. `GET /requirements/{req_id}/prd?format=json`
   - 成功时返回 200。
   - 响应必须包含：`requirement_id`、`title`、`format`、`content`。
   - `format` 必须为 `json`。
   - `content` 必须为对象，且至少包含：`title`、`user_stories`、`acceptance_criteria`、`impact`、`priority`、`decision_reasoning`、`evidence_trail`、`prd_content`、`opportunity_ids`、`status`、`created_at`、`updated_at`。

4. 错误路径
   - 不存在 requirement 返回 404。
   - 非法 format 返回 400，detail 包含 `Unsupported format`。

## 验收命令

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py -q
ruff check tests/test_prd_routes.py
```

如修改了共享 fixture 或路由相关契约测试，还需运行：

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

## 交付要求

提交交付报告，说明：

- 新增或调整了哪些契约断言。
- 每条验收命令的实际结果。
- 是否修改生产代码；如修改，必须说明原因。
