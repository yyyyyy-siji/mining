# P10-3 交付报告：PRD 生成器持久化与审计契约

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|
| `tests/test_prd_generator.py` | 增强 `test_generate_prd_success`：添加 `temperature=0.3` 断言、prompt 内容全覆盖（标题/用户故事/验收标准/证据 quote/source/confidence）、`updated_at` 非空断言、`session.commit` 调用断言、audit log 全参数断言 | P10-3 要求补强成功路径契约，覆盖 LLM 调用参数、持久化步骤和审计日志 |
| `tests/test_prd_generator.py` | 新增 `test_generate_prd_llm_failure_no_commit`：LLM 抛异常转 RuntimeError、验证 `commit` 未被调用、status 未被更新 | P10-3 错误路径契约：防止 LLM 失败时意外持久化 |
| `tests/test_prd_generator.py` | 添加 PainPointRow mock（`pp_1`）覆盖痛点 enrichment 分支 | P10-3 要求覆盖机会/痛点/证据 enrichment 分支 |
| `tests/test_prd_generator.py` | 注释 `opportunities_context` 死角（`prd_generator.py:148-161`） | 测试执行确认 opportunities/pain points 被获取但未被插入 prompt 模板 |

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|
| 成功路径：返回 mock PRD Markdown | `test_generate_prd_success` | passed |
| LLM 调用 `temperature=0.3` | `test_generate_prd_success` | passed |
| prompt 含标题/用户故事/验收标准/证据 quote/source/confidence | `test_generate_prd_success` | passed |
| `prd_content` 持久化 | `test_generate_prd_success` | passed |
| `status` 更新为 `reviewed` | `test_generate_prd_success` | passed |
| `updated_at` 非空 | `test_generate_prd_success` | passed |
| `session.commit` 调用一次 | `test_generate_prd_success` | passed |
| audit log: `event_type`, `pipeline_step`, `signal_id`, `model`, `input_tokens`, `output_tokens`, `detail.*` | `test_generate_prd_success` | passed |
| requirement 不存在抛 `ValueError` | `test_generate_prd_requirement_not_found` | passed |
| LLM 抛异常转 `RuntimeError`，不 commit | `test_generate_prd_llm_failure_no_commit` | passed |
| 空证据链场景 | `test_generate_prd_empty_evidence` | passed |
| 格式化 helper（已有） | `test_format_user_stories_table_*`, `test_format_acceptance_criteria_*`, `test_format_evidence_trail_*` | 6 passed |

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check tests/test_prd_generator.py` | passed | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py -q` | passed | 10 passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | passed | 18 passed (10 + 8) |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | passed | 43 passed，1 个 StarletteDeprecationWarning（非阻塞，P10-2 baseline 同） |

## 是否修改生产代码

未修改 `signal_miner/pipeline/prd_generator.py`。

**发现的代码死角**（记录，未修改）：
- `prd_generator.py:148-161`：`opportunities_context` 列表被构建但从未插入 `PRD_GENERATION_PROMPT` 模板。
- 影响：fetch 的 Opportunity 和 PainPoint 数据不会出现在 LLM prompt 中。
- 建议后续补充 prompt 模板占位符以利用这些数据。

## 遗留风险

- `opportunities_context` 死角导致当前 PRD 生成忽略关联机会和痛点上下文，可能降低 PRD 质量。
- 当前测试使用 mock LLM，未验证真实 LLM 输出质量；prompt 模板的可调性仍需人工审查。
