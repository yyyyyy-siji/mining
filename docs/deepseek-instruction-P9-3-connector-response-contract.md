# DeepSeek 执行指令：P9-3 连接器响应字段契约验收

## 任务目标

核对并修复连接器页面与后端连接器接口的响应字段契约，重点检查静态 SPA 数据源页面中 GitHub connector 的成功提示字段是否与后端实际响应一致。

## 背景 / 当前问题

P9-2 运行态验收通过，但发现一个非阻断观察项：

- `frontend/static/app.js` 的 GitHub connector 区域仍使用 `result.ingested_count`。
- 需要确认 `/api/v1/connectors/github/...` 或对应连接器接口实际返回字段名。
- 如果后端返回的是 `ingested`、`ingested_count` 或其他字段，前端必须与之匹配，避免连接器页面出现 `undefined` 或误导提示。

## 允许修改范围

- `frontend/static/app.js`
- `signal_miner/routes/connectors.py`
- `tests/` 下新增或修改连接器响应契约测试
- `docs/` 下交付报告

## 禁止修改范围

- 不要改数据库 schema。
- 不要改 pipeline、LLM、profile 逻辑。
- 不要重构整个数据源页面。
- 不要真实调用外部 GitHub API；测试应使用 mock。

## 实现要求

1. 阅读 `signal_miner/routes/connectors.py`，确认 GitHub connector API 的响应结构。
2. 阅读 `frontend/static/app.js` 数据源页面，确认所有连接器成功提示读取的字段。
3. 如果字段不一致，做最小修复：
   - 优先让前端读取后端实际字段。
   - 如后端字段设计不清晰，可新增兼容字段，但必须保持已有 API 不破坏。
4. 新增聚焦测试：
   - 后端连接器路由响应字段测试。
   - 前端源码契约测试，确保不会读取不存在字段。
5. 不要引入真实网络依赖。

## 验收标准

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
ruff check signal_miner/routes/connectors.py frontend/app.py signal_miner/routes/assets.py signal_miner/routes/feedback.py signal_miner/routes/signals.py signal_miner/utils
.venv/bin/python -m pytest <新增连接器契约测试> tests/test_github_connector.py -q
```

通过条件：

- 前后端字段一致。
- 数据源页面不会显示 `undefined`。
- GitHub connector 测试不访问真实网络。

## 交付报告模板

```markdown
# P9-3 交付报告：连接器响应字段契约验收

## 1. 字段契约结论

| 接口 | 后端字段 | 前端读取字段 | 是否一致 |
|---|---|---|---|

## 2. 修复内容

| 文件 | 修改 | 原因 |
|---|---|---|

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 4. 遗留风险

- 如无，写“无”。
```

