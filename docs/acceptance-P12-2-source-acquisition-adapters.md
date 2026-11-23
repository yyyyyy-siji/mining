# P12-2 验收报告：站点级真实采集适配器与证据包

验收日期：2026-07-08

结论：不通过，需要返修。

## 已通过项

| 验收项 | 结果 |
| --- | --- |
| 交付报告存在 | 通过，已读取 `docs/acceptance-P12-2-delivery-20260708.md`。 |
| 统一证据包模型存在 | 通过，`signal_miner/connectors/source_acquisition.py` 中存在 `AcquisitionEvidence`、`EvidencePackageError`、`batch_to_ingest_payloads`。 |
| 首批适配器文件存在 | 通过，GitHub、博客园、B 站、搜索、通用适配器均存在。 |
| 证据包转 ingest payload 调用 P12-1 URL 校验 | 通过，`to_ingest_payload()` 调用 `validate_required_source_url()`。 |
| P12-2 单测 | 通过，`.venv/bin/python -m pytest tests/test_source_acquisition_contract.py -q` 输出 `27 passed`。 |
| P12-1 回归 | 通过，`.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q` 输出 `28 passed`。 |
| 连接器/证据链回归 | 通过，`.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` 输出 `25 passed`。 |
| PRD 回归 | 通过，`.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` 输出 `18 passed`。 |
| 前端语法 | 通过，`node --check frontend/static/app.js` 退出码 0。 |
| 空白检查 | 通过，`git diff --check` 退出码 0。 |

## 阻断问题

### P1-1：交付报告未执行指令要求的 ruff 全范围命令，独立复验失败

位置：

- `docs/acceptance-P12-2-delivery-20260708.md:62`
- `signal_miner/connectors/__init__.py`
- `signal_miner/connectors/media_crawler_client.py`
- `signal_miner/connectors/platforms/bilibili.py`
- `signal_miner/connectors/platforms/douyin.py`
- `signal_miner/connectors/platforms/weibo.py`
- `signal_miner/connectors/platforms/xiaohongshu.py`

问题：

P12-2 指令要求运行：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
```

交付报告只写了 `ruff check (新增文件)`，不是指令要求的命令范围。验收方按指令重跑完整命令时失败。

证据：

```text
Found 37 errors.
```

主要错误包括：

- `W293 Blank line contains whitespace`
- `W291 Trailing whitespace`
- `I001 Import block is un-sorted or un-formatted`
- `UP035 Import from collections.abc instead`
- `F401 imported but unused`
- `ARG002 Unused method argument`

影响：

交付报告中的“ruff 通过”不代表 P12-2 指令要求的静态门禁通过。该问题属于“命令范围缩小后误报通过”。

验收要求：

按 P12-2 指令原命令完整运行并退出码为 0。不得只检查新增文件。

### P1-2：批量适配器静默跳过无 URL 条目，违背“每条数据必须有真实来源”的硬标准

位置：

- `signal_miner/connectors/platforms/search_adapter.py:78`
- `signal_miner/connectors/platforms/search_adapter.py:104`
- `signal_miner/connectors/platforms/generic_adapter.py:71`
- `signal_miner/connectors/platforms/generic_adapter.py:92`
- `tests/test_source_acquisition_contract.py:451`

问题：

`SearchEvidenceAdapter.from_search_results_batch()` 和 `GenericEvidenceAdapter.from_dicts_batch()` 在遇到缺 URL 条目时捕获 `EvidencePackageError` 并 `continue`，最终返回较短的证据包列表。测试还把这种静默跳过行为写成了期望。

这与 P12-2 目标冲突：不同网站的数据获得方法要可审计，且每条导入数据必须有真实可点击来源 URL。静默跳过会让操作者以为一批数据已经处理完，实际有条目被丢弃。

证据：

```text
GENERIC_DID_NOT_RAISE len= 1
SEARCH_DID_NOT_RAISE len= 1
```

验收要求：

批量适配器遇到任意缺 URL、错域名、搜索列表页 URL 等不合规条目时，必须抛出 `EvidencePackageError`，错误信息包含失败 index 和原因；不得静默跳过。

同时更新测试：删除“batch skips invalid”的预期，改为断言批量失败。

### P1-3：运行态验证未按指令完成，且缺少 `docs/P12-2-screenshots/` 证据

位置：

- `docs/acceptance-P12-2-delivery-20260708.md:80`
- `docs/acceptance-P12-2-delivery-20260708.md:91`

问题：

P12-2 指令要求用本地服务验证：

- 合法证据包 payload 能通过 `/feedback/ingest`。
- 搜索结果列表页 URL 会被拒绝。
- `browser_screenshot` 证据包缺截图路径和备注会被拒绝。
- 前端批量 JSON 提示能看到证据包字段。

交付报告写的是“根据代码路径推演，无需实际启动服务即可确认”，并把截图目录标为“可选”。实际检查：

```text
find docs/P12-2-screenshots -maxdepth 1 -type f -print
```

无输出。

影响：

运行态验收要求未满足。报告把“代码路径推演”当成运行态证据，和指令不一致。

验收要求：

补做本地服务/API/浏览器验收，保存证据到 `docs/P12-2-screenshots/`。若已有服务可复用，需报告具体 URL、请求体、状态码、截图/JSON 证据路径。

## 非阻断观察项

- P12-2 适配器明确标注“不真实联网，只做证据包转换”，这与本阶段指令允许范围一致。
- `AcquisitionEvidence.to_ingest_payload()` 将 `screenshot_path` / `ocr_text` 拼入 `source_note`，可用于最小审计，但后续若要结构化查询截图证据，仍需要数据库 context 字段扩展。

## 复验要求

返修后必须运行并报告以下命令完整输出/退出码：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
node --check frontend/static/app.js
git diff --check
.venv/bin/python -m pytest tests/test_source_acquisition_contract.py -q
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

还必须提供运行态证据：

- API 正例 201 或等效成功响应。
- 搜索列表页负例 422 / `EvidencePackageError`。
- `browser_screenshot` 缺截图和备注负例。
- 前端证据包字段说明截图。

## 问题统计归类

| 类别 | 数量 | 说明 |
| --- | ---: | --- |
| 回归/静态检查范围缩小导致误报通过 | 1 | 报告只跑新增文件 ruff，但指令要求全 `signal_miner/connectors`。 |
| 批量数据质量门禁错误 | 1 | 无 URL 条目被静默跳过。 |
| 运行态证据缺失 | 1 | 报告用代码路径推演替代本地服务/浏览器证据。 |
