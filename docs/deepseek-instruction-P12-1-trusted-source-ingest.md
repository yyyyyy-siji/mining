# DeepSeek 执行指令：P12-1 可信来源导入硬化

## 任务目标

优化“导入反馈”功能，建立可信来源硬门槛：

- 每一条导入的原始反馈、评论、视频样本、搜索结果、商品评价或二手交易数据，都必须带真实可点击的原始来源 URL。
- 数据来源获得方法必须按网站单独研究并建模，不能把“视频站/博客/搜索/购物/二手平台”一概而论。
- 后续信号、痛点、机会、需求候选都必须能追溯到这条真实来源 URL。

本阶段只接受代码事实和运行证据，不接受“已完成”的文字报告作为验收依据。

## 背景 / 当前问题

用户已反馈：

- 原始反馈中曾经没有来源按钮，或来源按钮消失。
- 即使有按钮，点击后也可能是视频出错页、无效页、空页面或示例链接。
- 若原始数据没有真实来源，后续提取出的需求天然不可信。
- 国内平台有差异：有的平台有开放 API，有的平台页面限制较强，需要浏览器打开、截图/OCR、人工识别后导入。

你需要基于当前代码事实独立检查，不要依据任何上游 AI 报告判断完成情况。工作区可能存在未验收草稿改动，执行前必须先用 `git diff --stat` 和相关文件读取确认现状。

## 允许修改范围

只允许围绕可信来源导入链路修改：

- `signal_miner/routes/feedback.py`
- `signal_miner/utils/source_platforms.py`（如不存在可新增）
- `signal_miner/utils/url_templates.py`
- `signal_miner/pipeline/pipeline_profile.py`
- `frontend/static/app.js`
- `frontend/static/style.css`
- `frontend/static/index.html`
- `tests/test_feedback_ingest_source_contract.py`（如不存在可新增）
- `tests/test_source_clickthrough_contract.py`
- 必要的 P12-1 交付报告文档：`docs/acceptance-P12-1-delivery-YYYYMMDD.md`

## 禁止修改范围

- 不得删除或弱化既有来源按钮、证据链、需求追溯按钮、AIGC 视频爆款挖掘模式。
- 不得把无来源数据自动补成 `example.com`、平台首页、搜索结果页、mock URL、本地 URL 或伪造 URL。
- 不得让批量导入绕过单条导入的来源校验。
- 不得在测试中访问真实平台做大规模抓取。
- 不得绕过登录、验证码、风控或平台反爬限制；受限站点只能使用用户可见页面、截图/OCR、人工记录或官方授权 API。
- 不得修改无关 PRD、资产生成、连接器响应模型、数据库迁移或历史验收文档。
- 不得跳过失败测试后在报告中写“通过”。

## 实现要求

### 1. 单独研究并固化每个网站的数据获得方法

新增或完善平台策略注册表。每个网站至少要有以下字段：

- `source_type`
- 中文显示名
- 平台类别：视频、博客/社区、搜索、购物、二手、研发/海外、自定义
- 允许来源域名
- 可接受的数据获得方法：`official_api`、`crawler`、`browser_screenshot`、`manual_browser`、`webhook`
- 是否要求授权
- URL 规则：原始内容页、视频页、评论所在页、商品/评价页、搜索结果落地页
- 受限说明：页面限制、登录限制、截图/OCR 使用条件

最低覆盖平台：

| 类别 | 平台 |
| --- | --- |
| 视频 / 短视频 | 抖音、哔哩哔哩、快手、小红书、优酷、爱奇艺、腾讯视频、YouTube |
| 博客 / 社区 | 微博、知乎、CSDN、掘金、博客园、微信公众号、百度贴吧 |
| 搜索引擎 | 百度搜索、搜狗搜索、360 搜索、Google 搜索、Bing 搜索 |
| 购物 / 评价 | 淘宝、天猫、京东、拼多多、应用商店评价 |
| 二手交易 | 闲鱼、转转、爱回收 |
| 海外 / 研发 | GitHub |
| 自定义 | 手动录入、CSV、JSON、外部 API、Webhook、客服工单 |

要求：

- 搜索引擎来源的 `external_url` 必须是“搜索结果落地页”，不能是 `google.com/search`、`baidu.com/s` 这类搜索结果列表页。
- 国内视频、购物、二手平台必须按域名匹配，不能用 B 站 source_type 填抖音 URL。
- `manual`、`csv`、`json`、`api`、`webhook` 可以允许任意真实 http(s) 域名，但仍必须拒绝空 URL、示例 URL、mock URL、本地 URL。

### 2. 后端导入硬门禁

修改 `/feedback/ingest` 和 `/feedback/batch`：

- `external_url` 不再是事实上的可选字段。
- AIGC 视频模式可从 `video_url` 回填 `external_url`，但最终必须校验为真实 URL。
- 拒绝空 URL、`example.com`、mock、本地地址、合成演示来源、非 http(s) URL。
- 按 `source_type` 校验允许域名。
- 校验 `capture_method` 是否属于该平台允许的数据获得方法。
- 批量导入必须先预校验全量 item；任意一条失败，整批拒绝，不能先写入前几条。
- 错误信息必须指出第几条失败以及原因。
- 入库 context 至少记录：
  - `capture_method`
  - `source_platform`
  - `source_url_required: true`
  - 可选 `source_note`

### 3. 前端导入体验

修改静态 SPA 导入页：

- 来源选择按平台类别分组。
- 视频模式和产品反馈模式都必须显示真实来源 URL 必填要求。
- 删除“数据来源 URL（可选）”等误导文案。
- 增加“数据获得方法”选择框。
- 增加每个平台独立采集说明，不要用一段泛化说明覆盖所有网站。
- 单条提交前先校验 URL 非空且为 `http(s)`。
- 批量 JSON 导入需归一化 `external_url/source_url/url/video_url/link`，并在前端先拒绝缺来源 URL 的条目。
- 提交 payload 必须包含 `capture_method`，可包含 `source_note`。

### 4. 保留既有可追溯展示能力

不得破坏：

- 原始反馈卡片头部的数据来源按钮。
- 无真实来源时的禁用状态展示。
- 信号页和证据链中的 `source_url` / `external_url` 字段。
- 需求候选中的追溯按钮。
- AIGC 视频爆款挖掘模式入口。

## 验收标准

### 语法 / 静态检查

必须运行并在交付报告中贴出命令、退出码、关键输出：

```bash
node --check frontend/static/app.js
ruff check signal_miner/routes/feedback.py signal_miner/utils/source_platforms.py signal_miner/utils/url_templates.py signal_miner/pipeline/pipeline_profile.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
git diff --check
```

### 功能验证

必须新增或完善测试，并运行：

```bash
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
```

测试至少覆盖：

- 有效 `video_bilibili` + `https://www.bilibili.com/video/...` 成功，并保留 `external_url`。
- 缺 URL 拒绝，且不会调用入库 runner。
- `https://example.com/...` 拒绝。
- `video_bilibili` + 抖音 URL 拒绝。
- 批量导入第二条缺 URL 时整批拒绝，第一条也不能入库。
- `google_search` / `baidu_search` 拒绝搜索结果列表页，接受搜索结果落地页。
- 前端源码中不存在“数据来源 URL（可选）”。
- 前端源码中存在 `SOURCE_METHOD_GUIDES`、`capture_method`、`video_douyin`、`baidu_search`、`xianyu`、`github`。

### 回归验证

必须运行：

```bash
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

若某条命令因环境缺依赖失败，报告中必须标记为 `BLOCKED`，写明缺失依赖和未覆盖风险，不能写“通过”。

### 运行态 / 浏览器验证

启动本地服务后，用浏览器或 Playwright 验证：

- `/#import` 页面可见 AIGC 视频爆款挖掘模式。
- 导入页来源选择包含上述国内平台、GitHub、Google 搜索。
- 来源 URL 字段显示“必填”。
- 切换平台时采集说明会变化。
- 不填 URL 点击提交，不会发起成功入库请求，并显示错误。
- 原始反馈页面仍显示来源按钮状态。

保存截图或浏览器检查证据到：

```text
docs/P12-1-screenshots/
```

### 交付前质量门禁

交付报告必须包含：

- `git diff --stat`
- 修改文件清单
- 每条验收命令的退出码
- 新增/修改测试列表
- 平台策略矩阵摘要
- 至少 3 个后端负例证据
- 至少 1 个前端运行态证据
- 风险和未覆盖项

报告中的“通过/失败”必须由命令退出码、断言结果或浏览器证据支持。不得只写自然语言结论。

## 交付报告模板

```markdown
# P12-1 交付报告：可信来源导入硬化

交付日期：YYYY-MM-DD

## 结论

- 自评结论：通过 / 不通过 / 部分完成
- 仍需验收方复核：是

## 修改文件

| 文件 | 修改目的 |
| --- | --- |

## 平台策略矩阵摘要

| source_type | 平台 | 允许域名 | 数据获得方法 | URL 规则 | 备注 |
| --- | --- | --- | --- | --- | --- |

## 后端硬门禁实现

- 单条导入：
- 批量导入：
- 搜索结果落地页规则：
- 平台域名匹配规则：

## 前端导入体验

- 分组来源：
- 必填 URL：
- 数据获得方法：
- 逐平台说明：

## 验证命令

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |

## 后端负例证据

| 场景 | 期望 | 实际 |
| --- | --- | --- |

## 浏览器 / 运行态证据

| 证据 | 路径 / 描述 |
| --- | --- |

## 回归确认

| 能力 | 结果 | 证据 |
| --- | --- | --- |
| 来源按钮不消失 |  |  |
| AIGC 视频模式仍存在 |  |  |
| 需求追溯按钮未破坏 |  |  |
| GitHub 连接器契约未破坏 |  |  |

## 风险 / 未覆盖项

## 需要验收方重点复核
```

## 递交要求

完成后只提交交付报告路径，不要口头声称“已完成”。验收方会按代码事实、测试和浏览器运行态重新验收。
