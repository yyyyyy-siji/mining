# O2 交付：网页社区预览、勾选导入与精确本批交接

日期：2026-11-04。执行者交付声明，最终以 Commander 独立验收为准。

## 最终行为

产品反馈模式的“数据源”页顶部增加社区材料入口，默认 V2EX 问与答、30 天、10 条，无行业关键词。用户先采集原文预览，再勾选并明确导入，最后点击“用本批材料发现机会”。采集预览不入库、不调用模型；导入和交接都不自动运行分析。

导入复用现有 `/feedback/batch`。页面仅按实际回执说“已处理/可用材料”，不把现有 `duplicates=0` 当作没有重复，也不宣称新增。按 unique `feedback_ids` 回读 `/feedback/{id}` 并验证产品模式，使用实际已存正文与来源建立机会页的选择；因此文本去重复用旧 ID 时，不会把新预览 URL 错贴给旧记录。回读失败可只重试读取，不再次导入。用户点击交接前会看到替换原机会页选择、候选和人工备注的提示，仍需在机会页明确点击“发现机会”。

## 本轮范围

| 文件 | 变更 |
| --- | --- |
| `signal_miner/connectors/community_samples.py` | 将 O1 同一套采集核心移入可安装包；来源、时间、CLI 采样语义不变 |
| `scripts/collect_community_opportunity_samples.py` | 原命令和公开导入路径的兼容 wrapper，不再复制采集核心 |
| `signal_miner/routes/connectors.py` | 新增严格请求、只读预览接口、线程采集与有界网络读取；旧 GitHub/Webhook 路由不改行为 |
| `frontend/static/app.js` | 社区预览/勾选/明确导入/实际已存材料回读/本批交接；异步回包过期保护；O1 脱离页面的旧结果不能覆盖新交接 |
| `frontend/static/style.css` | 社区面板局部样式及窄屏布局 |
| `tests/test_community_preview_routes.py` | 38 项新后端业务断言 |
| `tests/community_preview_frontend.test.cjs` | 11 项针对实际 SPA 函数的离线交互测试 |
| `tests/test_community_preview_frontend.py` | 将上述 Node 行为检查纳入 pytest |
| `docs/community-data-entry-O2.md` | 网页操作、来源覆盖和会话状态说明 |

没有修改 MASTER、冻结 P13 计划、模型/迁移、runner、旧去重/聚类/金标逻辑、视频流程、模型或密钥配置、业务数据库、历史测试。没有提交、reset 或清理已有未提交改动。工作区整个 diff 包含大量历史工作，不能视为本轮贡献；Commander 已保存 O2 开工基线。

## 后端接口与边界

`POST /api/v1/connectors/community/preview` 继承原 router 鉴权。允许字段仅有：

```json
{"source":"v2ex","query":"","days":30,"limit":10,"v2ex_node":"qna","kind":"both"}
```

- `source=hn|v2ex`，`query` 最多 200 字，`days=1..365`，`limit=1..30`，`v2ex_node=qna|ideas`，`kind=both|ask|comments`；未知字段、任意 URL、路径或 `max_requests` 返回 422。
- 固定端点，禁止重定向；HN 最多 3 次请求，V2EX 1 次，无自动重试。8 秒单阶段网络超时，20 秒网络预算在请求前及每个流式数据块后检查，24 秒 HTTP 等待上限。同步网络在线程中运行，不阻塞健康请求。
- 20 秒不是线程硬终止时限：已阻塞的读仍可能等待其设置的超时。HTTP 等待超时明确说明工作可能在收尾；锁由实际 worker 在结束时释放，不会在 HTTP 504 后虚报线程取消或提前接纳新并发。
- 同一服务进程只允许一个采集，忙碌返回 429，不无限排队。多进程各有自己的保护，不宣称分布式限流。
- 通过流式累积接受数据，每响应最多 2,000,000 字节，整批最多 6,000,000 字节，超限立即停止；不先完整读取再测大小。请求 `Accept-Encoding: identity`，收到其他压缩编码时在读取前拒绝，避免单压缩块先展开再检查。
- `items` 保留原始导入字段；每项均通过真实 `IngestRequest` 与来源门禁，未执行 ingest。`summary` 来自实际采集计数，附 `published_from/published_to`。empty/bounded 如实返回；网络、内容或来源校验失败为安全 502/504，不把失败伪装成空结果，也不回传原始网络异常。
- 原 HN/V2EX 原话、平台、API/feed、发布时间与采集时间保留。V2EX 缺少真实 `published` 仍跳过，不用 `updated` 回填。

## 验证命令与结果

在本项目目录执行指定回归：

```bash
.venv/bin/python -m pytest tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q
```

退出 **0**，**189 passed in 2.23s**（38 项本轮后端 + 151 项 O1 相关回归）。

在同一组上加入 `tests/test_community_preview_frontend.py tests/test_connector_response_models.py tests/test_connectors.py tests/test_auth.py`：退出 **0**，**214 passed in 2.19s**；一个既有 Starlette/TestClient 依赖弃用警告，无失败。

```bash
node --test tests/community_preview_frontend.test.cjs
```

退出 **0**，**11/11 passed**。测试执行实际 SPA 函数，以小型离线 DOM 模拟交互；证明字段保留、文本安全、真实 ID/来源回读、30 条限制、跨条件/页面/profile/卸载的过期响应保护、只重试读取、成功批禁止再次导入、不自动调用 discover，以及旧 O1 回包不覆盖新交接；不替代浏览器布局实测。

```bash
.venv/bin/ruff check signal_miner/connectors/community_samples.py signal_miner/routes/connectors.py scripts/collect_community_opportunity_samples.py tests/test_community_preview_routes.py tests/test_community_preview_frontend.py
node --check frontend/static/app.js
node --check tests/community_preview_frontend.test.cjs
.venv/bin/python -m py_compile signal_miner/connectors/community_samples.py signal_miner/routes/connectors.py scripts/collect_community_opportunity_samples.py tests/test_community_preview_routes.py tests/test_community_preview_frontend.py
.venv/bin/python scripts/collect_community_opportunity_samples.py --help
.venv/bin/python -c 'import signal_miner.connectors.community_samples as samples; print(samples.__name__)'
```

上述命令全部退出 **0**。CLI 包内导入与原 wrapper 函数为同一对象；旧 52 项采集测试没有修改或放宽。历史 Streamlit F841 本轮未动，不宣称工作区全量 lint clean。

### 后端断言覆盖

实际鉴权缺 key/错误 key 拒绝、正确 key 接受；严格 schema 与边界；两源固定 URL/预算/超时/禁止跳转；empty/bounded 计数；来源与时间字段；真实导入门禁；安全错误；流式 2 MB 提前停止、累计预算、压缩响应读取前拒绝；慢数据块跨 deadline；采集期间健康请求可响应；第二采集 429；HTTP 504 后 worker 结束前仍 429；真实临时 SQLite 全表快照不变。

## LIVE 与模拟边界

- 本执行者的路由/模型/前端测试是明确的离线 mock；没有用 mock 宣称 LIVE 成功，没有在本轮调用真实模型。
- Commander 已独立实测两源 API 各 3 条：V2EX HTTP 200、约 1.08 秒；HN HTTP 200、约 1.44 秒。来源、日期、请求预算与临时数据库全表不变均通过，记录为 `outputs/O2/acceptance-live-preview-20261104.json`，原始结果为 `outputs/O2/live-v2ex-preview-20261104.json`、`outputs/O2/live-hn-preview-20261104.json`。
- 上述时间是一次连通性样本，不是性能保证。identity 编码加固后的独立服务复核及最终浏览器导入/交接结果，以 Commander 后续验收记录为准，不在执行报告提前认定通过。
- 实际反馈导入是用户点击后的明确动作；预览阶段不写任何业务记录。Commander's E2E 使用独立临时库，不能当作修改用户业务库。

## 复现与剩余限制

使用已配置文本模型/鉴权启动独立临时库（不改 `.env`）：

```bash
DATABASE_URL=sqlite+aiosqlite:////tmp/mining-o2-review-new.sqlite .venv/bin/python -m signal_miner.main --host 127.0.0.1 --port 18804 --no-reload
```

打开网页，产品模式进入“数据源”，保持 V2EX/qna 默认并预览，展开原文、只勾两项导入；核对回执和 GET 回读后点击交接，机会页应只有实际返回并合并后的本批 ID，不自动分析。修改条件后重新预览、切换视频模式、在请求中切页面和制造回读失败，分别核对旧结果不串页、成功批不重复导入及只重试读取。继续使用已有 Github/Webhook 或手工导入入口，行为应保持。

HN/V2EX 仍偏技术用户。V2EX 是当前单个订阅流，没有完整历史/全部评论；HN 评论覆盖整个 HN。采样数不等于独立用户数、市场规模或验证后的需求。没有自动调度、OAuth、任意站点爬取、候选持久化或正式 P13 阶段推进。预览和机会人工备注属于会话态；刷新/离开可能丢失，需导出所需清单。
