# DeepSeek 执行指令：P9-7 最终回归与归档

## 任务目标

对 P9 系列“数据来源可点击进入 + API 契约固化 + 测试硬化”做最终回归和归档，确认当前阶段可以收口。

## 背景 / 当前状态

P9-1 到 P9-6 已陆续通过 commander 验收：

- P9-1：数据来源可点击进入代码级闭环。
- P9-2：运行态点击链路验收。
- P9-3：连接器响应字段契约验收。
- P9-4：API 响应模型契约固化。
- P9-5：路由成功路径契约测试固化。
- P9-6：契约测试硬化。

当前需要最终确认：

- P9 相关测试集中通过。
- 文档/报告齐全。
- 剩余非阻断风险明确。
- 没有临时服务或临时端口残留。

## 允许修改范围

- `docs/` 下新增最终汇总报告。
- 如发现文档路径或报告标题错误，可修正文档。
- 不修改业务代码。
- 不修改测试代码，除非发现明显文档引用错误导致测试无法运行。

## 禁止修改范围

- 不要改前端/后端实现。
- 不要重构测试。
- 不要运行真实 GitHub 网络请求。
- 不要做无关 ruff 清理。

## 验收步骤

1. 检查 P9 指令和验收报告是否齐全：
   - `docs/deepseek-instruction-P9-*.md`
   - `docs/acceptance-P9-*.md`
2. 运行 P9 相关测试：

```bash
ruff check tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

3. 可选运行限定业务文件语法检查：

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

4. 检查端口：

```bash
lsof -iTCP:8000 -sTCP:LISTEN -n -P || true
lsof -iTCP:8501 -sTCP:LISTEN -n -P || true
```

5. 生成最终汇总报告：
   - `docs/acceptance-P9-final-summary-YYYYMMDD.md`

## 验收标准

通过条件：

- P9 相关测试通过。
- P9 文档齐全。
- 无 8000/8501 临时服务残留。
- 汇总报告明确列出非阻断技术债。

## 交付报告模板

```markdown
# P9 最终汇总报告

## 1. 阶段结果

| 阶段 | 结论 | 报告 |
|---|---|---|

## 2. 最终验证

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 3. 功能结论

- 数据来源点击链路：
- API 契约：
- 测试保障：

## 4. 非阻断技术债

- 如无，写“无”。

## 5. 收口结论

```

