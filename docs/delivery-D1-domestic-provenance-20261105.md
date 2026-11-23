# D1 交付：国内来源可追溯接入准备

日期：2026-11-05。本文件为独立 Executor 交付声明，正式结论以 Commander 验收为准。

## 结果与本轮边界

完成“国内检索准备 → 区分线索/原文 → 明确导入原文 → 留存来源快照 → 正文引用及快照下载”的最小流程。知乎没有真实账号/Access Secret，本轮**没有执行带凭据的真实知乎搜索**，未把 mock、文档实读或配置存在写成知乎采集成功。

本轮没有修改 MASTER、P13 冻结计划、数据库结构/迁移、用户业务库、`.env` 或已有密钥；没有登录、创建账号、申请平台权限、安装爬虫或提交 Git。工作区本轮前已有大量脏改动，整个 diff 不代表本轮贡献。runner 只修改 `ingest_feedback` 的幂等/旧记录兼容及唯一约束冲突处理，其他 pipeline 逻辑不动。

## 文件范围

| 文件 | 最终行为 |
| --- | --- |
| `signal_miner/utils/source_evidence.py` | 版本化来源包、正文/快照 SHA-256、源感知身份 key、完整性重算与安全导出 |
| `signal_miner/routes/feedback.py` | 接收真实 ID/源时间/父对象/内容性质等字段；原文导入门槛；来源包、详情与快照端点 |
| `signal_miner/pipeline/runner.py` | 仅 ingest 精确幂等、保守旧 key 兼容、并发唯一约束重试回读 |
| `signal_miner/pipeline/opportunity_discovery.py` | 单一正文字段引用、摘要/精选评论/完整性失败排除、证据溯源字段 |
| `signal_miner/connectors/source_acquisition.py` | 原始 payload、采集时间、OCR/截图、对象/父对象字段结构化无损转换 |
| `signal_miner/connectors/community_samples.py` | HN/V2EX 真实对象 ID/时间/内容性质；明确标题单独成为正文的来源，Atom summary 不冒充 content |
| `signal_miner/connectors/zhihu_search.py` | 新增固定官方搜索适配器，仅产生检索线索，不入库/不调用模型 |
| `signal_miner/routes/connectors.py` | 知乎受鉴权保护的状态和线索预览端点，复用 O2 网络预算/并发锁 |
| `signal_miner/settings.py` | server-only `ZHIHU_ACCESS_SECRET`，`SecretStr` 且 repr 隐藏 |
| `signal_miner/utils/source_platforms.py` | 知乎来源明确允许 official_api，不借 custom 绕过 |
| `frontend/static/app.js`、`style.css` | 未配置状态、摘要/精选评论区、补原文、来源字段、完整快照与证据导出 |
| `tests/test_source_evidence_D1.py` | 35 项来源/幂等/快照/候选语义测试，真实临时 SQLite |
| `tests/test_zhihu_search_preparation.py` | 75 项明确 OFFLINE 的知乎适配/错误/安全/鉴权测试 |
| `tests/d1_source_frontend.test.cjs`、`tests/test_d1_source_frontend.py` | 10 项新 SPA 行为检查及 pytest wrapper |
| `docs/domestic-source-preparation-D1.md` | 来源取得方式、缺凭据准备和追溯操作说明 |

旧测试没有删除、放宽或修改断言。

## 来源包与身份语义

- 包在 `context.source_evidence` 中，版本 `source-evidence/v1`。记录平台/实体、external_id、原始 URL、父帖/父评论身份、定位等级、内容性质/覆盖、源创建/更新时间、真实采集时间、留存时间、采集方式/版本、作者、截图/OCR、备注和原始 payload。
- 源时间填写时必须含时区，统一 UTC；未知作者/时间保留未知，不借父帖属性，不把服务器留存时间充当发布时间。SQLite 回读丢时区后按新入库已统一 UTC 的语义校验，防止正常回读误报 hash 变化。
- 服务端计算正文 SHA-256 和覆盖来源/正文/原始 payload/作者/采集上下文的快照 SHA-256。调用方不能指定“已核验”状态。`verified` 只表示**留存完整性一致**；包中真实性始终 `not_verified`。
- 对正文、URL、raw payload、作者、来源备注/字段或来源包的修改/删除都会导致核对失败。新 key 记录的来源包整体丢失也报 mismatch；历史旧记录缺包则明确 not_recorded，不补造、不批量修复。
- 新幂等 key 包含 profile、平台/实体、自身及父对象身份、稳定来源 URL 和精确正文；不把抓取时间、SearchHashId、请求 ID、整份变化的原始响应混入幂等身份。同对象重复采集保留第一次留存记录；正文变更新增一条，旧记录不覆盖。
- 即使调用方提供 external_id，也始终纳入稳定来源 URL，避免 manual/custom 未填平台时，同 ID/同文跨页或跨域误合并。仅去除已知 `utm_*` 跟踪 query；HN 的 `id`、其他身份参数和 fragment 均保留。原始完整 URL 仍存档不改写。
- 旧 text-only key 仅在原 URL/profile/精确正文/自身 ID/平台/实体/父对象与定位均匹配时保守复用。评论没有自身 ID 时不复用旧 key，无法确定同对象就新增。命中唯一约束时 rollback 后回读并发先提交的同 key 记录，不绕过索引。

## 原文门槛与页面

`product_feedback` 普通导入明确拒绝 `api_excerpt` / `curated_comment`（422），提示补充原文，避免旧 pending 管线误把摘要当原文。候选服务也防御性过滤已存在的这些材料及快照不一致材料。

引用只匹配该对象的一个正文字段，返回 `quote_field`；不拼 subject、父标题或模型生成标题，也不因标题存在而放行缺正文材料。真实 title-only HN 来源会把真实标题显式记录为正文且 `text_origin=title`，不混淆生成标题。

候选证据包含 feedback_id、quote、quote_field、原 URL、实体/父对象、定位/性质、源创建/采集时间、snapshot_hash/status。只有父页面的评论显示“仅定位父页面”。反馈/候选可以请求快照并下载完整 JSON；新快照响应的状态覆盖先前详情标签，避免陈旧 verified 展示。

原文录入默认 manual_text / user_provided / unknown 定位，说明人工提供未联网核验；空作者不再伪造“匿名”已知作者。可填写评论 ID、父页、含时区源时间、截图/OCR 等。保留 O2 实际 ID 回读、去重交接和异步过期保护。Question 检索线索在补原文时映射 post，原始官方 ContentType 保留。

## 知乎准备接口

- `GET /api/v1/connectors/zhihu/status`：只返回 configured、能力/限制、官方申请入口、本机配置说明；不读取知乎网络，不返回 Secret。
- `POST /api/v1/connectors/zhihu/preview`：`query` 必填 1..200 字，`count` 默认 5、最多 10，`days` 1..365、默认 30。缺 Secret 503，零上游请求。
- 固定 GET `https://developer.zhihu.com/api/v1/content/zhihu_search`，Bearer Secret 和秒级 `X-Request-Timestamp` 只在服务端请求头。Query/Count 与 `CreateTime:desc:(from,to)` 单次请求，不重定向/分页/重试；复用 O2 单进程锁、流式字节和等待预算。
- HTTP/业务 Code 分别判断参数、鉴权、限流和上游失败，不用 empty 掩盖错误。URL 限真实问答/文章路径并核对 ContentID，原始带追踪参数 URL 仍保留。
- ContentText 明确为 API 摘要；CommentInfoList 仅精选内容字符串，不补造评论 ID/作者/时间。保留完整 item、SearchHashId、Query/Count/SortBy、真实创建/更新时间、采集时间和摘要 SHA。上游出现密钥回显/鉴权字段时整次拒绝，避免导出携带 Secret。
- 网页线索只预览/下载 JSON/打开来源/跳补原文，不自动导入或分析，不把摘要填进原文框。缺 Secret 时说明申请入口及服务器环境变量配置，本轮不要求用户现在去申请。

## 验证记录

最终完整回归命令：

```bash
.venv/bin/python -m pytest tests/test_source_evidence_D1.py tests/test_zhihu_search_preparation.py tests/test_d1_source_frontend.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_community_preview_routes.py tests/test_community_preview_frontend.py tests/test_feedback_ingest_source_contract.py tests/test_source_acquisition_contract.py tests/test_source_clickthrough_contract.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_pipeline.py tests/test_pipeline_integration.py tests/test_connector_response_models.py tests/test_connectors.py tests/test_auth.py tests/test_embedding_safety.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q
```

退出 **0**，**378 passed in 5.98s**。包含本轮 111 项 pytest（35 核心、75 知乎、1 前端 wrapper）和 267 项相关旧回归。一个已有 Starlette/TestClient 弃用警告，无失败。

```bash
node --test tests/d1_source_frontend.test.cjs tests/community_preview_frontend.test.cjs
```

退出 **0**，**21/21 passed**（D1 10 + O2 11）。离线执行实际 SPA 函数，覆盖状态缺失、摘要安全展示/下载、补原文空正文、源字段和时区、快照最新状态、父页定位、Question 映射及跨页/profile 异步保护；不替代浏览器布局验收。

本轮 10 个新/改 Python 应用文件和 3 个新增 Python 测试运行 Ruff 退出 **0**；应用文件 py_compile 退出 **0**；app.js 和 D1/O2 CJS 的 node --check 退出 **0**；原 CLI `--help` 退出 **0**。历史 Streamlit F841 不在本轮修改范围，不宣称整个脏工作区 lint clean。

### 发现问题与修复

1. 开发初稿已补齐完整快照中的作者/截图/OCR/备注，并加入采集上下文 hash，防止删除某个 context 字段绕过核对。
2. Commander 预审发现 external_id 存在时原 URL 被忽略。修复为来源 URL 始终参与幂等，增加 manual/custom 同 ID 跨域/跨页、UTM 变化和 HN query 身份测试。
3. Commander 预审发现旧 key 兼容遗漏父评论。修复为所有父对象及定位严格比较，缺自身 ID 的评论不复用旧 key，并加入临时库回归。
4. 前端 Question 值与原文实体枚举不一致，已映射 post 并保留原始官方 item。
5. Commander 浏览器收尾发现配置说明重复、能力/限制显示 JSON 数组。已改为单次配置提示与正常逐条文本，未改变接口或核心逻辑；新旧 Node 仍 21/21，相关前端 pytest 24 passed。

### 2026-11-06 人工采集方式默认值修正

Commander 最后浏览器核对发现，人工录入页的空方法选择会回落到平台方法数组首项，微博因此默认 crawler。按唯一收尾指令，只修改 `frontend/static/app.js`、新 D1 行为断言和本报告；后端、接口、旧测试、业务库、网络与密钥均未改动。

- 初始人工录入优先 `manual_browser`；知乎线索“补充原文”也显式选择 `manual_browser`。
- 用户主动选择 crawler/official_api 等方式，切换来源后仍合法时保留；不合法时优先回到人工浏览，不用数组首项冒充真实采集方式。没有禁用真实程序采集方式。
- 新 D1 行为测试验证初始默认、知乎补原文提交值、显式合法选择保留和不支持时的回退。测试 DOM 对重建 select 选项时的值重置与浏览器保持一致，未修改旧 O2 测试。
- `node --check frontend/static/app.js`、`node --check tests/d1_source_frontend.test.cjs` 退出 **0**。
- `node --test tests/d1_source_frontend.test.cjs tests/community_preview_frontend.test.cjs` 退出 **0**，**22/22 passed**（D1 11 + O2 11）。
- `.venv/bin/python -m pytest tests/test_d1_source_frontend.py tests/test_community_preview_frontend.py -o addopts='' -q` 退出 **0**，**2 passed in 0.22s**。

本次仅前端默认语义收尾，按指令没有重复执行已独立验收的后端 398 项及真实 V2EX 链路。等待 Commander 重载最终 JS 核对。

随后 Commander 在新 origin 已核对默认“人工浏览记录”，而旧 origin 普通刷新仍命中旧资源缓存。按追加授权，仅将 `frontend/static/index.html` 的 JS/CSS query 版本统一改为 `20261106-d1-source-provenance`，让入口请求本轮新资源；未增加缓存框架或修改后端。静态检查确认两个引用均使用新版本，原旧版本号已不在入口中，退出 **0**；等待旧 origin 重载复核。

## 离线/LIVE 边界和验收复现

本执行者新增测试全部明确 OFFLINE/临时数据库，未执行真实知乎接口、未写用户业务库，也未把有密钥 mock 当作实网验证。官方公开文档读取只是接口资料证据，不是用户材料采集。

Commander 将用独立临时库和已有真实 V2EX 路径验证“预览→导入→快照→正文引用”及新浏览器页；其结果应记录在独立验收报告，本执行报告不提前代签通过。

临时服务可沿用本机已有文本模型配置，仅覆盖数据库与端口：

```bash
DATABASE_URL=sqlite+aiosqlite:////tmp/mining-d1-review-new.sqlite .venv/bin/python -m signal_miner.main --host 127.0.0.1 --port 18805 --no-reload
```

先打开“数据源”确认知乎未配置、没有示例笔记；V2EX 少量真实预览后明确导入，在反馈/机会页下载来源快照并核对留存完整性。API 详情与 `GET /api/v1/feedback/{id}/source-snapshot` 应返回相同身份和原始 payload。修改临时库正文/URL/raw payload 后，快照应 mismatch，候选明确排除。原文标题和正文分开，选主体正文生成一次离线候选可验证 quote_field；真实模型质量另按使用验收判断。

未来有知乎账号/Secret 后，在本机服务端设置 `ZHIHU_ACCESS_SECRET` 并重启，再进行单独真实授权运行验收。当前没有凭据，准备完成与真实运行验证严格区分。来源哈希仅说明本地留存完整性，不能认证平台、代替真实人工核实或证明市场需求。
