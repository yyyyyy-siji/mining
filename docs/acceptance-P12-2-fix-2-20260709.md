# P12-2 二次返修验收报告：站点级证据包适配器

验收日期：2026-07-09

结论：不通过。

本次验收不采用交付报告作为结论依据，仅把 `docs/acceptance-P12-2-delivery-20260708.md` 作为线索，按代码事实、测试命令和运行态行为重新核验。

## 已通过项

- `SearchEvidenceAdapter.from_search_results_batch()` 已从静默跳过坏数据改为立即抛出 `EvidencePackageError`，错误信息包含 `第 N 条`。
- `GenericEvidenceAdapter.from_dicts_batch()` 已从静默跳过坏数据改为立即抛出 `EvidencePackageError`，错误信息包含 `第 N 条`。
- `AcquisitionEvidence.to_ingest_payload()` 会调用 P12-1 的 `validate_required_source_url()`。
- 运行态导入页面可以打开，导入反馈入口、证据包字段说明、`browser_screenshot` 提示和 `AIGC视频爆款挖掘` profile 均存在。
- 独立浏览器验收截图已保存：`docs/P12-2-screenshots/acceptance-P12-2-import-runtime-20260709.png`。

## 阻断问题

### P1：运行态 API 仍接受不可追溯的 browser_screenshot 数据

期望：任何进入 `/api/v1/feedback/ingest` 或 `/api/v1/feedback/batch` 的 `capture_method=browser_screenshot` 数据，都必须提供 `screenshot_path` 或 `source_note`，否则 422 拒绝。

实际：`IngestRequest` 没有 `screenshot_path` 字段，`_prepare_ingest_data()` 只做 URL 校验，不做截图证据校验。直接调用运行态路由时，缺少 `screenshot_path/source_note` 的截图采集数据仍返回 201。

验收复现：

```bash
.venv/bin/python - <<'PY'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from signal_miner.routes.feedback import router as feedback_router

app = FastAPI()
app.include_router(feedback_router, prefix='/api/v1')
client = TestClient(app)
mock_ingest = AsyncMock(return_value='rfb_test')
payload = {
    'source_type': 'douyin',
    'text': 'test content',
    'external_url': 'https://www.douyin.com/video/123456',
    'capture_method': 'browser_screenshot',
}
with patch('signal_miner.pipeline.runner.ingest_feedback', mock_ingest):
    response = client.post('/api/v1/feedback/ingest', json=payload)
print(response.status_code)
print(response.json())
PY
```

实际输出：

```text
201
{'feedback_id': 'rfb_test', 'is_duplicate': False, 'pipeline_profile': 'product_feedback'}
```

### P1：前端说明中的证据字段会被 API 忽略，无法沉淀到原始反馈 context

期望：批量 JSON 说明中的 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload` 至少应被 API 模型接收并写入 `RawFeedbackRow.context`，否则后续无法审计截图/OCR来源。

实际：前端展示了这些字段，但 `signal_miner/routes/feedback.py` 的 `IngestRequest` 与 `_prepare_ingest_data()` 没有接收/保存这些字段。即使请求带上 `screenshot_path` 和 `ocr_text`，路由仍返回 201，但传入 pipeline 的 `context` 中没有任何截图/OCR证据。

验收复现输出：

```text
status= 201
response= {'feedback_id': 'rfb_test', 'is_duplicate': False, 'pipeline_profile': 'product_feedback'}
context= {'capture_method': 'browser_screenshot', 'source_url_required': True, 'source_url_validation': 'format_and_platform_domain', 'source_platform': 'douyin'}
```

这说明当前实现只能在 `AcquisitionEvidence` 适配器路径上校验截图证据，不能覆盖真实运行态导入路径。对用户最关心的“导入反馈”功能而言，约束仍可被绕过。

## 已执行验收命令

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
node --check frontend/static/app.js
git diff --check
.venv/bin/python -m pytest tests/test_source_acquisition_contract.py -q
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python scripts/p12_2_api_evidence.py
.venv/bin/python -m pytest -q
```

结果：

- 静态检查通过。
- 分组测试通过。
- 全量测试通过：158 passed，存在既有 warning。
- 证据脚本 4/4 通过，但它没有覆盖运行态 API 对 `browser_screenshot` 缺证据的拒绝，也没有覆盖截图/OCR字段入库上下文。

## 验收决定

P12-2 二次返修不通过。

返修必须把 `browser_screenshot` 的截图证据约束下沉到运行态 API 合约，并保证前端/批量 JSON 声明的证据字段不会被静默丢弃。修复后需要补充路由级负例、批量索引错误、字段持久化上下文的契约测试，再重新提交交付报告。
