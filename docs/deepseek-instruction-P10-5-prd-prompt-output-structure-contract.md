# DeepSeek 执行指令：P10-5 PRD Prompt 输出结构契约

## 任务目标

在 P10-4 已将 Opportunity / PainPoint 上下文注入 prompt 的基础上，进一步固化 PRD 输出结构要求，明确要求 LLM 生成的 PRD 包含“关联机会与痛点”章节，避免上下文只作为输入参考但不体现在最终文档结构中。

## 背景 / 当前问题

P10-4 已修复 `opportunities_context` 未进入 prompt 的死角。当前 prompt 的输入区包含：

- `### 关联机会与痛点`
- Opportunity JTBD / 描述
- PainPoint 描述 / 严重度 / 频度

但 `PRD_GENERATION_PROMPT` 的“输出要求”编号列表仍未明确要求输出 `## 关联机会与痛点` 章节。为了让生成 PRD 的结构稳定，需要把该章节加入输出要求，并用测试断言固化。

## 允许修改范围

- `signal_miner/pipeline/prd_generator.py`
- `tests/test_prd_generator.py`

## 禁止修改范围

- 不修改 PRD 路由文件。
- 不修改 audit log 字段契约。
- 不修改 P9 数据来源点击、连接器、前端相关文件。
- 不改变 `generate_prd_for_requirement` 函数签名。

## 实现要求

1. 更新 `PRD_GENERATION_PROMPT` 的“输出要求”编号列表：
   - 新增 `## 关联机会与痛点` 章节要求。
   - 要求该章节总结关联 Opportunity 的 JTBD / 描述，以及 PainPoint 的描述 / 严重度 / 频度。
   - 保持原有章节要求仍然存在：概述、用户故事、验收标准、影响分析、证据链、决策理由、风险与假设。

2. 更新 `tests/test_prd_generator.py`：
   - 在成功路径中断言 `call_prompt` 包含 `## 关联机会与痛点` 或等价的输出章节要求。
   - 断言 prompt 仍包含 P10-4 已固化的 Opportunity / PainPoint 输入上下文。
   - 断言原有输出要求中的 `## 证据链`、`## 决策理由`、`## 风险与假设` 仍存在。

3. 保持 P10-3 / P10-4 契约：
   - PRD 持久化、状态更新、`updated_at`、commit、audit log 不变。
   - 无关联 opportunity fallback 仍为 `_无关联机会与痛点_`。
   - LLM 失败仍转 `RuntimeError` 且不 commit。

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
# P10-5 交付报告：PRD Prompt 输出结构契约

验收日期：2026-06-27

## 修改文件

| 文件 | 修改内容 | 原因 |
|---|---|---|

## 覆盖的契约

| 契约 | 测试名 | 结果 |
|---|---|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 遗留风险
```
