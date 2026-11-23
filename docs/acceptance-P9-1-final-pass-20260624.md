# P9-1 最终验收报告：数据来源可点击进入

验收日期：2026-06-24

结论：通过。

## 验收范围

本次复验覆盖 P9-1 与 P9-1-fix 指令中要求的来源 URL 点击链路返修：

- 静态 SPA 批量导入请求体契约。
- 静态 SPA 批量导入成功字段。
- Streamlit 来源链接 HTML 属性转义。
- 聚焦契约测试。
- GitHub connector 与 evidence chain 回归。

## 验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| Python 语法检查 | 通过 | `.venv/bin/python -m compileall signal_miner frontend/app.py` |
| 静态 SPA JS 语法检查 | 通过 | `node --check frontend/static/app.js` |
| 限定范围 ruff | 通过 | `ruff check frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils` → `All checks passed!` |
| P9-1-fix 聚焦测试 | 通过 | `.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py -q` → `9 passed` |
| GitHub + Evidence 回归 | 通过 | `.venv/bin/python -m pytest tests/test_github_connector.py tests/test_evidence_chain.py -q` → `15 passed` |

## 回归确认

- 静态 SPA 批量导入已从 `apiPost('/feedback/batch', { items })` 改为 `apiPost('/feedback/batch', items)`。
- 静态 SPA 批量导入成功提示已读取后端实际字段 `result.ingested`。
- 批量导入仍保留 `source_url/url/video_url/link → external_url` 归一化。
- Streamlit 已新增 `_render_source_link()`，并使用 `html.escape(..., quote=True)` 处理 URL 属性。
- Streamlit 本阶段来源链接调用已切换到 `_render_source_link()`。
- `/requirements/{req_id}/evidence-trail` 已保留 `external_url` 并增加 `source_url`。

## 非阻断观察

- 旧请求体 `{ "items": [...] }` 对后端仍返回 422，符合当前后端契约；前端已改为不再发送该形状。
- `frontend/static/app.js` 其他连接器区域仍存在 `result.ingested_count`，属于非本阶段的 GitHub connector UI 字段，未作为 P9-1-fix 阻断。后续如验收连接器页面，应单独核对该接口返回结构。
- 未启动临时服务，未做浏览器截图验收。

## 最终结论

P9-1-fix 已修复初验阻断项，代码级与契约级验收通过。当前可以接受为“数据来源可点击进入”的实现闭环基础版本。

## 后续建议

下一阶段建议做运行态验收：启动 FastAPI 静态 SPA，构造带 URL 的原始反馈、信号和需求证据链数据，用浏览器确认页面上链接真实可见、可点击、目标 URL 正确，并保存截图证据。

