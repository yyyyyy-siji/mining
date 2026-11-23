# DeepSeek 执行指令：P10-4 PRD 机会与痛点上下文入 Prompt

## 任务目标

修复 `generate_prd_for_requirement` 中 `opportunities_context` 被构建但未进入 LLM prompt 的逻辑缺口，让关联 Opportunity 与 PainPoint 上下文真正参与 PRD 生成，并用测试固化该契约。

## 背景 / 当前问题

P10-3 验收确认：

- `signal_miner/pipeline/prd_generator.py:148` 至 `signal_miner/pipeline/prd_generator.py:161` 会读取 linked `OpportunityRow` 与 `PainPointRow` 并构建 `opportunities_context`。
- `signal_miner/pipeline/prd_generator.py:179` 至 `signal_miner/pipeline/prd_generator.py:188` 构建 prompt 时没有传入该上下文。
- 结果是机会与痛点数据被读取但不会进入 LLM prompt，影响 PRD 背景质量。

## 允许修改范围

- `signal_miner/pipeline/prd_generator.py`
- `tests/test_prd_generator.py`

## 禁止修改范围

- 不修改 PRD 路由文件。
- 不修改 P9 数据来源点击、连接器、前端相关文件。
- 不改变 `generate_prd_for_requirement` 的函数签名。
- 不改变现有 audit log 字段契约。

## 实现要求

1. 在 `PRD_GENERATION_PROMPT` 中新增机会/痛点上下文章节。
   - 章节位置建议放在“需求信息”下、“证据链”前。
   - 标题建议使用 `### 关联机会与痛点`。
   - 占位符建议命名为 `{opportunities_context}`。

2. 将已构建的 `opportunities_context` 注入 prompt。
   - 有内容时用换行拼接。
   - 无内容时输出 `_无关联机会与痛点_`。

3. 更新或补充 `tests/test_prd_generator.py::test_generate_prd_success`：
   - 断言 prompt 包含 Opportunity 的 JTBD。
   - 断言 prompt 包含 Opportunity 描述。
   - 断言 prompt 包含 PainPoint 描述。
   - 断言 prompt 包含 PainPoint severity 与 frequency。

4. 补充无关联 opportunity 的测试或扩展现有空证据测试：
   - 当 `opportunity_ids=[]` 时，prompt 包含 `_无关联机会与痛点_`。

5. 保持 P10-3 已通过契约：
   - PRD 内容持久化。
   - `status="reviewed"`。
   - `updated_at` 非空。
   - `session.commit` 被 await 一次。
   - `log_pipeline_event` 参数不变。
   - LLM 失败不 commit。

## 验收标准

### 语法 / 静态检查

```bash
ruff check signal_miner/pipeline/prd_generator.py tests/test_prd_generator.py
```

### 功能验证

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py -q
```

### 回归验证

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

## 交付报告模板

```markdown
# P10-4 交付报告：PRD 机会与痛点上下文入 Prompt

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|

## 修复说明

说明 `opportunities_context` 如何进入 prompt，以及无关联机会时的 fallback 文案。

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 遗留风险
```
