# P10-3 最终验收报告：PRD 生成器持久化与审计契约

验收日期：2026-06-27

结论：通过。

## 验收范围

本次验收覆盖 `signal_miner.pipeline.prd_generator.generate_prd_for_requirement` 的 generator 层契约测试：

- requirement 不存在时抛 `ValueError`。
- 成功路径返回 LLM 生成的 PRD Markdown。
- LLM 默认调用参数包含 `temperature=0.3`。
- prompt 包含需求标题、用户故事、验收标准、证据摘要、quote、来源和置信度。
- PRD 内容写回 `req_row.prd_content`。
- requirement 状态更新为 `reviewed`。
- `updated_at` 被写入。
- `session.commit` 被 await 一次。
- `log_pipeline_event` 被 await 一次，且关键参数完整。
- LLM 抛异常时转换为 `RuntimeError`，且不执行 commit。

## 代码核查

- `tests/test_prd_generator.py:112` 补强成功路径测试。
- `tests/test_prd_generator.py:213` 校验 LLM 被 await 一次，并断言 `temperature=0.3`。
- `tests/test_prd_generator.py:218` 至 `tests/test_prd_generator.py:226` 校验 prompt 中的需求、用户故事、验收标准和证据链字段。
- `tests/test_prd_generator.py:236` 至 `tests/test_prd_generator.py:242` 校验持久化字段、状态更新、`updated_at` 和 commit。
- `tests/test_prd_generator.py:245` 至 `tests/test_prd_generator.py:255` 校验 audit log 参数。
- `tests/test_prd_generator.py:306` 新增 LLM 失败不 commit 的错误路径测试。

## 验证结果

```bash
ruff check tests/test_prd_generator.py
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

P10-1 PRD 路由成功路径、P10-2 PRD 路由契约硬化、P9 数据来源点击与连接器契约保护集均未受影响。

## 最终结论

P10-3 达成目标：generator 层的持久化、状态更新、commit、审计日志和 LLM 失败错误路径已经有明确测试保护。

## 后续建议

验收中确认 `signal_miner/pipeline/prd_generator.py:148` 至 `signal_miner/pipeline/prd_generator.py:188` 存在真实逻辑缺口：`opportunities_context` 被构建，但没有插入 `PRD_GENERATION_PROMPT`。这会导致关联 Opportunity 和 PainPoint 已被读取却不会进入 LLM prompt。建议进入 P10-4 专项修复并补充断言。
