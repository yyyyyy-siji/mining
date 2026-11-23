# DeepSeek 执行指令：P10-3 PRD 生成器持久化与审计契约

## 任务目标

为 `signal_miner.pipeline.prd_generator.generate_prd_for_requirement` 补充 generator 层契约测试，覆盖路由层 mock 掉 generator 后尚未验证的内部流程：需求读取、上下文拼装、LLM 调用、PRD 持久化、状态更新、commit、audit log。

## 背景 / 当前问题

P10-1 修复了 PRD 路由成功路径 500 回归。P10-2 已补强路由响应契约，但 `POST /generate-prd` 测试通过 mock generator 隔离了内部 DB 与 audit log 调用。因此还需要对 generator 层单独建立契约测试，防止内部流程变更导致 PRD 未持久化、状态未更新或审计日志丢失。

## 允许修改范围

- `tests/test_prd_generator.py`
- 如项目已有 generator 相关测试 helper，可在测试文件内局部复用或补充。

## 禁止修改范围

- 不修改 `signal_miner/pipeline/prd_generator.py`，除非测试发现真实 bug。
- 不修改 PRD 路由生产代码。
- 不修改 P9 数据来源点击、连接器、前端相关文件。

## 实现要求

1. 新增或补强 `generate_prd_for_requirement` 成功路径测试：
   - mock `signal_miner.pipeline.prd_generator.get_session_factory`。
   - session 中的 `RequirementAssetRow` mock 必须包含：`id`、`title`、`user_stories`、`acceptance_criteria`、`impact`、`decision_reasoning`、`evidence_trail`、`opportunity_ids`、`status`、`prd_content`。
   - mock linked `OpportunityRow`、`PainPointRow`、`SignalRow` 的读取，覆盖机会、痛点、证据 enrichment 分支。
   - mock LLM `call_text` 返回固定 Markdown。
   - mock `signal_miner.pipeline.prd_generator.log_pipeline_event`，验证被调用一次。

2. 成功路径断言：
   - 返回值等于 mocked PRD Markdown。
   - `llm.call_text` 被 await 一次，且 `temperature` 默认值为 `0.3`。
   - prompt 包含需求标题、用户故事、验收标准、证据摘要、quote、来源和置信度。
   - `req_row.prd_content` 被更新为 PRD Markdown。
   - `req_row.status` 被更新为 `reviewed`。
   - `req_row.updated_at` 非空。
   - `session.commit` 被 await 一次。
   - `log_pipeline_event` 被 await 一次，且参数包含：
     - `event_type="prd.generated"`
     - `pipeline_step="prd_generation"`
     - `signal_id=<requirement_id>`
     - `model=<llm.provider_name>`
     - `input_tokens` / `output_tokens`
     - `detail.requirement_id`
     - `detail.prd_length`
     - `detail.evidence_count`

3. 错误路径断言：
   - requirement 不存在时抛 `ValueError`。
   - LLM 抛异常时转为 `RuntimeError`，且不执行 commit。

## 验收标准

### 语法 / 静态检查

```bash
ruff check tests/test_prd_generator.py
```

### 功能验证

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py -q
```

### 回归验证

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

如修改了共享测试 fixture，还需运行：

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

## 交付报告模板

```markdown
# P10-3 交付报告：PRD 生成器持久化与审计契约

验收日期：2026-06-25

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 是否修改生产代码

如修改生产代码，说明真实 bug、影响范围与修复原因。

## 遗留风险
```
