# P10-6 交付报告：PRD 证据来源链接契约

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | evidence enrichment 新增 `source_url` 字段（优先 `link.source_url`，回退 `link.external_url`） | 保留来源链接，传递到 prompt |
| `signal_miner/pipeline/prd_generator.py` | `_format_evidence_trail`：`source_url` 非空时追加 `- 来源链接: [打开原始来源]({url})`；无时静默跳过 | 避免输出 None/空链接 |
| `signal_miner/pipeline/prd_generator.py` | `PRD_GENERATION_PROMPT` 输出要求 `## 证据链` 追加 "来源链接（如有）" | 明确 LLM 输出应含可点击来源链接 |
| `tests/test_prd_generator.py` | `test_format_evidence_trail_with_entries` 证据 1 新增 `source_url`，断言 Markdown 链接；证据 2 无链接，断言不含 "来源链接" 和 "None" | 覆盖有/无 source_url 两种输出行为 |
| `tests/test_prd_generator.py` | `test_generate_prd_success` evidence trail 新增含 `source_url` 条目和含 `external_url` fallback 条目，断言双链接均在 prompt 中；`evidence_count` → 2 | 覆盖 source_url 直传和 external_url 回退两路径 |

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|
| evidence 含 `source_url` 时输出 Markdown 链接 | `test_format_evidence_trail_with_entries` | passed |
| evidence 无 `source_url` 时不输出 "来源链接" | `test_format_evidence_trail_with_entries` | passed |
| evidence 无 `source_url` 时不泄露 `None` | `test_format_evidence_trail_with_entries` | passed |
| `source_url` 出现在 PRD prompt 中 | `test_generate_prd_success` | passed |
| `external_url` fallback → 出现在 PRD prompt 中 | `test_generate_prd_success` | passed |
| prompt 输出要求含 "来源链接（如有）" | `test_generate_prd_success` | passed |
| P10-5 输出结构契约（`## 关联机会与痛点` / `## 证据链` / `## 决策理由` / `## 风险与假设`） | `test_generate_prd_success` | passed |
| P10-4 机会/痛点输入上下文 | `test_generate_prd_success` | passed |
| P10-3 持久化契约（prd_content / status / updated_at / commit / audit log） | `test_generate_prd_success` | passed |
| requirement 不存在 → `ValueError` | `test_generate_prd_requirement_not_found` | passed |
| LLM 异常 → `RuntimeError`，不 commit | `test_generate_prd_llm_failure_no_commit` | passed |
| 空证据 + 空 opportunity fallback | `test_generate_prd_empty_evidence` | passed |

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py tests/test_prd_generator.py` | passed | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py -q` | passed | 10 passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | passed | 18 passed (10 + 8) |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | passed | 43 passed, 1 个 StarletteDeprecationWarning（baseline 同） |

## 遗留风险

无。来源链接已通过 `source_url` / `external_url` 双路径进入 prompt，格式化不输出 None/空链接，P9 来源点击契约到 PRD 生成的链路已闭合。
