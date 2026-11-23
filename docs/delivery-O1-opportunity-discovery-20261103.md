# O1 交付：真实社区材料到候选产品机会

日期：2026-11-03。执行者交付声明，等待 Commander 独立验收。

## 范围与行为

本轮保持通用产品机会发现定位，只增加只读候选预览和有界社区材料导出。

| 文件 | 本轮变更 |
| --- | --- |
| `signal_miner/pipeline/opportunity_discovery.py` | 本批文本归纳服务；不使用 Embedding，不调用完整管线，不写 ORM/审核状态 |
| `signal_miner/routes/assets.py` | 新增显式选材 `POST /api/v1/opportunities/discover`，保留既有路由 |
| `frontend/static/app.js` | 产品机会页局部选材、分页、重试、三卡预览、来源、会话判断及 TXT 清单导出 |
| `frontend/static/style.css` | 新区域的局部响应式样式 |
| `frontend/app.py` | 产品机会页提示使用 SPA 的本批预览入口；不宣称 Streamlit 已有同等功能 |
| `scripts/collect_community_opportunity_samples.py` | HN Algolia / V2EX 单个 Atom feed 的有界只读采集，导出现有 batch API 可接受的 JSON |
| `tests/test_opportunity_discovery.py` | 30 项业务断言，包括临时数据库全表快照不变 |
| `tests/test_community_opportunity_samples.py` | 52 项离线采集、时间语义与导入契约测试 |

工作区存在大量既有未提交修改。以上是本轮新增/局部变更范围，不能把整个 `git diff` 视为本轮贡献。没有 reset、clean、checkout、创建分支、提交或修改业务数据库、密钥、顶层需求、P13 金标工具及旧管线。

### 候选发现契约

- 请求必须包含 `feedback_ids`，1–30 个不重复、确实存在且属于 `product_feedback` 的 ID。不会默认读取全库。
- 单条原文（含标题）上限 12,000 字符，本批上限 60,000 字符；超过时整批明确拒绝，不截断材料。
- 空文本/不合格来源明确列入 `excluded`；完全相同原文只分析一次，返回重复数，原记录全部保留。没有合格材料时不调用模型。
- 只调用一次运行时文本 LLM，60 秒超时；无 Embedding 的 DeepSeek 也能使用。原完整管线及其熔断保持原状。
- 最多 3 张候选，可以 0 张。字段包括标题、人群、场景、痛点、最小设想、理由、待验证问题和原文依据。没有综合分数/校准概率。
- 模型只能提供证据 ID/quote。跨批/未知 ID、未匹配原话的引用被剔除；URL/来源从合格的选中记录回填。无有效证据的卡不推荐。
- 复用 `strip_code_fences`、Pydantic 结构校验、现有确定性原话匹配和来源 URL/平台/采集方式校验。未通过结构验证的候选有明确排除信息。
- 模型或结构错误返回可重试的 502，不把提供商原始错误/密钥透传。原文仅进入文本提示的数据区，没有给模型配置工具或执行材料中指令的能力。
- 仅返回预览，不新增/修改 RawFeedback、Signal、Theme、PainPoint、Opportunity、Requirement、PipelineRun 或审核状态。不会宣告任何 P13 阶段通过。
- 页面把原话与系统归纳/方案分开，普遍性、替代方案和采用/付费意愿待验证。人工行动/备注仅保存在当前页面内存，刷新/关闭丢失，用户可下载 TXT 清单。

## 验证记录

执行目录：本项目 `signal-miner`。

```bash
.venv/bin/python -m pytest tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q
```

初次交付退出码 **0**，**140 passed in 2.17s**。首次旧静态源码契约发现机会页查询使用等价局部 `profile` 变量后，已恢复该历史查询原写法，再跑以上全部测试通过。未改旧测试。随后修复 V2EX 时间语义并增加 11 项断言，相同命令最终退出 **0**，**151 passed in 2.05s**（本轮新测试 82 项，相关旧回归 69 项）。

```bash
.venv/bin/ruff check signal_miner/pipeline/opportunity_discovery.py signal_miner/routes/assets.py scripts/collect_community_opportunity_samples.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py
node --check frontend/static/app.js
.venv/bin/python -m py_compile signal_miner/pipeline/opportunity_discovery.py signal_miner/routes/assets.py scripts/collect_community_opportunity_samples.py frontend/app.py
```

三个命令均退出 **0**。另执行 `ruff check frontend/app.py` 退出 **1**，唯一问题是本轮前已存在的第 263 行 `conf_threshold = 0.5` 未使用（F841）；本轮只在机会页增加兼容提示，未扩范围删除旧代码。此项不能记为 Ruff 全量通过。

### LIVE 与模拟边界

- **LIVE HN 采集**：`--source hn --days 30 --limit 4 --max-requests 4`，2 次请求、导出 4 条；文件 `/tmp/mining-o1-hn-live-20261103.json`，13,277 字节。
- **LIVE V2EX 采集**：`--source v2ex --v2ex-node qna --days 30 --limit 4`，1 次请求、读取当前 feed 50 条、导出 4 条，其余 46 条计入 `beyond_sample_limit`；文件 `/tmp/mining-o1-v2ex-live-20261103.json`，10,180 字节。
- 以上 8 条逐条通过真实 `IngestRequest` / `_prepare_ingest_data` 契约校验；**没有实际入库**。文件是公开社区采集样本，不是正式金标，也未评估金标授权。
- HN 为 `custom + official_api`；V2EX 为 `custom + crawler`，元数据准确标注 `public_feed`。没有为 RSS 冒称官方 API。
- 82 项新测试中的模型/HTTP 测试使用明确的 mock，只证明业务契约和错误处理；SQLite 不变性测试使用真实临时数据库。
- 真实 LLM 和浏览器端到端由 Commander 独立验收，本执行报告不把 mock 记作 LIVE 模型成功。未重复消费真实 LLM 调用。

## 可复现使用

先在不存在的新路径导出少量材料；不会自动入库、调用 LLM 或修改 `.env`：

```bash
.venv/bin/python scripts/collect_community_opportunity_samples.py --source hn --query workflow --days 30 --limit 10 --max-requests 6 --output /tmp/mining-hn-new-samples.json
.venv/bin/python scripts/collect_community_opportunity_samples.py --source v2ex --v2ex-node qna --days 30 --limit 10 --output /tmp/mining-v2ex-new-samples.json
```

输出路径父目录须已存在，文件须不存在；已有文件不会覆盖。默认每请求 10 秒，可设 1–30 秒；HN 最多 20 请求、总样本最多 100。V2EX 仅一个白名单 feed，`--query` 在这份 feed 中本地过滤，不能视为全站搜索。错误返回非零且打印采集摘要，不会写成功文件；空结果明确输出空数组及 `status=empty`。

隔离验证可用新临时库启动（保留现有文本模型及鉴权配置，不改 `.env`）：

```bash
DATABASE_URL=sqlite+aiosqlite:////tmp/mining-o1-review-new.sqlite .venv/bin/python -m signal_miner.main --host 127.0.0.1 --port 8011 --no-reload
```

浏览器验证：

1. 打开 `http://127.0.0.1:8011`，使用现有 API Key 入口（若服务有配置），选择产品反馈模式。
2. 在“数据导入”上传采集 JSON；该导入是用户明确操作。也可以人工录入可访问社区的原文及真实直达链接。
3. 打开“机会卡片”，在上方本批区域勾选材料（每页 20 条，跨页最多 30 条），点击“发现机会”。无需运行旧完整管线。
4. 核对本批数量、排除原因、原话和原始来源。检查 0 候选时的诚实提示、错误后的选择保留/重试，以及历史资产仍可展开。
5. 给候选记录“继续找用户了解/做一个小原型/放弃”和原因，下载 TXT。刷新页面确认未产生持久化候选；切换视频模式确认新入口不出现。
6. 使用测试提供商返回含 HTML 的标题/quote 验证按文字显示；不把这种模拟当作真实模型质量证明。

API 验证：向既有 `/api/v1/feedback/batch` 提交采集数组，读取其返回的 `feedback_ids`，再提交：

```json
{"feedback_ids": ["实际返回的本批ID1", "实际返回的本批ID2"]}
```

目标为 `POST /api/v1/opportunities/discover`。鉴权开启时仍要求既有 `X-API-Key`，没有新增绕过。检查模型前后的临时数据库全表快照一致；未知 ID/视频 ID 返回 422，模型失败返回 502，可重试且不留业务状态。

## Commander 复核后的修正：V2EX 时间语义

- 仅修改本轮采集脚本、对应测试和本报告。V2EX 不再用 `updated` 回填缺失的 `published`，`days` 只按有效真实发布时间过滤。
- 缺失/空白 `published` 跳过并明确记录 `missing_published_at`；无效或无时区的值记录 `invalid_published_at`。旧发布时间不会因最近编辑而变成新帖。
- `raw_payload.published_at` 是有效 `<published>` 转成 UTC 后的值；`updated_at` 和 `original.updated` 单独保留来源 `<updated>` 原值，不替代发布时间，不要求其晚于发布时间。
- 新增 11 项断言覆盖缺失/空白/无效/无时区发布时间、旧帖最近更新、时区转换、不同更新元数据、精确时间边界与未来发布时间。既有成功 fixture 改为明确包含独立 `<published>`。
- 相同全组命令 **151 passed in 2.05s，退出 0**。`ruff check scripts/collect_community_opportunity_samples.py tests/test_community_opportunity_samples.py` 和脚本 `py_compile` 均退出 **0**。
- 本次没有重新采集或修改任何 LIVE 文件，没有入库；已有 LIVE 样本含独立 `<published>`，不受此修正影响。

## 剩余限制与数据选择

- HN 和 V2EX 都偏技术用户。HN 评论来自整个 HN 讨论，不只 Ask HN；V2EX 只有当前 feed 近期帖子，未采评论、不保证覆盖指定天数的全部帖子或历史。
- 选择最近材料只能产生研究线索，不能由样本数推导独立用户数、市场规模、需求普遍性或商业价值。原话匹配也不能证明模型归纳语义正确；仍需用户核对和后续访谈/原型验证。
- URL 校验沿用现有确定性规则，没有在候选发现时联网检查页面存活。
- GitHub 匿名读取在 Commander 调研时遇到 403，稳定采集需合适只读凭据及额度；本轮未声称修复。其他中文社区/评价目前支持用户可访问的原文+链接导入，不提供自动全站采集承诺。
- 没有引入复杂评分、多人审批、版本回滚、自动调度、PRD 增强或视频理解。页面候选只在当前会话保留。
