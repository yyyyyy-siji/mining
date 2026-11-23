# P10-5 交付报告：PRD Prompt 输出结构契约

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | `PRD_GENERATION_PROMPT` 输出要求编号列表新增 `6. ## 关联机会与痛点` 章节要求（原 6-8 → 7-9 顺延） | P10-4 已将上下文注入输入区，但输出要求未明确要求生成该章节，导致结构不稳定 |
| `tests/test_prd_generator.py` | `test_generate_prd_success` 新增输出章节断言：`## 关联机会与痛点`、`## 证据链`、`## 决策理由`、`## 风险与假设` 均在 prompt 中 | 固化输出结构契约，防止章节被意外删除 |

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|
| prompt 输出要求含 `## 关联机会与痛点` | `test_generate_prd_success` | passed |
| prompt 输出要求含 `## 证据链` | `test_generate_prd_success` | passed |
| prompt 输出要求含 `## 决策理由` | `test_generate_prd_success` | passed |
| prompt 输出要求含 `## 风险与假设` | `test_generate_prd_success` | passed |
| P10-4 输入上下文：Opportunity JTBD / 描述 | `test_generate_prd_success` | passed |
| P10-4 输入上下文：PainPoint 描述 / severity / frequency | `test_generate_prd_success` | passed |
| P10-3 持久化契约（prd_content / status / updated_at / commit / audit log） | `test_generate_prd_success` | passed |
| requirement 不存在 → `ValueError` | `test_generate_prd_requirement_not_found` | passed |
| LLM 异常 → `RuntimeError`，不 commit | `test_generate_prd_llm_failure_no_commit` | passed |
| 空证据链 + 空 opportunity → fallback 文案 | `test_generate_prd_empty_evidence` | passed |

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py tests/test_prd_generator.py` | passed | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py -q` | passed | 10 passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | passed | 18 passed (10 + 8) |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | passed | 43 passed, 1 个 StarletteDeprecationWarning（baseline 同） |

## 遗留风险

无。P10-4 → P10-5 形成了完整的端到端链路：DB 读取机会/痛点 → 输入区注入上下文 → 输出要求明确章节 → 测试断言双链覆盖。
