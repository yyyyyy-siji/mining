# P12-1 最终验收报告：可信来源导入硬化

验收日期：2026-07-08

结论：通过。

## 验收范围

本次验收覆盖 `docs/deepseek-instruction-P12-1-trusted-source-ingest.md` 中定义的可信来源导入硬化要求：

- 导入反馈必须有真实可点击来源 URL。
- 平台策略必须按网站单独建模，不按大类泛化。
- 单条和批量导入必须由后端硬拒绝无来源、占位来源、错平台域名和搜索结果列表页。
- 前端导入页必须显示来源必填、采集方法和逐平台采集说明。
- 原始反馈来源按钮、AIGC 视频模式和需求追溯契约不得回归。

交付报告已读取：`docs/acceptance-P12-1-delivery-20260708.md`。以下结论来自独立命令、代码事实和运行态检查，不依据交付报告自评。

## 代码事实核验

| 核验项 | 结果 |
| --- | --- |
| `signal_miner/utils/source_platforms.py` 存在逐平台策略注册表 | 通过，运行断言显示 `policy_count=42`，最低要求平台无缺失。 |
| B 站 / Google Search / 闲鱼 / GitHub / Manual 策略字段 | 通过，域名、采集方法、`allow_any_domain` 和搜索落地页规则符合预期。 |
| `/feedback/ingest` 调用 `validate_required_source_url` | 通过。 |
| `/feedback/batch` 先全量预校验，再 `zip(items, prepared_items, strict=True)` 入库 | 通过。 |
| 前端不存在“数据来源 URL（可选）” | 通过。 |
| 前端存在 `SOURCE_OPTION_GROUPS`、`SOURCE_METHOD_GUIDES`、`capture_method` 和必填 URL 文案 | 通过。 |

## 验证结果

| 命令 / 检查 | 结果 |
| --- | --- |
| `node --check frontend/static/app.js` | 通过，退出码 0。 |
| `ruff check signal_miner/routes/feedback.py signal_miner/utils/source_platforms.py signal_miner/utils/url_templates.py signal_miner/pipeline/pipeline_profile.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py` | 通过，`All checks passed!`。 |
| `git diff --check` | 通过，退出码 0。 |
| `.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q` | 通过，`28 passed`。 |
| `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 通过，`25 passed`；仅有 Starlette/httpx deprecation warning。 |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 通过，`18 passed`。 |
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | 通过。 |

## API 运行态

| 场景 | 结果 |
| --- | --- |
| `manual` 缺少来源 URL | 返回 422：`导入数据必须提供真实来源 URL，不能为空。` |
| `video_bilibili` 使用抖音 URL | 返回 422：要求 `bilibili.com` / `b23.tv`。 |
| `google_search` 使用 `google.com/search` | 返回 422：必须是搜索结果落地页。 |
| `google_search` 使用 GitHub issue 落地页 | 返回 201，证明成功路径可用。该验收临时数据 `rfb_332cc37562ab45caab8d` 已删除，`deleted_rows=1`、`found_after=False`。 |

## 浏览器运行态

运行态证据保存于 `docs/P12-1-screenshots/`，本次验收新增：

- `acceptance-import-missing-url-commander-20260708.png`
- `acceptance-feedback-source-buttons-commander-20260708.png`
- `acceptance-browser-evidence-commander-20260708.json`

浏览器 DOM 核验结果：

| 检查 | 结果 |
| --- | --- |
| 产品反馈导入页显示“真实来源 URL（必填，可点击）” | 通过。 |
| 产品反馈导入页不存在“数据来源 URL（可选）” | 通过。 |
| 产品反馈来源列表包含微博、知乎、B 站、百度/Google 搜索、淘宝/京东、闲鱼、GitHub 等 | 通过，`sourceCount=29`。 |
| 切换到 `baidu_search` 后说明变化为“保存搜索结果落地页 URL” | 通过。 |
| 缺来源 URL 点击提交，前端显示“必须提供真实可点击来源 URL” | 通过。 |
| AIGC 视频模式存在，视频链接显示必填，来源列表包含抖音、B 站、快手、小红书、优酷、爱奇艺、腾讯视频、YouTube | 通过，`sourceCount=9`。 |
| 原始反馈页仍显示来源按钮状态 | 通过，`sourceActionCount=100`，`hasSourceButtonText=true`。 |

## 回归确认

| 能力 | 结论 |
| --- | --- |
| 原始反馈来源按钮不消失 | 通过。 |
| AIGC 视频爆款挖掘不消失 | 通过。 |
| 需求追溯按钮契约未破坏 | 通过，由 `test_source_clickthrough_contract.py` 覆盖。 |
| GitHub 连接器响应契约未破坏 | 通过。 |
| PRD 生成与路由回归未破坏 | 通过。 |

## 非阻断风险

- P12-1 只完成“导入可信来源硬门禁”和“站点级策略登记”。它没有实现真实爬取、官方 API 拉取、OCR 或截图分析流水线。
- 运行态验收使用本地服务 `127.0.0.1:8000`。该服务为既有运行进程，验收未额外启动新服务，也未清理历史 P9/P10/P11 文档和其他既有脏工作区。
- 真实站点页面是否仍可打开会受登录、风控、地域和平台规则变化影响；P12-1 不主动探测外站可达性。

## 最终结论

P12-1 通过验收。

本阶段已经把“导入入口不能接受无真实来源数据”固化到后端、前端和契约测试中。下一阶段应进入 P12-2：站点级真实采集适配器与证据包落地，解决“数据如何从各网站获得”的执行层缺口。
