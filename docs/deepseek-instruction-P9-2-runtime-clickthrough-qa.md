# DeepSeek 执行指令：P9-2 运行态数据来源点击验收

## 任务目标

在真实运行环境中验证 P9-1 的“数据来源可点击进入”是否能被用户实际使用。重点不是继续改代码，而是启动服务、构造带来源 URL 的数据、用浏览器确认静态 SPA 与 Streamlit 页面中链接可见且可点击，并保存证据。

## 背景 / 当前状态

P9-1-fix 已通过代码级验收：

- 静态 SPA 批量导入请求体已匹配后端数组契约。
- 静态 SPA 成功提示已使用 `result.ingested`。
- Streamlit 来源链接已通过 `_render_source_link()` 做 HTML 属性转义。
- 聚焦测试与 GitHub / evidence chain 回归通过。

下一阶段需要补齐运行态证据，避免“源码存在链接”但实际页面不可见、不可展开、不可点击。

## 允许修改范围

原则上不修改业务代码。允许新增验收文档和截图：

- `docs/P9-2-screenshots/`
- `docs/acceptance-P9-2-runtime-clickthrough.md`
- 如需要，可新增一次性验证脚本到 `scripts/`，但不得改变生产逻辑。

## 禁止修改范围

- 不要修改数据库 schema。
- 不要修改 LLM、pipeline、profile 隔离逻辑。
- 不要重构前端。
- 不要把运行态缺陷直接“顺手修掉”；如发现缺陷，记录并提交返修指令。

## 验收步骤

### 1. 启动后端静态 SPA

在 `MINING/signal-miner` 中启动服务：

```bash
.venv/bin/python -m signal_miner.main --host 127.0.0.1 --port 8000 --no-reload
```

如果 8000 被占用，换 8001，并在报告中记录。

### 2. 准备测试数据

通过 API 导入至少 2 条数据：

- 普通产品反馈，带 `external_url: "https://example.com/product-feedback-source"`。
- AIGC 视频反馈，带 `video_url: "https://example.com/aigc-video-source"`。

如果需要验证信号和需求证据链，可用已有数据库数据；若没有现成数据，可以构造最小数据库记录，但必须说明方式。

### 3. 静态 SPA 浏览器验收

用浏览器访问：

```text
http://127.0.0.1:8000/
```

至少验证：

- 原始反馈页展开卡片后可见“查看数据来源”。
- 链接 href 指向导入的 URL。
- 信号页如有对应信号，可见“查看原始来源”。
- 需求候选页展开证据链后，如有 evidence link URL，可见“查看原始来源”。
- 批量 JSON 导入一条带 `source_url` 或 `url` 的数据后，导入成功且页面可见来源链接。

截图保存到：

```text
docs/P9-2-screenshots/
```

### 4. Streamlit 验收

启动 Streamlit：

```bash
streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

至少验证：

- 普通反馈手动录入页有“数据来源 URL（可选）”输入。
- 录入后原始反馈页可见来源链接。
- AIGC 视频 `video_url` 仍可作为来源链接。

### 5. 清理

验收完成后停止所有临时服务，并在报告中写明端口和清理状态。

## 验收标准

通过条件：

- 所有目标页面链接均可见。
- 链接 `href` 与导入的原始 URL 一致。
- 链接使用新页面打开，不覆盖当前应用。
- 无 URL 的数据不显示空链接、`undefined` 或异常。
- 批量导入带 `source_url/url/video_url/link` 的数据可以成功进入后端。

失败条件：

- 任一核心页面看不到来源链接。
- 链接 href 错误或为空。
- 批量导入仍失败。
- 页面出现运行时 JS 错误导致功能不可用。

## 交付报告模板

```markdown
# P9-2 交付报告：运行态数据来源点击验收

## 1. 服务信息

| 服务 | URL | 状态 | 清理状态 |
|---|---|---|---|

## 2. 测试数据

| 类型 | 来源 URL | 创建方式 | 记录 ID |
|---|---|---|---|

## 3. 浏览器验收结果

| 页面 | 链接是否可见 | href 是否正确 | 截图 |
|---|---|---|---|

## 4. Streamlit 验收结果

| 页面 | 链接是否可见 | href 是否正确 | 截图 |
|---|---|---|---|

## 5. 问题与风险

- 如无，写“无”。
```

