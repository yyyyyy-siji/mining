# DeepSeek 执行指令：P10-6 PRD 证据来源链接契约

## 任务目标

让 PRD 生成器的证据链 prompt 携带可点击来源链接，确保从 P9 已固化的 `source_url` / `external_url` 能继续传递到 PRD 生成上下文中。

## 背景 / 当前问题

P9 已围绕“数据来源可点击进入”固化了 API 与前端契约。P10-5 验收确认 PRD prompt 输出结构已经稳定，但 `signal_miner/pipeline/prd_generator.py` 的证据链格式仍只包含：

- 信号摘要
- 用户原话
- 来源类型
- 置信度

当前没有把 evidence link 中可能存在的 `source_url` 或 `external_url` 写入 prompt。结果是生成的 PRD 即使引用证据，也缺少可点击的原始来源链接。

## 允许修改范围

- `signal_miner/pipeline/prd_generator.py`
- `tests/test_prd_generator.py`

## 禁止修改范围

- 不修改 PRD 路由文件。
- 不修改 P9 前端、连接器、source clickthrough 相关文件。
- 不改变 `generate_prd_for_requirement` 函数签名。
- 不改变 audit log 字段契约。

## 实现要求

1. 在 evidence enrichment 中保留来源链接：
   - 优先读取 `link.get("source_url")`。
   - 如果为空，回退到 `link.get("external_url")`。
   - 字段建议命名为 `source_url`。

2. 更新 `_format_evidence_trail`：
   - 当 `source_url` 存在时，每条证据输出一行来源链接。
   - 建议格式：`- 来源链接: [打开原始来源]({source_url})`。
   - 当 `source_url` 不存在时，不要输出 `None`、空 Markdown 链接或误导性 URL。

3. 更新 `PRD_GENERATION_PROMPT` 输出要求：
   - `## 证据链` 章节要求中明确每条证据在有来源链接时必须包含可点击来源链接。

4. 更新 `tests/test_prd_generator.py`：
   - `_format_evidence_trail` 的单元测试新增含 `source_url` 的输入，并断言输出包含 Markdown 链接。
   - 新增或增强无 `source_url` 的测试，断言不会输出 `None` 或空链接。
   - `test_generate_prd_success` 的 mock evidence link 增加 `source_url`，断言 `call_prompt` 包含该 URL 或 Markdown 链接。
   - 如使用 `external_url` fallback，至少补一个断言证明 fallback 生效。

5. 保持 P10-3/P10-4/P10-5 已通过契约：
   - PRD 内容持久化、`status="reviewed"`、`updated_at`、commit、audit log 不变。
   - Opportunity / PainPoint 上下文仍进入 prompt。
   - 输出要求仍包含 `## 关联机会与痛点`、`## 证据链`、`## 决策理由`、`## 风险与假设`。
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
# P10-6 交付报告：PRD 证据来源链接契约

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
