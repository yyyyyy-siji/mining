# P10 最终阶段汇总：PRD 路由、生成器与 Prompt 契约收尾

验收日期：2026-06-27

结论：全部通过。

---

## 阶段汇总

| 阶段 | 目标 | 最终验收报告 | 结论 |
|---|---|---|---|
| P10-1 | PRD 路由 500 回归修复 | `docs/acceptance-P10-1-final-pass-20260625.md` | 通过 |
| P10-2 | PRD 路由响应契约硬化 | `docs/acceptance-P10-2-final-pass-20260625.md` | 通过 |
| P10-3 | PRD generator 持久化与审计契约 | `docs/acceptance-P10-3-final-pass-20260627.md` | 通过 |
| P10-4 | Opportunity/PainPoint 上下文入 prompt | `docs/acceptance-P10-4-final-pass-20260627.md` | 通过 |
| P10-5 | PRD prompt 输出结构契约 | `docs/acceptance-P10-5-final-pass-20260627.md` | 通过 |
| P10-6 | PRD 证据来源链接契约 | `docs/acceptance-P10-6-final-pass-20260627.md` | 通过 |
| P10-7 | 总回归与归档 | 本文档 | 通过 |

## 当前 PRD 链路覆盖

### 路由层（P10-1 / P10-2）
- `POST /requirements/{req_id}/generate-prd` 成功响应字段、类型和值。
- Generator 抛 `ValueError` → 404。
- Generator 抛 `RuntimeError` → 500，含 `PRD generation failed`。
- `GET /requirements/{req_id}/prd?format=markdown` 与 `?format=json` 响应契约。

### Generator 层（P10-3）
- 需求读取、LLM 调用（`temperature=0.3`）、prompt 组装。
- PRD 内容持久化到 `prd_content`、状态更新为 `reviewed`、`updated_at` 非空。
- `session.commit` 被 await 一次。
- `log_pipeline_event` audit log（含 `event_type`/`pipeline_step`/`signal_id`/`model`/tokens/detail）。
- Requirement 不存在 → `ValueError`。
- LLM 异常 → `RuntimeError`，commit 不执行。

### Prompt 层（P10-4 / P10-5 / P10-6）
- **P10-4**：`opportunities_context`（Opportunity JTBD/描述 + PainPoint 描述/severity/frequency）注入 `PRD_GENERATION_PROMPT` 输入区，空 context 输出 `_无关联机会与痛点_`。
- **P10-5**：输出要求固化 `## 关联机会与痛点` 章节，与 `## 证据链`/`## 决策理由`/`## 风险与假设` 共存。
- **P10-6**：evidence enrichment 新增 `source_url`（优先 `source_url`，回退 `external_url`），`_format_evidence_trail` 输出 `[打开原始来源]({url})`，无链接不输出 None/空链接。

## 总回归结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py` | 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 通过 | 18 passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 通过 | 43 passed, 1 StarletteDeprecationWarning (Starlette TestClient/httpx 兼容性弃用提示，非阻塞) |
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | 通过 | 所有模块编译成功 |
| `node --check frontend/static/app.js` | 通过 | JS 语法无错误 |

## 归档说明

- **所有 P10 交付物**（指令、交付报告、最终验收报告）均在 `docs/` 目录下，命名规则为 `{type}-P10-{N}-{desc}-{date}.md`。
- **P10 生产代码修改** 集中在 `signal_miner/pipeline/prd_generator.py`（P10-4/P10-5/P10-6）。
- **P10 测试代码修改** 集中在 `tests/test_prd_routes.py`（P10-1/P10-2）和 `tests/test_prd_generator.py`（P10-3/P10-4/P10-5/P10-6）。
- **`signal_miner/routes/assets.py`** 的 `source_url` 变更属于 P9 来源点击链路遗留变更，不应归因到 P10-1。
- **P9 来源点击链路** 已通过 P10-6 的证据来源链接与 PRD prompt 打通，形成端到端闭环。

## 遗留风险

- `StarletteDeprecationWarning`：Starlette TestClient/httpx 兼容性弃用提示，非阻塞。
- PRD generator 的 LLM 调用始终以 mock 覆盖生成层契约；真实 LLM 输出质量与 prompt 调校仍需人工审查。
