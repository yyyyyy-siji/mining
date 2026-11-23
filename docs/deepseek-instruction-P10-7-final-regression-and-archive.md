# DeepSeek 执行指令：P10-7 PRD 链路总回归与归档

## 任务目标

对 P10-1 至 P10-6 的 PRD 路由、generator、prompt、证据来源链接契约做一次收尾总回归，并整理阶段归档说明。

## 背景 / 当前问题

P10 已连续完成：

- P10-1：PRD 路由 500 回归修复。
- P10-2：PRD 路由响应契约硬化。
- P10-3：PRD generator 持久化与审计契约。
- P10-4：Opportunity / PainPoint 上下文入 prompt。
- P10-5：PRD prompt 输出结构契约。
- P10-6：PRD 证据来源链接契约。

需要用最终回归确认这些阶段共同成立，并生成阶段汇总文档。

## 允许修改范围

- `docs/acceptance-P10-final-summary-20260627.md`
- 如发现测试报告路径或文档链接错误，可只修正文档。

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码，除非总回归暴露真实失败。
- 不修改 P9 前端、连接器、source clickthrough 相关文件。

## 实现要求

1. 汇总 P10-1 至 P10-6 每阶段目标、最终验收报告路径和核心测试证据。
2. 明确当前 PRD 链路已覆盖：
   - 路由成功路径。
   - 路由响应字段契约。
   - generator 持久化、状态更新、commit、audit log。
   - Opportunity / PainPoint prompt 输入与输出结构。
   - evidence source URL / external URL 到 Markdown 可点击链接。
3. 运行并记录总回归命令。
4. 如发现失败，不要扩大修改范围；输出失败原因并等待返修指令。

## 验收标准

### 静态检查

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

### PRD 链路测试

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

### P9/P10 保护集

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

### 语法检查

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 交付报告模板

```markdown
# P10-7 交付报告：PRD 链路总回归与归档

验收日期：2026-06-27

## 阶段汇总

| 阶段 | 目标 | 最终验收报告 | 结论 |
|---|---|---|---|

## 总回归结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 归档说明

## 遗留风险
```
