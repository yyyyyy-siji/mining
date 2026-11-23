# P10-4 交付报告：PRD 机会与痛点上下文入 Prompt

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | `PRD_GENERATION_PROMPT` 新增 `### 关联机会与痛点` 章节（含 `{opportunities_context}` 占位符） | 修复 P10-3 发现的死角：`opportunities_context` 已构建但未进入 LLM prompt |
| `signal_miner/pipeline/prd_generator.py` | `.format()` 调用中格式化并传入 `opportunities_context`（有内容时换行拼接，无内容时 `_无关联机会与痛点_`） | 让关联机会与痛点数据真正进入 LLM 上下文 |
| `tests/test_prd_generator.py` | `test_generate_prd_success` 替换死角注释为真实断言（JTBD、机会描述、痛点描述、severity、frequency） | 固化机会/痛点上下文入 prompt 的契约 |
| `tests/test_prd_generator.py` | `test_generate_prd_empty_evidence` 新增 `_无关联机会与痛点_` fallback 断言 | 覆盖 `opportunity_ids=[]` 的边界场景 |

## 修复说明

`opportunities_context` 原在 `prd_generator.py:148-161` 被构建（fetch Opportunity + PainPoint），但 `.format()` 调用中无对应占位符。修复后：

1. **Prompt 模板**：在"影响分析"和"证据链"之间新增 `### 关联机会与痛点` 章节。
2. **格式化逻辑**：
   - `opportunities_context` 非空 → `"\n".join(opportunities_context)`，逐条输出 JTBD/描述/痛点。
   - `opportunities_context` 为空 → `"_无关联机会与痛点_"`。

未改变 `generate_prd_for_requirement` 的函数签名、audit log 字段或现有持久化逻辑。

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|
| prompt 包含 Opportunity JTBD | `test_generate_prd_success` | passed |
| prompt 包含 Opportunity 描述 | `test_generate_prd_success` | passed |
| prompt 包含 PainPoint 描述 | `test_generate_prd_success` | passed |
| prompt 包含 PainPoint severity | `test_generate_prd_success` | passed |
| prompt 包含 PainPoint frequency | `test_generate_prd_success` | passed |
| `opportunity_ids=[]` 时 prompt 含 fallback 文案 | `test_generate_prd_empty_evidence` | passed |
| P10-3 成功路径持久化契约（prd_content/status/updated_at/commit/audit log） | `test_generate_prd_success` | passed |
| requirement 不存在抛 `ValueError` | `test_generate_prd_requirement_not_found` | passed |
| LLM 异常转 `RuntimeError` 且不 commit | `test_generate_prd_llm_failure_no_commit` | passed |

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py tests/test_prd_generator.py` | passed | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py -q` | passed | 10 passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | passed | 18 passed (10 + 8) |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | passed | 43 passed, 1 个 StarletteDeprecationWarning（baseline 同） |

## 遗留风险

无。`opportunities_context` 死角已消除，关联的机会和痛点数据现在完整进入 LLM prompt。
