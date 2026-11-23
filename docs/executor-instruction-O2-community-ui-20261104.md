# O2 执行指令：网页采集预览到机会发现

日期：2026-11-04。用户要求继续已完成的 O1；本轮只解决数据入口仍需手工运行脚本的问题。

## 任务目标

产品反馈模式下，在「数据源」页完成：选择 HN/V2EX → 限量采集预览 → 人工勾选原文 → 明确点击导入 → 将实际返回的本批反馈 ID 带到「机会卡片」。采集预览本身不入库、不调用模型。保持项目通用产品机会定位，不硬编码行业。

## 背景 / 当前问题

O1 已通过 151 项相关测试及真实模型、浏览器验收。HN/V2EX 采集目前只有脚本；产品反馈页面无法直接取得第一批材料。已有 `/feedback/batch` 可以复用，但它的 `ingested` 是处理数、`duplicates` 恒为 0，底层去重可能复用旧 ID，不能向用户宣称全是新增；逐条提交也不应承诺全批原子性。

## 允许修改范围

- 新增 `signal_miner/connectors/community_samples.py`：将 O1 采集核心提取为可安装的包内模块。
- `scripts/collect_community_opportunity_samples.py`：保持 CLI 参数、输出语义、原导入路径兼容；留作 wrapper，不复制第二套核心。
- `signal_miner/routes/connectors.py`：局部新增采集预览请求/响应和端点，既有 GitHub/Webhook 行为不变。
- `frontend/static/app.js`、`frontend/static/style.css`：局部新增产品反馈社区采集面板、导入、批次跳转；导入页/机会页可增加入口提示。
- 新增 `tests/test_community_preview_routes.py` 及必要的 O2 前端契约/行为检查；原 O1 采集测试原则上不改，不放宽断言。
- `docs/delivery-O2-community-ui-20261104.md`、数据入口说明及本轮必要文档。

## 禁止修改范围

不修改 MASTER、冻结 P13 计划、数据库模型/迁移、原 runner、现有去重/聚类/金标逻辑、模型或密钥设置、业务数据库、历史测试、视频流程。不要引入自动调度、OAuth、任意 URL 爬取、候选持久化、自动运行 LLM 或完整管线。不要处理工作区历史脏改动、提交或 reset。

## 实现要求

### 后端

1. 新增 `POST /api/v1/connectors/community/preview`，自动继承现有 router 鉴权。请求字段仅允许已知选项：`source=hn|v2ex`、可选 `query`（最多200字符）、`days`（1..365，默认30）、`limit`（1..30，默认10）、`v2ex_node=qna|ideas`、`kind=both|ask|comments`。禁止未知字段（尤其 URL、输出路径、max_requests）以避免用户误以为可控制未支持能力。
2. URL 仅来自既有固定端点；禁止重定向。HN 服务端固定最多3次请求，V2EX1次，单请求设置合理超时（如8秒）；同步网络采集放线程池，不阻塞事件循环。可加整体等待上限，但不要把取消等待描述为同步线程已取消。无重试循环。
3. 返回 `items`（可直接用于现有 batch 的原文材料）和 `summary`（平台、请求/读取/返回/跳过数、跳过原因、时间/查询范围、终止原因、状态及覆盖限制）。空结果必须如实为 empty；预算提前耗尽应明确 bounded。错误以 502/504 等明确失败，不能用空列表冒充成功，不透传原始网络异常/内部配置。
4. 保持 O1 来源和时间语义：V2EX RSS 是 public_feed，不能冒称官方 API；缺 published 不得用 updated 冒充。所有返回项通过实际 IngestRequest 与来源门禁。只预览，不写 ORM/文件，不调用模型。
5. 保持 CLI 原参数、模块导入与旧测试兼容，避免应用从未打包的 scripts 引用。验证 CLI help 和包内可导入。
6. 网页入口增加最小并发保护（同一服务进程已有采集进行时明确429/忙碌，不排队无限堆积）。网页 HTTP 读取使用流式累积，HN和V2EX每响应最多2MB，超过立即停止；不得先无限读完再检查。总预算也应限制，测试证明健康请求不会被同步网络阻塞。实现以少量本地 helper 为限，不扩成通用任务框架。

### 前端

1. 仅产品反馈模式展示采集面板，放数据源页上方；默认 V2EX 问与答、30天、10条，无默认行业关键词。HN可切换帖子/评论；V2EX显示节点，并明确关键词只过滤当前订阅流。
2. 按钮先「采集预览」；显示原始标题、正文（可折叠全文）、可点击原帖链接、发布时间与采集时间（各取真实对应字段）。所有第三方内容按文本安全显示。
3. 显示真实数量、空结果/错误/预算/来源覆盖提示；用户可勾选需导入的材料，明确点击「导入所选材料」。采集不自动入库，导入不自动分析。
4. loading 禁止重复点击；改变采集条件后必须重新预览，不能把旧材料当新条件结果。任何异步回包不能写入新页面/新profile，或覆盖更新的操作。失败不显示成功，可重试；更换一批预览要清晰替换当前批。
5. 导入调用现有 `/feedback/batch`。结果显示「已处理/可用材料」等诚实措辞，不使用旧计数字段声称“新增N条、无重复”。导入时保留原始字段，URL/正文不能被页面重构丢失。重复点击同一成功批次导入应禁用。
6. 导入成功后出现「用本批材料发现机会」；按实际 `feedback_ids` 与对应材料建立 O1 session 的 selected map（按 ID 去重，最多30），显式按钮后跳转 `#opportunities`。不依赖最近一页/全库，不自动消费模型。替换已有选择/结果时文案清楚；旧预览和人工备注属于会话态，不伪称持久化。
7. 已有 GitHub/Webhook、手工导入、O1 机会卡片、视频模式保持可用。没有增加新网站或泛化采集平台。
8. 底层去重可能把不同原帖的相同文本映射到已有ID，已有记录的来源未必等于本次预览。向机会页交接时，必须按返回的唯一ID读取现有 `GET /feedback/{id}`，以实际已存记录构建选择（校验product_feedback），不可把本次预览URL贴到旧ID上。若回读失败，保留成功导入结果并允许重试交接，不为此再次导入，也不悄悄分析其他材料。可用材料数按唯一实际ID显示；不扩范围修改旧去重策略。

## 验收标准

### 语法 / 静态检查

本轮新/改 Python 文件 Ruff、编译通过；`node --check frontend/static/app.js`；CLI `--help` 成功。历史 Streamlit F841 不扩范围修改，也不宣称工作区全量 lint clean。

### 功能验证

- 离线路由测试：鉴权（无key拒绝、有key接受）、有效两源、边界及未知字段422、请求预算/超时/无重定向、网络失败非成功、empty/bounded状态、字段来源/时间不漂移、来源门禁、预览临时库全表不变。
- 至少一次真实 API 采集（两源各少量）、实际反馈导入契约；Commander 会在单独临时库/浏览器独立做预览→勾选→导入→本批选择验证。
- 合理前端契约或最小行为测试验证转义、跨页/跨模式异步响应保护、导入后不自动调用 discover、本批 ID 精确传递；不写照抄实现的无效测试。

### 回归验证

```bash
.venv/bin/python -m pytest tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q
```

### 交付前质量门禁

每条命令检查退出码；mock 不写作 LIVE。时间字段混用是 O1 发现的缺陷，本轮必须保留其回归，不得删除断言。数量/来源/状态来自真实响应；采样数不写成独立用户数或已验证市场需求。报告仅列本轮范围，不把历史整个 diff 作为贡献。

## 交付报告模板

说明最终行为、改动文件及范围；逐项列命令/退出码/结果；列 LIVE 与 mock 边界；说明网络/来源覆盖、会话状态、导入去重计数限制。写明没有修改业务库/密钥/冻结需求。无需创建PR或提交。完成后向 Commander 回报，不自行宣告正式 P13 阶段通过。
