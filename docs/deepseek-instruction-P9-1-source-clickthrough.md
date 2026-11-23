# DeepSeek 执行指令：P9-1 数据来源可点击进入

## 任务目标

补齐 SignalMiner 中“数据来源需要直接能够点击进入”的优化。完成后，用户在主要前端页面查看原始反馈、信号、机会卡片、需求候选和证据链时，只要后端数据中存在 `external_url`、`source_url` 或可解析的视频链接，就必须能看到明确的可点击入口，并能在新页面打开原始来源。

## 背景 / 当前问题

当前后端已经具备一部分 URL 透传能力：

- `signal_miner/routes/feedback.py` 支持 `external_url` / `video_url`，并在列表中返回 `external_url` 与 `source_url`。
- `signal_miner/routes/signals.py` 会从父级 `RawFeedbackRow` 解析 `source_url`。
- `signal_miner/pipeline/evidence.py` 会把 `RawFeedbackRow.external_url` 写入证据链。
- `signal_miner/routes/assets.py` 的 `/requirements/{req_id}/evidence-trail` 会返回 evidence link 的 `external_url`。
- Streamlit 前端已有部分链接展示。

但完成度不一致：

- FastAPI 默认挂载的静态 SPA `frontend/static/app.js` 没有完整消费这些 URL：
  - 原始反馈列表没有展示来源链接。
  - 信号列表没有展示 `source_url`。
  - 机会卡片没有展示 supporting evidence 的来源链接。
  - 需求证据链接口返回了 `external_url`，但页面没有渲染可点击链接。
- Streamlit 前端 `frontend/app.py` 普通产品反馈手动录入没有“数据来源 URL”输入项，只能在批量导入或 AIGC 视频模式带入 URL。
- `/requirements/{req_id}/evidence-trail` 当前只返回 `external_url`，没有统一返回 `source_url`，如果未来只靠 `(source_type, external_id)` 解析 URL，前端无法稳定使用统一字段。

本阶段只做这项能力闭环，不做视觉大改版、不重构业务管线。

## 允许修改范围

仅允许修改以下文件或新增紧密相关测试：

- `frontend/static/app.js`
- `frontend/app.py`
- `signal_miner/routes/assets.py`
- 如确需新增或调整后端测试，可修改：
  - `tests/test_evidence_chain.py`
  - `tests/test_prd_routes.py`
  - `tests/test_github_connector.py`
  - 或新增一个聚焦 URL 透传的测试文件
- 如确需新增轻量前端验证脚本，可放在 `tests/` 或 `scripts/`，但不要引入新前端框架。

## 禁止修改范围

不得修改以下内容：

- 数据库 schema / Alembic 迁移，除非发现当前 schema 完全无法存储 URL；按现状不需要。
- LLM prompt、抽取逻辑、聚类逻辑、PRD 生成逻辑。
- pipeline profile 隔离逻辑。
- API 鉴权逻辑。
- 样本数据大规模重写。
- CSS 大规模重构或整体 UI 风格重做。
- 不要把静态 SPA 替换成新框架。

## 实现要求

### 1. 静态 SPA：手动导入支持来源 URL

文件：`frontend/static/app.js`

在“手动输入反馈”表单中新增一个可选输入框：

- 中文标签建议：`数据来源 URL（可选）`
- 字段 ID 建议：`import-external-url`
- 提交 `/feedback/ingest` 时，如果用户填写了该字段，则在 payload 中传入 `external_url`。
- 为空时不要传空字符串，传 `undefined` 或不传字段。

批量 JSON 导入也要兼容常见字段名：

- `external_url`
- `source_url`
- `url`
- `video_url`
- `link`

导入到 `/feedback/batch` 时统一写入 `external_url`。

### 2. 静态 SPA：原始反馈列表展示来源链接

文件：`frontend/static/app.js`

在“原始反馈”页每张反馈卡片展开内容中：

- 优先使用 `fb.source_url`。
- 如果没有，则 fallback 到 `fb.external_url`。
- 如果存在 URL，渲染为 `<a href="..." target="_blank" rel="noopener noreferrer">查看数据来源</a>` 或显示原始 URL。
- 链接必须出现在展开后的详情中，不能只存在于隐藏数据里。

### 3. 静态 SPA：信号列表展示原始来源链接

文件：`frontend/static/app.js`

在“提取信号”页每个信号卡片中：

- 使用 `sig.source_url` 渲染可点击链接。
- 如果没有 URL 但有 `sig.source_type`，保留来源平台文字说明。
- 链接文案建议：`查看原始来源`。

### 4. 静态 SPA：机会卡片展示 supporting evidence 来源链接

文件：`frontend/static/app.js`

当前机会卡片列表只展示摘要。需要在展开机会卡片时补充证据链来源入口：

- 可以在用户展开时调用 `GET /api/v1/opportunities/{id}` 获取详情，或在渲染时按需拉取详情。
- 渲染 `supporting_evidence` 中每条证据的：
  - quote 或 signal_summary
  - source_type
  - signal_id
  - `external_url` 或 `source_url` 的可点击链接
- 如果证据中没有 URL，不要显示空链接。

注意：不要为每个机会在列表初次加载时无控制地并发打大量详情请求；优先 lazy load。

### 5. 静态 SPA：需求证据链展示来源链接

文件：`frontend/static/app.js`

`loadEvidenceChain(reqId)` 已调用 `/requirements/{reqId}/evidence-trail`，该接口返回的每个 link 中已有 `external_url`。

需要在每个 evidence node 中：

- 优先取 `link.source_url`。
- fallback 到 `link.external_url`。
- 有 URL 时渲染可点击链接，文案建议：`查看原始来源`。
- 链接使用 `target="_blank"` 和 `rel="noopener noreferrer"`。

### 6. Streamlit：普通反馈手动录入支持来源 URL

文件：`frontend/app.py`

在普通产品反馈模式的手动录入表单中增加可选输入：

- 中文标签建议：`数据来源 URL（可选）`
- 英文标签建议：`Source URL (Optional)`

提交 `/feedback/ingest` 时：

- 如果填写，则传 `external_url`。
- AIGC 视频模式保留现有 `video_url` 行为；如同时新增 `external_url`，需保证 `video_url` 仍能 fallback 为来源 URL。

### 7. 后端：需求证据链统一返回 source_url

文件：`signal_miner/routes/assets.py`

在 `/requirements/{req_id}/evidence-trail` 的 `evidence_links` 中增加 `source_url` 字段：

- 如果有 `RawFeedbackRow`，使用 `resolve_source_url(source_type=rfb.source_type, external_id=rfb.external_id, external_url=rfb.external_url, context=rfb.context if dict else {})`。
- 如果没有 RawFeedbackRow，则 fallback 到 `link.get("source_url")` 或 `link.get("external_url")`。
- 保留现有 `external_url` 字段，避免破坏已有前端。

### 8. 安全与渲染要求

- 前端插入 URL 时至少要避免明显破坏 HTML 属性。若继续使用字符串模板，需对 href 值做最小 HTML attribute escaping，或使用 DOM API 创建 `<a>`。
- 不要把用户反馈正文未经处理地扩大为新的 `unsafe_allow_html` 面。
- 不要引入复杂 sanitization 库，除非项目已有依赖。

## 验收标准

### 语法 / 静态检查

在 `MINING/signal-miner` 目录执行：

```bash
python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
ruff check signal_miner tests
```

期望：

- `compileall` 无语法错误。
- `node --check` 无语法错误。
- `ruff check` 无新增错误。

### 功能验证

至少完成以下验证，并在交付报告中贴出证据：

1. 单条反馈导入 payload 支持 `external_url`：
   - 手动录入静态 SPA 能把输入 URL 提交到 `/feedback/ingest`。
   - Streamlit 普通反馈模式能把输入 URL 提交到 `/feedback/ingest`。

2. 批量 JSON 导入支持多字段来源 URL：
   - `url`
   - `source_url`
   - `video_url`
   - `link`

3. API 返回链路：
   - `GET /feedback` 返回 `external_url` 和/或 `source_url`。
   - `GET /signals` 返回 `source_url`。
   - `GET /requirements/{id}/evidence-trail` 每条 evidence link 返回 `source_url`，并保留 `external_url`。

4. 静态 SPA 可视化入口：
   - 原始反馈展开后能点击“查看数据来源”。
   - 信号卡片中能点击“查看原始来源”。
   - 机会卡片 supporting evidence 中能点击“查看原始来源”。
   - 需求证据链每条有 URL 的证据能点击“查看原始来源”。

### 回归验证

必须确认以下行为不被破坏：

- 无 URL 的反馈仍可正常导入和展示，不出现 `undefined`、空链接或异常。
- 原有 `video_url` 仍可作为 AIGC 视频来源链接。
- `pipeline_profile` 过滤不受影响。
- GitHub connector 的 `external_url` 映射仍通过测试。
- 证据链完整性验证仍通过。

建议执行：

```bash
pytest tests/test_github_connector.py tests/test_evidence_chain.py tests/test_prd_routes.py -q
```

如果新增了 URL 透传测试，也必须执行新增测试。

## 交付报告模板

请按以下格式提交交付报告：

```markdown
# P9-1 交付报告：数据来源可点击进入

## 1. 变更摘要

| 文件 | 变更内容 | 说明 |
|---|---|---|

## 2. 功能完成情况

| 验收项 | 状态 | 证据 |
|---|---|---|
| 静态 SPA 手动导入 external_url | ✅/❌ | |
| 静态 SPA 批量导入 URL 字段兼容 | ✅/❌ | |
| 原始反馈可点击来源 | ✅/❌ | |
| 信号可点击来源 | ✅/❌ | |
| 机会 supporting evidence 可点击来源 | ✅/❌ | |
| 需求证据链可点击来源 | ✅/❌ | |
| Streamlit 普通反馈 external_url 输入 | ✅/❌ | |
| `/requirements/{id}/evidence-trail` 返回 source_url | ✅/❌ | |

## 3. 验证命令

```bash
# 粘贴实际执行命令和关键输出
```

## 4. 回归确认

| 回归项 | 状态 | 说明 |
|---|---|---|

## 5. 风险与遗留问题

- 如无遗留问题，写“无”。
- 如未能完成某项，必须说明原因、影响范围和建议修复方式。
```

