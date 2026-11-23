# P10-5 最终验收报告：PRD Prompt 输出结构契约

验收日期：2026-06-27

结论：通过。

## 验收范围

本次验收覆盖 PRD prompt 输出结构契约：

- `PRD_GENERATION_PROMPT` 的输出要求中新增 `## 关联机会与痛点`。
- 原有输出要求中的 `## 证据链`、`## 决策理由`、`## 风险与假设` 保持存在。
- P10-4 已加入的 Opportunity / PainPoint 输入上下文仍然进入 prompt。
- P10-3 已固化的持久化、状态更新、commit、audit log 和 LLM 失败不 commit 契约保持不变。

## 代码核查

- `signal_miner/pipeline/prd_generator.py:66` 输出要求新增 `6. **## 关联机会与痛点**`，并说明需要总结 Opportunity 的 JTBD / 描述和 PainPoint 的描述 / 严重度 / 频度。
- `signal_miner/pipeline/prd_generator.py:67` 至 `signal_miner/pipeline/prd_generator.py:69` 保留 `## 证据链`、`## 决策理由`、`## 风险与假设` 输出要求。
- `tests/test_prd_generator.py:236` 至 `tests/test_prd_generator.py:240` 新增 prompt 输出结构断言。
- `tests/test_prd_generator.py:229` 至 `tests/test_prd_generator.py:234` 保留 P10-4 的 Opportunity / PainPoint 上下文断言。

## 验证结果

```bash
ruff check signal_miner/pipeline/prd_generator.py tests/test_prd_generator.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py -q
```

结果：10 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

结果：18 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：43 passed，1 个 `StarletteDeprecationWarning`，非阻塞。

## 回归确认

P10-1 PRD 路由成功路径、P10-2 PRD 路由响应契约、P10-3 generator 持久化与审计契约、P10-4 Opportunity / PainPoint 上下文入 prompt、P9 数据来源点击与连接器保护集均未受影响。

## 最终结论

P10-5 达成目标：PRD prompt 不仅接收 Opportunity / PainPoint 上下文，也明确要求生成文档输出 `## 关联机会与痛点` 章节。

## 后续建议

下一阶段建议补齐 PRD 证据链中的可点击来源链接契约。当前 `signal_miner/pipeline/prd_generator.py` 的 `_format_evidence_trail` 只输出信号摘要、quote、来源类型和置信度，尚未把 `source_url` / `external_url` 带入 PRD prompt。
