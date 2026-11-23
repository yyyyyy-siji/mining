# 🚀 Phase 3 任务交付报告 — PRD 生成器与资产导出

**日期**: 2026-05-29  
**执行者**: Executor AI  
**阶段**: Phase 3 — PRD Generator & Export

---

## 1. 变更摘要

| 操作 | 文件 | 说明 |
|---|---|---|
| [MODIFY] | `signal_miner/db/models.py` | `RequirementAssetRow` 新增 `prd_content: Mapped[str \| None]` 字段 (Text, nullable) |
| [NEW] | `signal_miner/pipeline/prd_generator.py` | PRD 生成核心模块：LLM 驱动的 Markdown PRD 生成 + 证据链透传 + 审计日志 |
| [MODIFY] | `signal_miner/routes/assets.py` | 新增 2 个 API 端点 |
| [NEW] | `tests/test_prd_generator.py` | 9 个测试用例 |

---

## 2. 新增 API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/requirements/{req_id}/generate-prd` | 触发 LLM 生成 Markdown PRD，存入 `prd_content` 字段 |
| `GET` | `/api/v1/requirements/{req_id}/prd?format=markdown` | 返回 Markdown PRD 文本（默认） |
| `GET` | `/api/v1/requirements/{req_id}/prd?format=json` | 返回结构化资产 JSON（含全部字段 + prd_content） |

---

## 3. PRD 生成器设计要点

### Prompt 设计
- 以中文生成专业 Markdown PRD
- 包含 8 个章节：概述、用户故事（表格）、验收标准（编号列表）、影响分析、**证据链**、决策理由、风险与假设
- 证据链**完整透传**：每条证据含信号摘要、用户原话（Quote）、来源类型、置信度

### 数据流
```
POST /generate-prd
  → 加载 RequirementAssetRow + 关联的 Opportunity/PainPoint/Signal
  → 丰富证据链（查询 SignalRow 获取完整信号详情）
  → 构建 Prompt + 调用 LLM
  → 存储 prd_content + 更新 status="reviewed"
  → 审计日志 (event_type="prd.generated")
  → 返回生成摘要
```

---

## 4. 静态自检结果 (Ruff Audit)

```
$ ruff check signal_miner/
All checks passed!
```

**结果: 0 Errors, 0 Warnings** ✅

---

## 5. 测试运行结果 (Pytest Verification)

```
$ pytest tests/test_prd_generator.py -v

tests/test_prd_generator.py::test_format_user_stories_table_with_stories   PASSED
tests/test_prd_generator.py::test_format_user_stories_table_empty          PASSED
tests/test_prd_generator.py::test_format_acceptance_criteria_with_items    PASSED
tests/test_prd_generator.py::test_format_acceptance_criteria_empty         PASSED
tests/test_prd_generator.py::test_format_evidence_trail_with_entries       PASSED
tests/test_prd_generator.py::test_format_evidence_trail_empty              PASSED
tests/test_prd_generator.py::test_generate_prd_requirement_not_found       PASSED
tests/test_prd_generator.py::test_generate_prd_success                     PASSED
tests/test_prd_generator.py::test_generate_prd_empty_evidence              PASSED

============================== 9 passed in 1.05s ==============================
```

**结果: 9/9 Passed (100%)** ✅

> **已知限制**: `tests/test_evidence_chain.py` 因 managed Python 环境的 `pydantic_core` 代码签名限制（Team ID 不匹配）无法在当前沙箱加载。这是环境层面问题，非本次代码变更引入。

---

## 6. 架构合规验证

| 检查项 | 状态 | 说明 |
|---|---|---|
| FastAPI 异步路由 | ✅ | 新增路由使用 `async def`，通过 `http_request.app.state.runtime` 获取共享资源 |
| SQLAlchemy 2.0 | ✅ | `Mapped[str \| None]` + `mapped_column(Text, nullable=True)` |
| Pipeline Adapter | ✅ | `generate_prd_for_requirement` 接收 `BaseLLMAdapter`，不耦合具体实现 |
| 审计日志 | ✅ | `log_pipeline_event(event_type="prd.generated")` |
| 证据链可追溯 | ✅ | PRD 末尾输出信号摘要、用户原话、来源、置信度 |
| 向后兼容 | ✅ | `prd_content` 为 `nullable=True`，存量数据不受影响 |

---

## 7. 测试覆盖详情

| 测试用例 | 类型 | 覆盖点 |
|---|---|---|
| `test_format_user_stories_table_with_stories` | 单元 | 用户故事→Markdown 表格 |
| `test_format_user_stories_table_empty` | 单元 | 空列表→占位文本 |
| `test_format_acceptance_criteria_with_items` | 单元 | AC→编号列表 |
| `test_format_acceptance_criteria_empty` | 单元 | 空列表→占位文本 |
| `test_format_evidence_trail_with_entries` | 单元 | 证据链→结构化 Markdown |
| `test_format_evidence_trail_empty` | 单元 | 空列表→占位文本 |
| `test_generate_prd_requirement_not_found` | 集成 | 不存在的 requirement_id → ValueError |
| `test_generate_prd_success` | 集成 | Mock LLM 完整流程：Prompt 校验、prd_content 持久化、审计日志 |
| `test_generate_prd_empty_evidence` | 集成 | 空证据链仍能生成基本 PRD |

---

**Phase 3 任务全部完成，验收标准已通过。请指挥官审阅。**
