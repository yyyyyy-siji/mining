# DeepSeek 执行指令：P9-4 API 响应模型契约固化

## 任务目标

将 P9-1 到 P9-3 中已经验证过的关键 API 响应结构固化为明确的 Pydantic response model，降低前后端字段漂移风险。

## 背景 / 当前问题

P9-3 验收通过，但发现：

- `POST /connectors/github/fetch` 当前返回裸 `dict`。
- `GET /connectors` 当前返回裸 `dict`。
- 字段契约目前依赖源码级断言和路由级 mock 验证。

当前字段本身是正确的，但长期维护上更稳妥的方式是把响应结构写成显式模型，并用测试锁定。

## 允许修改范围

- `signal_miner/routes/connectors.py`
- `tests/` 下新增或修改 API response model / route contract 测试
- 如前端不需要改，不要改 `frontend/static/app.js`

## 禁止修改范围

- 不要修改数据库 schema / migration。
- 不要修改 GitHub connector 抓取逻辑。
- 不要真实调用 GitHub API。
- 不要改 P9-1/P9-2 来源链接 UI。
- 不要做无关 ruff 清理。

## 实现要求

1. 在 `signal_miner/routes/connectors.py` 中新增响应模型：
   - `ConnectorListResponse`
   - `GitHubFetchResponse`
   - 如需要，可为 webhook 响应也新增模型，但不是本阶段必须。
2. 为路由加上 `response_model`：
   - `GET /connectors` → `ConnectorListResponse`
   - `POST /connectors/github/fetch` → `GitHubFetchResponse`
3. 保持现有 JSON 字段不变：
   - `GET /connectors` 返回 `{ "connectors": [...] }`
   - `POST /connectors/github/fetch` 返回 `{ "repo": ..., "ingested_count": ..., "source_type": ... }`
4. 新增路由级测试：
   - 使用 mock `GitHubConnector`，不得访问真实网络。
   - 验证 `ingested_count` 存在且 `ingested` 不存在。
   - 验证 `GET /connectors` 返回 `connectors`。
5. 保持 `tests/test_github_connector.py` 通过。

## 验收标准

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
ruff check signal_miner/routes/connectors.py
.venv/bin/python -m pytest <新增连接器响应模型测试> tests/test_github_connector.py -q
```

通过条件：

- 响应字段和 P9-3 完全一致。
- OpenAPI / FastAPI response model 不改变前端消费字段。
- 测试不访问真实 GitHub 网络。

## 交付报告模板

```markdown
# P9-4 交付报告：API 响应模型契约固化

## 1. 响应模型

| 路由 | response_model | 字段 |
|---|---|---|

## 2. 修改内容

| 文件 | 修改 | 说明 |
|---|---|---|

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 4. 兼容性确认

- GitHub connector 前端仍读取 `result.ingested_count`。
- 批量导入仍读取 `result.ingested`，不受影响。

## 5. 遗留风险

- 如无，写“无”。
```

