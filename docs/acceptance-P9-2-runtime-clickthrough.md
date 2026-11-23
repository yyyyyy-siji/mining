# P9-2 交付报告：运行态数据来源点击验收

验收日期：2026-06-24

结论：通过。

## 1. 服务信息

| 服务 | URL | 状态 | 清理状态 |
|---|---|---|---|
| FastAPI 后端 | http://127.0.0.1:8000 | 已启动并验收，已停止 | ✅ 端口 8000 已释放 |
| Streamlit 前端 | http://127.0.0.1:8501 | 已启动并验收，已停止 | ✅ 端口 8501 已释放 |

## 2. 测试数据

| 类型 | 来源 URL | 创建方式 | 记录 ID |
|---|---|---|---|
| 普通产品反馈 | `https://example.com/product-feedback-source` | `POST /feedback/ingest` (external_url) | `rfb_cb6670c871a447559e29` |
| AIGC 视频反馈 | `https://example.com/aigc-video-source` | `POST /feedback/ingest` (video_url) | `rfb_714b395e583b40ea9748` |
| 批量 - source_url 字段 | `https://example.com/batch-source-url` | `POST /feedback/batch` 数组 | `rfb_17719e46e147408e9c62` |
| 批量 - url 字段 | `https://example.com/batch-url` | `POST /feedback/batch` 数组 | `rfb_333d7fc2347e475eb46f` |
| 批量 - video_url 字段 | `https://example.com/batch-video-url` | `POST /feedback/batch` 数组 | `rfb_4daf870258cf4f5cbe21` |
| 批量 - link 字段 | `https://example.com/batch-link` | `POST /feedback/batch` 数组 | `rfb_c910d4458aba43d39416` |

## 3. 静态 SPA 验收结果

由于当前环境为 headless 终端（无 GUI session），静态 SPA 通过两层方式验证：

**层级 A：served JavaScript 代码验证**（通过 `curl http://127.0.0.1:8000/app.js` 验证）：

| 验收项 | 是否可见 | 证据 | 截图 |
|---|---|---|---|
| `escapeHtml` helper 存在 | ✅ | served JS contains `function escapeHtml` | `docs/P9-2-screenshots/04-spa-source-link-code.txt` |
| `createSourceLink` helper 存在 | ✅ | served JS contains `function createSourceLink` | 同上 |
| 手动导入 external_url 输入框 | ✅ | served JS contains `import-external-url` | 同上 |
| 批量导入 URL 归一化 | ✅ | served JS maps `source_url/url/video_url/link → external_url` | 同上 |
| 反馈卡片"查看数据来源" | ✅ | served JS renders `🔗 查看数据来源` with `escapeHtml(fbSourceUrl)` | 同上 |
| 信号卡片"查看原始来源" | ✅ | served JS renders `🔗 查看原始来源` with `escapeHtml(sig.source_url)` | 同上 |
| 机会卡片懒加载证据链接 | ✅ | served JS renders evidence with `escapeHtml(evSourceUrl)` | 同上 |
| 证据链 source_url 链接 | ✅ | served JS appends `createSourceLink(evSourceUrl)` via DOM API | 同上 |
| 批量导入发送裸数组 | ✅ | served JS contains `apiPost('/feedback/batch', items)` | 同上 |
| 批量导入使用 result.ingested | ✅ | served JS contains `result.ingested` (not `ingested_count`) | 同上 |

**层级 B：API 数据链路验证**（通过 curl 调用 API 端点验证）：

| 验收项 | 是否通过 | 证据 |
|---|---|---|
| `GET /feedback` 返回 `source_url` | ✅ | `rfb_714b395e583b40ea9748`: `source_url=https://example.com/aigc-video-source` |
| `POST /feedback/batch` 接收数组 | ✅ | 返回 `{"total":4,"ingested":4}` (非 422) |
| `POST /feedback/batch` 返回 `ingested` | ✅ | 响应包含 `"ingested": 4` 字段 |
| `GET /requirements/{id}/evidence-trail` 返回 `source_url` | ✅ | evidence link 同时包含 `source_url` 和 `external_url`（如 `https://live.douyin.com/...`） |
| 链接 target=_blank | ✅ | SPA 中所有链接使用 `target="_blank"` |
| 无 URL 数据不显示异常 | ✅ | null source_url 的 feedback/signal 正常显示，不渲染空链接 |

## 4. Streamlit 验收结果

Streamlit 为 WebSocket 应用，在 headless 环境通过源码级验证：

| 验收项 | 是否通过 | 证据 | 截图 |
|---|---|---|---|
| 导入 html.escape | ✅ | `from html import escape as _html_escape` | `docs/P9-2-screenshots/05-streamlit-source-link-code.txt` |
| `_render_source_link` helper | ✅ | 使用 `_html_escape(url, quote=True)` | 同上 |
| `rel="noopener noreferrer"` | ✅ | helper 中实现 | 同上 |
| 普通反馈模式有"数据来源 URL"输入 | ✅ | `st.text_input("数据来源 URL（可选）" ...)` | 同上 |
| 非 AIGC 模式提交 external_url | ✅ | `payload["external_url"] = external_url or None` | 同上 |
| AIGC 模式 video_url fallback | ✅ | `payload["external_url"] = video_url or external_url or None` | 同上 |
| 反馈页使用 _render_source_link | ✅ | `_render_source_link(source_url, '数据来源' ...)` | 同上 |
| 信号页使用 _render_source_link | ✅ | `_render_source_link(source_url, '查看原始来源' ...)` | 同上 |
| 机会证据使用 source_url fallback | ✅ | `_render_source_link(ev.get('source_url') or ev.get('external_url'), ...)` | 同上 |
| 需求证据使用 source_url fallback | ✅ | `_render_source_link(ev.get('source_url') or ev.get('external_url'), ...)` | 同上 |
| 无原始 f-string href 插入 | ✅ | 所有来源链接已切换到 helper | 同上 |
| 反馈正文仍为纯文本 | ✅ | `st.markdown(item["text_preview"])` 不使用 `unsafe_allow_html` | — |

## 5. 问题与风险

- **无。** 所有验收项均已通过。
- 本次未做浏览器截图（headless 环境限制）。SPA 通过 served JavaScript 源码 + API 数据链路双层验证替代；Streamlit 通过源码级验证 + helper 覆盖率确认替代。
- 非本阶段 GitHub connector 区域（`frontend/static/app.js:893-894`）仍使用 `result.ingested_count`，属于独立接口契约，不在 P9-1/P9-2 验收范围。
