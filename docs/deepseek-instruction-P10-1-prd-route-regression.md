# DeepSeek 执行指令：P10-1 PRD 路由回归修复

## 任务目标

处理 P9 系列验收中记录的非阻断技术债：`tests/test_prd_routes.py::test_post_generate_prd_success` 返回 500。目标是恢复 PRD 路由成功路径测试，并确认不会影响 P9 已验收的数据来源点击链路和连接器契约。

## 背景 / 当前问题

P9 已完成并收口，但在早期回归中观察到：

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py::test_post_generate_prd_success -q
```

期望：`200`

实际：`500`

该问题与 P9 的 URL 点击链路无直接关系，因此未阻断 P9；但它属于 PRD 路由回归风险，应单独处理。

## 允许修改范围

- `signal_miner/routes/assets.py`
- `signal_miner/pipeline/prd_generator.py`
- `tests/test_prd_routes.py`
- 如确需调整 mock fixture，可修改相关测试辅助代码

## 禁止修改范围

- 不要修改 P9 URL 点击链路前端。
- 不要修改连接器 response model。
- 不要真实调用 LLM。
- 不要修改数据库 schema。
- 不要做无关 ruff 清理。

## 实现要求

1. 复现失败：

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py::test_post_generate_prd_success -q -vv
```

2. 查明 500 根因：
   - 是测试 mock session factory 没有被 `generate_prd_for_requirement()` 使用？
   - 是 `log_pipeline_event()` 触发真实 DB/runtime？
   - 是 AsyncMock / MagicMock 形状不匹配？
   - 是路由层和 generator 层各自调用不同 `get_session_factory` patch 点？

3. 做最小修复：
   - 优先修测试 mock，使其真实覆盖路由成功路径。
   - 如果业务代码确有 bug，做最小业务修复。
   - 保持 PRD 生成不真实调用外部 LLM。

4. 增加或修正测试覆盖：
   - `test_post_generate_prd_success` 必须通过。
   - 404、markdown/json retrieval、unsupported format 等现有 PRD route 测试不得回退。

## 验收标准

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
ruff check signal_miner/routes/assets.py signal_miner/pipeline/prd_generator.py tests/test_prd_routes.py
```

通过条件：

- PRD route 测试全部通过。
- P9 相关测试仍通过。
- 不真实调用外部 LLM。
- 不访问真实 GitHub 网络。

## 交付报告模板

```markdown
# P10-1 交付报告：PRD 路由回归修复

## 1. 根因

## 2. 修改内容

| 文件 | 修改 | 原因 |
|---|---|---|

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 4. P9 回归确认

## 5. 遗留风险
```

