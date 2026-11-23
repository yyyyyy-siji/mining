# P10-6 最终验收报告：PRD 证据来源链接契约

验收日期：2026-06-27

结论：通过。

## 验收范围

本次验收覆盖 PRD generator 的证据来源链接契约：

- evidence enrichment 保留 `source_url`。
- `source_url` 为空时回退 `external_url`。
- `_format_evidence_trail` 在有链接时输出 Markdown 链接。
- 无链接时不输出 `来源链接`、`None` 或空链接。
- PRD prompt 输出要求明确 `## 证据链` 需要包含来源链接（如有）。
- P10-3/P10-4/P10-5 的持久化、审计、机会/痛点上下文、输出结构契约保持不变。

## 代码核查

- `signal_miner/pipeline/prd_generator.py:67` 的 `## 证据链` 输出要求已包含 `来源链接（如有）`。
- `signal_miner/pipeline/prd_generator.py:110` 读取 `source_url`。
- `signal_miner/pipeline/prd_generator.py:119` 至 `signal_miner/pipeline/prd_generator.py:121` 仅在 `source_url` 存在时输出 `- 来源链接: [打开原始来源](...)`。
- `signal_miner/pipeline/prd_generator.py:184` 使用 `link.get("source_url") or link.get("external_url")`，覆盖直传和 fallback。
- `tests/test_prd_generator.py:55` 至 `tests/test_prd_generator.py:85` 覆盖有链接和无链接的格式化行为。
- `tests/test_prd_generator.py:263` 至 `tests/test_prd_generator.py:265` 覆盖 `source_url` 与 `external_url` fallback 均进入 prompt。

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

P10-1 PRD 路由成功路径、P10-2 路由响应契约、P10-3 generator 持久化与审计契约、P10-4 Opportunity / PainPoint 上下文入 prompt、P10-5 PRD 输出结构契约，以及 P9 数据来源点击与连接器保护集均未受影响。

## 最终结论

P10-6 达成目标：PRD 证据链 prompt 已闭合 `source_url` / `external_url` 到 Markdown 可点击来源链接的传递链路。

## 后续建议

下一阶段建议做 P10 收尾总回归与归档，集中确认 P10-1 至 P10-6 的验收文档、测试保护集和工作树状态，避免 PRD 链路阶段性成果散落。
