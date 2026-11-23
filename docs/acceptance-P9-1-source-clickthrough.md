# P9-1 验收报告：数据来源可点击进入

验收日期：2026-06-24

结论：不通过，需要返修。

## 已通过项

- `frontend/static/app.js` 已新增手动录入 `external_url` 输入框。
- `frontend/static/app.js` 已在原始反馈、信号、机会 supporting evidence、需求证据链中尝试渲染来源链接。
- `frontend/app.py` 已新增普通反馈来源 URL 输入。
- `signal_miner/routes/assets.py` 已在 `/requirements/{req_id}/evidence-trail` 中增加 `source_url` 字段。
- 限定修改范围的 ruff 检查通过：
  - `ruff check frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils`
- 语法检查通过：
  - `.venv/bin/python -m compileall signal_miner frontend/app.py`
  - `node --check frontend/static/app.js`
- 聚焦 URL 模型断言通过：
  - `IngestRequest.external_url`
  - `resolve_source_url(external_url=...)`
  - `resolve_source_url("bilibili", external_id="BV123")`

## 阻断问题

### P0-1：静态 SPA 批量导入请求体仍与后端接口不匹配

位置：

- `frontend/static/app.js`
- `signal_miner/routes/feedback.py`

问题：

静态 SPA 在批量 JSON 导入时仍调用：

```js
apiPost('/feedback/batch', { items })
```

但 FastAPI 路由签名是：

```python
async def batch_ingest(items: list[IngestRequest]) -> BatchIngestResponse:
```

该接口期望请求体直接是数组，而不是 `{ "items": [...] }`。因此静态 SPA 的批量导入会直接返回 422，无法完成“批量 JSON 中 URL 字段统一写入 `external_url`”这一验收项。

证据：

```bash
.venv/bin/python - <<'PY'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from signal_miner.routes.feedback import router

app = FastAPI()
app.include_router(router, prefix='/api/v1')
client = TestClient(app)
payload = {'items': [{'source_type': 'manual', 'text': 'hello', 'external_url': 'https://example.com'}]}
resp = client.post('/api/v1/feedback/batch', json=payload)
print(resp.status_code)
print(resp.json())
PY
```

实际输出：

```text
422
{'detail': [{'type': 'list_type', 'loc': ['body'], 'msg': 'Input should be a valid list', ...}]}
```

影响：

- 静态 SPA 批量导入不可用。
- `url/source_url/video_url/link` 字段归一化即使写了，也不会进入后端。
- P9-1 核心验收项“批量 JSON 导入支持多字段来源 URL”失败。

验收要求：

- 静态 SPA 必须按后端当前契约直接提交数组：`apiPost('/feedback/batch', items)`；或后端显式改为兼容 `{items: [...]}`。优先改前端，避免扩大接口变更。
- 成功提示必须读取后端实际字段 `ingested`，不能读取不存在的 `ingested_count`。

### P1-1：Streamlit 链接渲染未对 URL 做 HTML 属性转义

位置：

- `frontend/app.py`

问题：

新增和已有来源链接使用 `unsafe_allow_html=True`，并将 URL 原样插入 `href` 属性，例如：

```python
st.markdown(f"🔗 <a href='{source_url}' target='_blank'>...</a>", unsafe_allow_html=True)
```

P9-1 指令要求“前端插入 URL 时至少要避免明显破坏 HTML 属性”。当前实现没有做 HTML attribute escaping，也没有使用 Streamlit 原生 Markdown 链接方式，恶意 URL 字符串可能破坏属性边界。

影响：

- 不满足 P9-1 安全与渲染要求。
- 对新加的普通反馈 `external_url` 输入尤其明显，因为该字段来自用户输入。

验收要求：

- Streamlit 中新增一个小型 URL 渲染 helper，至少对 URL 做 `html.escape(url, quote=True)`。
- 所有本阶段新增或触达的来源链接统一使用该 helper。
- 链接仍需在新页面打开；如继续使用 HTML，补充 `rel="noopener noreferrer"`。

### P1-2：缺少覆盖本阶段核心能力的自动化测试

位置：

- `tests/`

问题：

本次修改没有新增或调整测试来覆盖：

- `/feedback/ingest` 接收并存储 `external_url`。
- `/feedback` 返回 `source_url`。
- `/signals` 返回 `source_url`。
- `/requirements/{id}/evidence-trail` 返回 `source_url` 并保留 `external_url`。
- 静态 SPA 批量导入请求体与 `BatchIngestResponse.ingested` 字段匹配。

影响：

- URL 透传链路容易再次断裂。
- 当前 P0 批量导入问题就是缺少最小契约测试导致的。

验收要求：

- 至少新增后端契约级测试，覆盖 `external_url/source_url` 字段。
- 对静态 SPA 可接受 `node --check` + focused source assertion；如果不引入浏览器测试，至少要用文本断言确认请求体不再是 `{ items }`，成功提示读取 `result.ingested`。

## 非阻断观察项

- `ruff check signal_miner tests` 全量失败，失败点集中在既有 connector/test 文件；限定 P9-1 修改范围的 ruff 检查通过。因此本项不作为 P9-1 阻断，但后续应单独清理。
- `.venv/bin/python -m pytest tests/test_github_connector.py tests/test_evidence_chain.py tests/test_prd_routes.py -q` 中 `tests/test_prd_routes.py::test_post_generate_prd_success` 失败为 500。该失败路径与 P9-1 URL 点击链路无直接关系，未作为本阶段阻断，但需要在后续 PRD 路由回归中单独处理。
- 修改范围超出原指令的严格允许列表：`feedback.py`、`signals.py`、`signal_miner/utils/` 也发生变更。从能力实现角度可以理解，但交付报告应说明原因，并用测试覆盖新增公共 helper。

## 复验要求

返修后必须重新执行：

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
ruff check frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils
.venv/bin/python -m pytest <新增URL契约测试> tests/test_github_connector.py tests/test_evidence_chain.py -q
```

并提供以下 focused proof：

```bash
.venv/bin/python - <<'PY'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from signal_miner.routes.feedback import router

app = FastAPI()
app.include_router(router, prefix='/api/v1')
client = TestClient(app)

bad_shape = {'items': [{'source_type': 'manual', 'text': 'hello', 'external_url': 'https://example.com'}]}
print('embedded object status:', client.post('/api/v1/feedback/batch', json=bad_shape).status_code)

# 前端应不再发送 bad_shape；如果选择后端兼容，则该状态必须不是 422。
PY
```

