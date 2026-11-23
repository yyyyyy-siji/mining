# P12-2 二次返修指令：运行态截图/OCR证据契约补齐

你是执行 AI。本阶段只允许修复 P12-2 二次验收失败项，不要扩展到真实爬虫、OCR 引擎或新平台采集器。

验收失败报告：`docs/acceptance-P12-2-fix-2-20260709.md`

## 背景

P12-2 适配器层已经能生成 `AcquisitionEvidence`，也能在适配器路径中拒绝缺少截图证据的 `browser_screenshot` 数据。但运行态导入路径仍存在漏洞：

- `/api/v1/feedback/ingest` 接受 `capture_method=browser_screenshot` 且没有 `screenshot_path/source_note` 的请求。
- 前端批量 JSON 说明展示了 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload`，但 API 模型不接收这些字段，最终不会写入 `RawFeedbackRow.context`。

这会破坏用户的最高优先级要求：每条导入数据必须有真实、可点击、可追溯的来源。

## 必修目标

1. 运行态 API 必须拒绝不可追溯的 `browser_screenshot` 请求。
2. 前端说明中列出的证据字段必须被 API 接收并保存到 `context`，不能静默丢弃。
3. 单条导入和批量导入必须使用同一套校验逻辑；批量失败必须返回 `第 N 条`。
4. 不得放松 P12-1 的真实来源 URL 校验，不得允许搜索结果列表页、占位 URL 或错域名 URL 进入系统。

## 修改要求

### 1. 后端请求模型补齐

在 `signal_miner/routes/feedback.py` 中扩展 `IngestRequest`，至少增加：

- `screenshot_path: str | None`
- `ocr_text: str | None`
- `source_captured_at: datetime | None`
- `raw_payload: dict[str, Any] | None`

如需 `Any`，使用标准 typing 导入。保持现有字段兼容。

### 2. 后端运行态校验补齐

在 `_prepare_ingest_data()` 中增加统一校验：

- 当 `request.capture_method == "browser_screenshot"` 且 `request.screenshot_path` 与 `request.source_note` 均为空时，抛出 HTTP 422。
- 错误信息必须包含 `screenshot_path` 和 `source_note`，便于测试和用户定位。
- `/feedback/batch` 应复用 `_prepare_ingest_data()`，因此批量错误必须继续带 `第 N 条数据来源不合格` 前缀。

### 3. 后端上下文保存补齐

在 `_prepare_ingest_data()` 生成的 `context` 中保存非空证据字段：

- `screenshot_path`
- `ocr_text`
- `source_captured_at`，保存为 ISO 字符串
- `raw_payload`

保留已有的 `capture_method`、`source_note`、`video_url`、`views`、`likes`、`platform`。

### 4. 前端导入路径补齐

在 `frontend/static/app.js` 中处理运行态一致性：

- 单条导入选择 `browser_screenshot` 时，必须让用户能提供 `screenshot_path` 或 `source_note`，或在缺少两者时前端直接阻止提交并提示。
- 批量 JSON 上传时，不得丢弃 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload` 字段。
- 如果批量 JSON 中某项 `capture_method=browser_screenshot` 且缺少 `screenshot_path/source_note`，前端可以提前提示；即使前端未提前提示，后端也必须 422 拒绝。
- 不要删除 `AIGC视频爆款挖掘` profile。

### 5. 测试补齐

至少新增或修改以下测试：

- `tests/test_feedback_ingest_source_contract.py`
  - 单条 `/feedback/ingest`：`browser_screenshot` 缺少 `screenshot_path/source_note` 返回 422。
  - 单条 `/feedback/ingest`：带 `screenshot_path` 的 `browser_screenshot` 返回 201，mock pipeline 收到的 `context["screenshot_path"]` 存在。
  - 带 `ocr_text`、`source_captured_at` 的请求，mock pipeline 收到的 `context` 保留这些字段。
  - 批量 `/feedback/batch`：第 2 条 `browser_screenshot` 缺证据时返回 422，detail 包含 `第 2 条`。
- 保留并继续通过 `tests/test_source_acquisition_contract.py` 的适配器层测试。

### 6. 证据脚本更新

更新 `scripts/p12_2_api_evidence.py`：

- 增加对真实路由 `/api/v1/feedback/ingest` 的负例：`browser_screenshot` 缺 `screenshot_path/source_note` 必须 422。
- 增加正例：带 `screenshot_path/ocr_text/source_captured_at` 时 201，且 mock pipeline context 中保留字段。
- 输出到 `docs/P12-2-screenshots/p12-2-api-evidence.json`。

## 必跑验收命令

交付前必须运行并在交付报告中贴出结果：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
node --check frontend/static/app.js
git diff --check
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_acquisition_contract.py -q
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python scripts/p12_2_api_evidence.py
.venv/bin/python -m pytest -q
```

## 交付报告要求

更新 `docs/acceptance-P12-2-delivery-20260708.md`，必须包含：

- 修改文件清单。
- 对两个阻断问题的逐条修复说明。
- 必跑命令输出摘要。
- `scripts/p12_2_api_evidence.py` 生成的 JSON 证据摘要。
- 明确说明：运行态 API 已拒绝缺少截图证据的 `browser_screenshot`，且截图/OCR字段会进入 pipeline context。
