# DeepSeek 执行指令：P12-2 站点级真实采集适配器与证据包

## 任务目标

P12-1 已完成“导入时必须有真实可点击来源 URL”的硬门禁，但还没有解决“每个网站的数据如何真实获得”的执行层问题。

本阶段目标是建立站点级采集适配器和证据包契约，让不同网站的数据获得方法可执行、可审计、可测试，并继续保证每条导入数据都带真实可点击来源 URL。

## 背景 / 当前问题

当前系统已有：

- `signal_miner/utils/source_platforms.py`：逐平台策略、允许域名、采集方法、搜索落地页规则。
- `/feedback/ingest` 与 `/feedback/batch`：可信来源 URL 硬校验。
- 前端导入页：分平台来源选择、采集方法、来源备注。

当前缺口：

- 站点策略只是登记，尚未形成统一采集适配器接口。
- GitHub、博客园、B 站公开页、搜索结果 API/JSON、截图/OCR 类来源没有统一证据包输出格式。
- 受限网站只记录了 `browser_screenshot` 方法，但没有证据包字段来保存截图路径、OCR/人工识别说明和原始页面 URL 的绑定关系。
- 不能让后续执行 AI 用“已有来源策略”冒充真实采集完成。

## 允许修改范围

只允许修改或新增以下范围：

- `signal_miner/connectors/`
- `signal_miner/connectors/platforms/`
- `signal_miner/models/feedback.py`
- `signal_miner/utils/source_platforms.py`
- `signal_miner/routes/feedback.py`
- `frontend/static/app.js`
- `frontend/static/style.css`
- `tests/test_source_acquisition_contract.py`（可新增）
- `tests/test_feedback_ingest_source_contract.py`
- `tests/test_source_clickthrough_contract.py`
- 必要文档：`docs/acceptance-P12-2-delivery-YYYYMMDD.md`

如必须修改其他文件，必须在交付报告中单独说明理由。

## 禁止修改范围

- 不得放松 P12-1 的 URL 必填、域名匹配、搜索落地页、批量预校验规则。
- 不得伪造外部平台数据或用 `example.com`、mock、本地地址冒充来源。
- 不得绕过登录、验证码、风控、付费墙或平台反爬限制。
- 不得把“截图/OCR”写成已自动完成，除非确实实现了可运行 OCR 流程并有测试证据。
- 不得删除原始反馈来源按钮、证据链、需求追溯按钮或 AIGC 视频模式。
- 不得修改无关 PRD、发布候选、历史验收文档。

## 实现要求

### 1. 新增统一证据包模型

建立一个采集输出契约，可放在 `signal_miner/connectors/source_acquisition.py` 或等价模块中。

每条采集结果必须包含：

- `source_type`
- `external_url`
- `capture_method`
- `text`
- `subject` 可选
- `author_name` 可选
- `source_note` 可选
- `source_captured_at` 可选
- `raw_payload` 可选
- `screenshot_path` 可选
- `ocr_text` 可选

要求：

- 证据包必须能转换为 `/feedback/ingest` 或 `/feedback/batch` 可接受的 payload。
- 转换前必须调用 P12-1 的 `validate_required_source_url`，不能绕过来源校验。
- `capture_method=browser_screenshot` 时，必须有 `screenshot_path` 或明确的 `source_note`，否则拒绝。

### 2. 首批站点级适配器

实现首批低风险、可测试的适配器，不要求真实登录、不要求大规模外站抓取：

| source_type | 适配器要求 |
| --- | --- |
| `github` | 复用或包裹现有 GitHub connector，输出证据包时必须保留 issue/comment 的 `html_url`，`capture_method=official_api`。 |
| `cnblogs` | 实现公开文章 URL / API JSON 的解析适配器；无 token 时允许只解析传入样例 JSON，不访问网络。 |
| `bilibili` / `video_bilibili` | 实现公开视频 URL 证据包构造器；可接受用户提供的标题、评论文本、BV URL，不得伪造评论。 |
| `baidu_search` / `google_search` | 实现搜索结果 JSON 适配器，输入为搜索 API 返回的结果数组或手工导出的 JSON；输出必须使用每条结果的落地页 URL，不得使用搜索页 URL。 |
| `manual` / `csv` / `json` | 实现通用证据包预检，确保每条都有真实 URL 和采集方法。 |

注意：本阶段可以不真实调用外部 API，但必须把“适配器如何把真实 API/页面/截图结果转换成证据包”的路径打通并测试。

### 3. 前端最小补强

如已有导入页不足以支持证据包字段，补充最小 UI：

- 批量 JSON 提示必须列出证据包字段名。
- `browser_screenshot` 方法下必须提示填写截图路径或来源备注。
- 不得增加营销式说明页，只在导入工具界面内补充必要字段/提示。

### 4. 测试要求

新增 `tests/test_source_acquisition_contract.py`，至少覆盖：

- GitHub 样例 issue/comment 转证据包，保留 `html_url`。
- 博客园样例文章 JSON / URL 转证据包，保留 `cnblogs.com` URL。
- B 站手工视频样本转证据包，保留 `bilibili.com/video/...`。
- Google/Baidu 搜索结果 JSON 使用落地页 URL，拒绝搜索结果列表页。
- `browser_screenshot` 无 `screenshot_path` 且无 `source_note` 时拒绝。
- 证据包转 ingest payload 时调用 P12-1 URL 校验，错域名失败。

同时保留 P12-1 测试：

```bash
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
```

## 验收标准

### 语法 / 静态检查

必须运行：

```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
node --check frontend/static/app.js
git diff --check
```

### 功能验证

必须运行：

```bash
.venv/bin/python -m pytest tests/test_source_acquisition_contract.py -q
.venv/bin/python -m pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q
```

### 回归验证

必须运行：

```bash
.venv/bin/python -m pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

### 运行态验证

必须用本地服务验证：

- 一个合法证据包 payload 能通过 `/feedback/ingest`。
- 一个搜索结果列表页 URL 会被拒绝。
- 一个 `browser_screenshot` 证据包缺截图路径和备注会被拒绝。
- 前端批量 JSON 提示能看到证据包字段。

保存证据到：

```text
docs/P12-2-screenshots/
```

## 交付前质量门禁

交付报告必须包含：

- 修改文件清单。
- 证据包字段契约表。
- 首批适配器覆盖表。
- 每条命令的退出码和关键输出。
- 至少 3 个负例。
- 至少 1 个运行态正例。
- 明确说明哪些网站仍未实现真实 API/页面抓取，只是支持证据包导入。

不得把“可导入样例 JSON”表述为“已真实采集全站数据”。

## 交付报告模板

```markdown
# P12-2 交付报告：站点级真实采集适配器与证据包

交付日期：YYYY-MM-DD

## 结论

## 修改文件

| 文件 | 修改目的 |
| --- | --- |

## 证据包字段契约

| 字段 | 必填 | 说明 |
| --- | --- | --- |

## 首批适配器覆盖

| source_type | 输入 | 输出 | 是否真实联网 | 限制 |
| --- | --- | --- | --- | --- |

## 验证命令

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |

## 负例证据

| 场景 | 期望 | 实际 |
| --- | --- | --- |

## 运行态证据

## 回归确认

## 风险 / 未覆盖项
```

## 递交要求

完成后提交 `docs/acceptance-P12-2-delivery-YYYYMMDD.md`。验收方将按代码事实、测试和运行态复验，不接受只看报告通过。
