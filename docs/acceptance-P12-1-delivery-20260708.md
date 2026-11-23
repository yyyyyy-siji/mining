# P12-1 交付报告：可信来源导入硬化

交付日期：2026-07-08

## 结论

- 自评结论：通过。
- 仍需验收方复核：是。
- 验收依据：代码事实、自动化测试、API 运行态返回、浏览器运行态截图。

## 修改文件

| 文件 | 修改目的 |
| --- | --- |
| `signal_miner/utils/source_platforms.py` | 新增逐平台来源策略、允许域名、数据获得方法、搜索落地页规则和 URL 校验。 |
| `signal_miner/routes/feedback.py` | `/feedback/ingest` 与 `/feedback/batch` 增加真实来源 URL 硬门禁，批量导入先全量预校验再入库。 |
| `signal_miner/utils/url_templates.py` | 扩展平台显示名与占位/本地 URL 过滤。 |
| `signal_miner/pipeline/pipeline_profile.py` | 扩展产品反馈与 AIGC 视频模式可选来源类型。 |
| `frontend/static/app.js` | 导入页改为平台分组、真实 URL 必填、采集方法选择、逐平台说明、批量 URL 预校验。 |
| `frontend/static/style.css` | 增加来源采集说明提示样式。 |
| `frontend/static/index.html` | 更新静态资源缓存版本。 |
| `tests/test_feedback_ingest_source_contract.py` | 新增后端可信来源契约测试。 |
| `tests/test_source_clickthrough_contract.py` | 增加前端导入页可信来源契约断言。 |
| `docs/P12-1-screenshots/` | 保存浏览器运行态证据截图。 |

工作区说明：当前仓库在本阶段前已存在多项历史修改和未跟踪验收文档；本报告只声明上表中 P12-1 相关交付范围。

## 平台策略矩阵摘要

| 类别 | 覆盖平台 | URL 规则 | 数据获得方法 |
| --- | --- | --- | --- |
| 视频 / 短视频 | 抖音、B 站、快手、小红书、优酷、爱奇艺、腾讯视频、YouTube | 视频页 / 评论所在页，按平台域名匹配 | 官方 API、公开页采集、浏览器截图/OCR、人工浏览，按站点单独限制 |
| 博客 / 社区 | 微博、知乎、CSDN、掘金、博客园、微信公众号、贴吧 | 文章 / 回答 / 帖子 / 笔记详情页 | 官方 API、公开页采集、浏览器截图/OCR、人工浏览 |
| 搜索引擎 | 百度、搜狗、360、Google、Bing | 必须是搜索结果落地页，不接受搜索结果列表页 | 官方 API、人工浏览、浏览器截图/OCR |
| 购物 / 评价 | 淘宝、天猫、京东、拼多多、应用商店评价 | 商品页 / 评价页 | 官方 API、浏览器截图/OCR、人工浏览，按站点单独限制 |
| 二手交易 | 闲鱼、转转、爱回收 | 商品页 / 报价页 | 官方 API、浏览器截图/OCR、人工浏览 |
| 海外 / 研发 | GitHub | issue / discussion / PR / comment 的 `html_url` | 官方 API、人工浏览 |
| 自定义 / 内部 | manual、CSV、JSON、API、Webhook、客服工单 | 允许任意真实 http(s) 原始页或源系统可点击 URL | 人工浏览、Webhook、官方 API |

## 后端硬门禁实现

- 单条导入：`external_url` 或视频模式 `video_url` 必须解析成真实 URL，否则返回 422，且不调用入库 runner。
- 批量导入：先预校验全部 item；任意一条失败时整批拒绝，并返回“第 N 条数据来源不合格”。
- 平台域名匹配：如 `video_bilibili` 只接受 `bilibili.com` / `b23.tv`。
- 搜索规则：`google_search` / `baidu_search` 等只接受结果落地页，不接受搜索结果列表页。
- 入库 context 记录：`capture_method`、`source_platform`、`source_url_required`、`source_url_validation`、可选 `source_note`。

## 前端导入体验

- 产品反馈模式来源按博客/社区、搜索、购物、二手、海外/自定义分组。
- AIGC 视频模式保留并扩展到抖音、B 站、快手、小红书、优酷、爱奇艺、腾讯视频、YouTube。
- “数据来源 URL（可选）”已移除，替换为“真实来源 URL（必填，可点击）”。
- 视频模式显示“视频链接（必填，真实可打开）”。
- 每个平台切换时显示独立采集说明，并同步允许的 `capture_method`。
- 批量 JSON 归一化 `external_url/source_url/url/video_url/link`，缺 URL 前端直接拒绝。

## 验证命令

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |
| `node --check frontend/static/app.js` | 0 | 无语法错误输出。 |
| `ruff check signal_miner/routes/feedback.py signal_miner/utils/source_platforms.py signal_miner/utils/url_templates.py signal_miner/pipeline/pipeline_profile.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py` | 0 | `All checks passed!` |
| `git diff --check` | 0 | 无空白错误输出。 |
| `.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q` | 0 | `28 passed` |
| `.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 0 | `25 passed`，仅有 Starlette/httpx deprecation warning。 |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 0 | `18 passed` |
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | 0 | 编译完成。 |

## 后端负例证据

| 场景 | 期望 | 实际 |
| --- | --- | --- |
| `manual` 缺少 `external_url` | 422，不入库 | `422 {"detail":"导入数据必须提供真实来源 URL，不能为空。"}` |
| `video_bilibili` 填抖音 URL | 422，不入库 | `422 {"detail":"哔哩哔哩视频 的来源 URL 必须来自对应站点域名：bilibili.com、b23.tv。"}` |
| `google_search` 填 `google.com/search` | 422，不入库 | `422 {"detail":"Google 搜索结果 的证据 URL 必须是搜索结果落地页，不能是搜索结果列表页。"}` |

## 浏览器 / 运行态证据

| 证据 | 路径 / 结果 |
| --- | --- |
| 产品反馈导入页 | `docs/P12-1-screenshots/import-product-mode.png`；包含真实来源 URL 必填、采集方法、国内平台、GitHub、Google 搜索。 |
| 百度搜索采集说明 | 浏览器 DOM 断言：切换 `baidu_search` 后说明为“保存搜索结果落地页 URL”，方法为 `official_api/manual_browser/browser_screenshot`。 |
| 缺 URL 提交拦截 | `docs/P12-1-screenshots/import-missing-url-toast.png`；toast 为“必须提供真实可点击来源 URL”。 |
| AIGC 视频模式 | `docs/P12-1-screenshots/import-aigc-video-mode.png`；包含 AIGC 视频爆款挖掘、视频链接必填、国内视频平台。 |
| 原始反馈来源按钮 | `docs/P12-1-screenshots/feedback-source-buttons.png`；运行态统计 `sourceActionCount=51`，来源按钮状态仍存在。 |

## 回归确认

| 能力 | 结果 | 证据 |
| --- | --- | --- |
| 来源按钮不消失 | 通过 | 浏览器运行态 `sourceActionCount=51`。 |
| AIGC 视频模式仍存在 | 通过 | 浏览器运行态 `selectedProfile=aigc_video` 且页面包含 `AIGC视频爆款挖掘`。 |
| 需求追溯按钮未破坏 | 通过 | `tests/test_source_clickthrough_contract.py` 中追溯按钮契约测试通过。 |
| GitHub 连接器契约未破坏 | 通过 | `tests/test_connector_response_models.py tests/test_github_connector.py` 回归通过。 |
| PRD 路由/生成回归 | 通过 | `tests/test_prd_generator.py tests/test_prd_routes.py` 回归通过。 |

## Git / 工作区状态

P12-1 相关 tracked diff 摘要：

```text
frontend/static/app.js                    | 691 ++++++++++++++++++++++++++++--
frontend/static/index.html                |   4 +-
frontend/static/style.css                 |  93 ++++
signal_miner/pipeline/pipeline_profile.py |  27 +-
signal_miner/routes/feedback.py           | 147 ++++---
```

新增未跟踪交付物包括：

- `signal_miner/utils/source_platforms.py`
- `tests/test_feedback_ingest_source_contract.py`
- `docs/P12-1-screenshots/`
- `docs/acceptance-P12-1-delivery-20260708.md`

工作区仍包含 P9/P10/P11 历史验收文档和其他既有改动，未在本阶段回退。

## 风险 / 未覆盖项

- 本阶段只做 URL 格式、占位过滤、平台域名、采集方法和搜索页规则校验，不主动访问目标站点验证页面内容是否仍可公开访问；部分平台登录/风控状态随用户环境变化。
- 截图/OCR 采集的实际 OCR 流程尚未实现为连接器，只在导入契约中记录 `capture_method=browser_screenshot`。
- 搜索引擎策略要求保存结果落地页，但还未实现自动搜索连接器。

## 需要验收方重点复核

- 批量导入是否确实没有任何无来源 item 写库。
- 搜索引擎来源是否全部使用落地页 URL。
- 国内受限平台的采集说明是否符合后续真实采集流程。
