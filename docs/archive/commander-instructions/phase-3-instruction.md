# Phase 3: PRD 生成器与资产导出 (PRD Generator & Export) - 执行指令

> **致执行者 (Executor AI)**: 
> 欢迎来到阶段 3。我是本次项目的指挥官。你的任务是严格按照以下指令完成代码编写与测试，并在完成后按要求提交交付报告。**请记住你的边界：仅执行本阶段任务，不得修改与本阶段无关的底层架构（如 SQLAlchemy 配置等）。**

## 🎯 阶段目标

补齐 Pipeline 的最后一块拼图：实现基于 `RequirementAsset` 的结构化 PRD 生成，并支持 Markdown 与 JSON 格式的导出。

## 📝 任务清单

### 1. 数据库模型扩展
修改 `signal_miner/db/models.py`：
- 在 `RequirementAssetRow` 中新增一列 `prd_content: Mapped[str | None] = mapped_column(Text)`，用于存储生成的 Markdown 格式的 PRD 内容。

*提示：需注意确保向后兼容，如果需要，可通过 Alembic 生成 migration（由于 SQLite 限制，允许直接在 `models.py` 中添加并在测试环境中重建库，如果已配置完整的 alembic，请生成并运行 migration）。*

### 2. PRD 生成核心逻辑
创建文件 `signal_miner/pipeline/prd_generator.py`：
- 编写一个核心异步函数 `async def generate_prd_for_requirement(requirement_id: str, llm: BaseLLMAdapter) -> str:`
- **Prompt 设计**：基于传入的 `RequirementAssetRow`（包含标题、User Stories、Acceptance Criteria、Business/User Impact、Decision Reasoning 以及 Evidence Trail），要求 LLM 输出一份专业的、排版精美的 Markdown PRD。
- **证据链透传**：PRD 的末尾或具体的需求点上，必须附带 Evidence Trail（至少是相关的信号 summary 和原始 quote），体现系统的核心价值（Traceability）。
- 将生成的 Markdown 文本存储到 `RequirementAssetRow.prd_content` 中。
- 在 `signal_miner/services/audit.py` (如果有) 或使用 `log_pipeline_event` 记录生成动作 (`event_type="prd.generated"`)。

### 3. API 路由暴露
修改 `signal_miner/routes/assets.py`：
- 新增 `POST /requirements/{req_id}/generate-prd`：触发上述生成函数。
- 新增 `GET /requirements/{req_id}/prd`：
  - 支持 Query 参数 `?format=markdown` (默认) 或 `?format=json`。
  - 返回生成的 PRD。如果是 markdown，返回纯文本或包裹在 JSON 中的文本；如果是 json，返回结构化的资产组合。

### 4. 单元与集成测试
修改或新增测试文件（如 `tests/test_prd_generator.py` 或在现有集成测试中添加）：
- 测试 `generate_prd_for_requirement` 的逻辑（可以使用 Mock LLM）。
- 测试 API 路由是否能正确触发和返回。

---

## ⚖️ 验收标准 (The Golden Rules)

你在完成开发后，必须向用户（User）提交一份**阶段交付报告**，报告中必须**明确提供以下输出（直接粘贴终端截图或文本）**：

1. **代码规范验证**：
   运行 `ruff check signal_miner/`，必须输出 0 警告 / All clear。
2. **测试验证**：
   运行 `pytest tests/`，必须全绿（不得导致原有测试如 evidence chain 失败）。
3. **架构验证**：
   报告中简述你添加的文件和 API 路由路径，确保符合现有的 FastAPI + SQLAlchemy + Pipeline Adapter 结构。

---

**执行者，收到此指令后，请立即开始执行。完成后请按规范提交报告。**
