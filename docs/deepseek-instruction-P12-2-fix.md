# DeepSeek 返修指令：P12-2 站点级真实采集适配器与证据包

## 任务目标

修复 P12-2 验收失败项。不要重写整套适配器，只处理验收报告中的三个阻断问题：

1. 指令要求的 ruff 全范围命令失败。
2. 批量适配器静默跳过无 URL 条目。
3. 缺少本地服务/API/浏览器运行态证据。

失败报告：`docs/acceptance-P12-2-source-acquisition-adapters.md`

## 允许修改范围

仅允许修改：

- `signal_miner/connectors/`
- `signal_miner/connectors/platforms/`
- `tests/test_source_acquisition_contract.py`
- `frontend/static/app.js`（仅当运行态截图证明前端提示缺失时）
- `docs/acceptance-P12-2-delivery-20260708.md`（更新交付报告）
- `docs/P12-2-screenshots/`（新增运行态证据）

如确需修改其他文件，必须在交付报告中列明原因。

## 禁止修改范围

- 不得放松 P12-1 的 URL 必填、域名匹配、搜索落地页、批量预校验。
- 不得删除或弱化现有 P12-2 适配器功能。
- 不得把缺 URL 条目静默跳过、计数后继续、或只写 warning。
- 不得只改测试来适配错误行为。
- 不得把“代码路径推演”当成运行态证据。

## 返修要求

### 1. 修复 ruff 全范围命令

必须让以下命令退出码为 0：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
```

注意：验收失败时该命令发现 37 个问题，集中在：

- `signal_miner/connectors/__init__.py`
- `signal_miner/connectors/media_crawler_client.py`
- `signal_miner/connectors/platforms/bilibili.py`
- `signal_miner/connectors/platforms/douyin.py`
- `signal_miner/connectors/platforms/weibo.py`
- `signal_miner/connectors/platforms/xiaohongshu.py`

只做 lint/typing/unused-arg 级别修复，不改变连接器业务行为。

### 2. 批量适配器必须失败而不是静默跳过

修改：

- `SearchEvidenceAdapter.from_search_results_batch()`
- `GenericEvidenceAdapter.from_dicts_batch()`

要求：

- 任一 item 缺 URL、错 URL、字段不合规时抛出 `EvidencePackageError`。
- 错误信息必须包含失败 item 的 1-based index 和原始原因。
- 不得 `continue` 静默跳过。
- 返回列表长度必须等于输入列表长度，除非抛异常。

更新测试：

- 删除或改写 `test_search_result_batch_skips_invalid`。
- 删除或改写 `test_generic_adapter_batch_skips_invalid`。
- 新增断言：

```text
SearchEvidenceAdapter.from_search_results_batch([...invalid...]) 抛 EvidencePackageError，信息包含 "第 2 条"
GenericEvidenceAdapter.from_dicts_batch([...invalid...]) 抛 EvidencePackageError，信息包含 "第 2 条"
```

### 3. 补做运行态证据

必须在本地服务或等价 ASGI TestClient 路径上验证：

- 合法 GitHub 证据包转 payload 后，`/feedback/ingest` 成功或 TestClient 返回成功。
- 搜索结果列表页 URL 被拒绝。
- `browser_screenshot` 缺 `screenshot_path` 且缺 `source_note` 被拒绝。
- 前端批量 JSON 页面显示证据包字段说明。

保存证据到：

```text
docs/P12-2-screenshots/
```

至少包含：

- `p12-2-api-evidence.json`
- `p12-2-import-evidence-package-fields.png`

如果使用 TestClient 而非运行中的 HTTP 服务，报告中必须明确写出原因和验证路径。

## 必跑命令

返修完成后完整运行：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
node --check frontend/static/app.js
git diff --check
.venv/bin/python -m pytest tests/test_source_acquisition_contract.py -q
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

## 交付报告更新要求

更新 `docs/acceptance-P12-2-delivery-20260708.md`，新增“返修说明”小节，必须包含：

- ruff 全范围命令退出码和关键输出。
- 批量适配器失败策略说明。
- 更新后的测试名。
- 运行态证据文件路径。
- 未覆盖风险。

## 交付后回复

只提交更新后的交付报告路径，不要口头声称验收通过。验收方会重新按代码事实复验。
