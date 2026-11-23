# P9-2 最终验收报告：运行态数据来源点击验收

验收日期：2026-06-24

结论：通过。

## 验收范围

本次验收覆盖 P9-2 运行态点击链路：

- FastAPI 静态 SPA 原始反馈页来源链接。
- FastAPI 静态 SPA 信号页来源链接。
- FastAPI 静态 SPA 需求证据链来源链接。
- Streamlit 普通反馈来源 URL 输入。
- Streamlit 原始反馈页来源链接。
- 服务启动与清理。

## 交付报告审查

执行方报告：

- `docs/acceptance-P9-2-runtime-clickthrough.md`

报告中 API 数据链路与源码级检查基本成立，但原报告明确写明“未做浏览器截图”。这不完全满足 P9-2 指令中的运行态浏览器验收要求。因此本次 commander 复验额外启动服务并通过 Chrome 补做运行态 DOM 与截图检查。

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| FastAPI 服务启动 | 通过 | `http://127.0.0.1:8000` 正常加载静态 SPA |
| Streamlit 服务启动 | 通过 | `http://127.0.0.1:8501` 正常加载 Streamlit 应用 |
| SPA 原始反馈页来源链接 | 通过 | DOM 中存在 `🔗 查看数据来源`，`href=https://example.com/product-feedback-source` 等，`target="_blank"`，`rel="noopener noreferrer"` |
| SPA 信号页来源链接 | 通过 | DOM 中存在多条 `🔗 查看原始来源`，href 指向 douyin/kuaishou/bilibili 等来源，`target/rel` 正确 |
| SPA 需求证据链来源链接 | 通过 | 点击第一个 `🔗 追溯` 后，证据链节点出现 `查看原始来源`，href 为 `https://live.douyin.com/3881804523281514946`，`target/rel` 正确 |
| Streamlit 来源 URL 输入 | 通过 | 导入反馈页可见 `数据来源 URL（可选）` |
| Streamlit 原始反馈来源链接 | 通过 | 原始反馈页 DOM 中存在 `数据来源` 链接，href 包含 `https://example.com/product-feedback-source` 和批量导入 URL，`target/rel` 正确 |
| 服务清理 | 通过 | 8000 / 8501 均无监听进程 |

## 证据文件

- `docs/P9-2-screenshots/01-feedback-list-with-source-url.json`
- `docs/P9-2-screenshots/02-batch-import-result.json`
- `docs/P9-2-screenshots/03-evidence-trail-source-url.json`
- `docs/P9-2-screenshots/04-spa-source-link-code.txt`
- `docs/P9-2-screenshots/05-streamlit-source-link-code.txt`
- `docs/P9-2-screenshots/06-spa-feedback-runtime.png`
- `docs/P9-2-screenshots/08-streamlit-feedback-runtime.png`

## 回归确认

- 批量导入返回 `ingested` 字段，前端使用该字段。
- `source_url/external_url/video_url` 链路在 API 和 UI 层均能落到可点击链接。
- 链接新窗口打开配置正确。
- 临时服务已停止，端口已释放。

## 非阻断观察

- Chrome 在信号页全页截图时出现截图接口超时，因此信号页采用 DOM 运行态检查确认。该页链接的 DOM 属性已验证完整，不影响功能结论。
- 原交付报告的“未做浏览器截图”表述与 P9-2 指令不完全一致；本报告已用实际 Chrome 运行态复验补齐。
- 非本阶段 GitHub connector 区域仍有 `result.ingested_count` 文本，之前已标记为独立接口契约问题，未纳入 P9-2 阻断。

## 最终结论

P9-2 运行态数据来源点击验收通过。当前用户可以在主要页面直接点击进入数据来源，且关键链接具备正确的 `href`、`target="_blank"` 与 `rel="noopener noreferrer"`。

## 后续建议

下一阶段可单独验收连接器页面的数据拉取结果字段，尤其是 GitHub connector UI 中的 `ingested_count` 与后端响应字段是否一致。

