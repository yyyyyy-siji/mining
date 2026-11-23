# DeepSeek 返修指令：P9-1-fix 数据来源可点击进入

## 任务目标

修复 P9-1 验收中的阻断问题，使“数据来源可点击进入”优化可以通过复验。本次只做聚焦返修，不重做 UI，不扩展新功能。

## 背景 / 当前问题

P9-1 初验结论：不通过。

阻断项：

1. 静态 SPA 批量导入仍向 `/feedback/batch` 发送 `{ items: [...] }`，而后端接口期望请求体直接是数组，实际返回 422。
2. 静态 SPA 批量导入成功提示读取 `result.ingested_count`，但后端 `BatchIngestResponse` 字段是 `ingested`。
3. Streamlit 来源链接使用 `unsafe_allow_html=True` 时直接把用户输入 URL 插入 HTML 属性，没有做 HTML attribute escaping。
4. 缺少覆盖 URL 透传和批量导入契约的自动化测试或 focused assertions。

验收报告位置：

- `docs/acceptance-P9-1-source-clickthrough.md`

## 允许修改范围

只允许修改：

- `frontend/static/app.js`
- `frontend/app.py`
- `tests/` 下新增或修改聚焦 URL / batch contract 的测试
- 如测试确需导入 helper，可新增小型测试辅助函数，但不要改业务管线

除非证明必须，否则不要再修改：

- `signal_miner/routes/feedback.py`
- `signal_miner/routes/signals.py`
- `signal_miner/routes/assets.py`
- `signal_miner/utils/url_templates.py`

## 禁止修改范围

- 不要改数据库 schema / migration。
- 不要改 LLM、pipeline、profile 隔离逻辑。
- 不要重构整个前端。
- 不要用 broad ruff --fix 清理无关文件。
- 不要修改无关 connector 文件。

## 实现要求

### 1. 修复静态 SPA 批量导入请求体

文件：`frontend/static/app.js`

当前错误模式：

```js
apiPost('/feedback/batch', { items })
```

必须改为匹配后端契约：

```js
apiPost('/feedback/batch', items)
```

同时保持 URL 字段归一化：

```js
item.external_url = item.external_url || item.source_url || item.url || item.video_url || item.link || undefined;
```

### 2. 修复批量导入成功提示字段

文件：`frontend/static/app.js`

后端 `BatchIngestResponse` 字段是：

- `total`
- `ingested`
- `duplicates`
- `feedback_ids`

成功提示必须读取 `result.ingested`，不能读取 `result.ingested_count`。

### 3. 修复 Streamlit URL HTML 属性转义

文件：`frontend/app.py`

新增一个小型 helper，例如：

```python
from html import escape

def render_source_link(url: str | None, label: str) -> None:
    if not url:
        return
    safe_url = escape(url, quote=True)
    safe_label = escape(label)
    st.markdown(
        f"🔗 <a href=\"{safe_url}\" target=\"_blank\" rel=\"noopener noreferrer\">{safe_label}</a>",
        unsafe_allow_html=True,
    )
```

要求：

- 本阶段涉及的来源链接统一用该 helper。
- 不要把用户反馈正文改成 HTML 渲染。
- 保持中英文文案。

### 4. 补充最小验证

至少新增一个测试或 focused script，覆盖以下断言：

- 静态 SPA 源码中不再存在 `apiPost('/feedback/batch', { items })`。
- 静态 SPA 源码中存在 `apiPost('/feedback/batch', items)`。
- 静态 SPA 成功提示使用 `result.ingested`。
- `frontend/app.py` 中来源链接 helper 使用 `html.escape(..., quote=True)` 或等价方式。

如新增 pytest，建议命名：

- `tests/test_source_clickthrough_contract.py`

可以做源码级断言，不必引入浏览器。

## 验收标准

### 语法 / 静态检查

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
ruff check frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils
```

期望全部通过。

### 聚焦测试

执行新增测试，例如：

```bash
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py -q
```

期望全部通过。

### 回归测试

```bash
.venv/bin/python -m pytest tests/test_github_connector.py tests/test_evidence_chain.py -q
```

期望全部通过。

`tests/test_prd_routes.py::test_post_generate_prd_success` 当前存在与本阶段无直接关系的 500 问题，本返修不要求处理；如顺手修复，必须单独说明。

## 交付报告模板

```markdown
# P9-1-fix 交付报告：数据来源可点击进入返修

## 1. 修复项

| 阻断项 | 修复方式 | 文件 |
|---|---|---|

## 2. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 3. 聚焦证据

- 批量导入请求体已从 `{ items }` 改为数组。
- 成功提示读取 `result.ingested`。
- Streamlit URL 链接已做 HTML 属性转义。

## 4. 遗留问题

- 如无，写“无”。
```

