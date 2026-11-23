# P10-4 最终验收报告：PRD 机会与痛点上下文入 Prompt

验收日期：2026-06-27

结论：通过。

## 验收范围

本次验收覆盖 P10-3 发现的 `opportunities_context` 死角修复：

- `PRD_GENERATION_PROMPT` 新增 `### 关联机会与痛点` 章节。
- `generate_prd_for_requirement` 将已构建的 Opportunity / PainPoint 上下注入 prompt。
- 有关联上下文时使用换行拼接。
- 无关联上下文时使用 `_无关联机会与痛点_` fallback。
- P10-3 已通过的持久化、状态更新、commit、audit log、LLM 失败不 commit 契约保持不变。

## 代码核查

- `signal_miner/pipeline/prd_generator.py:50` 新增 `### 关联机会与痛点` 章节和 `{opportunities_context}` 占位符。
- `signal_miner/pipeline/prd_generator.py:182` 构建 `opportunities_text`，非空时 `"\n".join(opportunities_context)`，为空时 `_无关联机会与痛点_`。
- `signal_miner/pipeline/prd_generator.py:196` 将 `opportunities_context=opportunities_text` 传入 prompt `.format()`。
- `tests/test_prd_generator.py:229` 至 `tests/test_prd_generator.py:234` 断言 prompt 包含 Opportunity JTBD、Opportunity 描述、PainPoint 描述、severity、frequency。
- `tests/test_prd_generator.py:307` 至 `tests/test_prd_generator.py:309` 断言无关联 opportunity 时 prompt 包含 fallback 文案。

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

P10-1 PRD 路由成功路径、P10-2 PRD 路由响应契约、P10-3 generator 持久化与审计契约、P9 数据来源点击与连接器保护集均未受影响。

## 最终结论

P10-4 达成目标：原先只构建但未使用的 Opportunity / PainPoint 上下文现在会进入 LLM prompt，并有测试保护。

## 后续建议

下一阶段建议固化 PRD prompt 输出结构：当前 prompt 已把机会与痛点作为输入上下文提供给 LLM，但“输出要求”章节尚未明确要求生成文档包含“关联机会与痛点”章节。可通过 P10-5 明确输出章节并补充 prompt 契约测试。
