# DeepSeek 执行指令：P11-3 发布冻结前最终检查单

## 任务目标

在 P11-2 暂存计划通过后，生成发布冻结前最终检查单。该检查单用于人工执行暂存/提交前的最后核对，不执行任何 git 索引或提交操作。

## 背景 / 当前问题

P11-2 已形成发布候选暂存计划，但验收过程会继续新增文档，因此发布冻结前必须重新读取最新工作树状态，并确认代码差异、语法、测试和文档归档建议仍一致。

## 允许修改范围

- `docs/release-candidate-P11-3-freeze-checklist-20260628.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 实现要求

1. 重新读取并记录：

```bash
git status --short
git diff --stat
git diff --check
```

2. 生成最终检查单，至少包含：

- 当前工作树状态摘要。
- P9 来源点击链路文件清单。
- P10 PRD 链路文件清单。
- 文档/截图/可排除项人工确认清单。
- 建议的人工提交顺序。
- 不执行 git 操作声明。

3. 运行并记录验证命令：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

4. 如 `git diff --check` 发现 whitespace 或 conflict marker 问题，只记录问题并停止为不通过，不要自行修改代码。

## 验收标准

最终检查单必须能回答：

- 当前最新工作树有多少 modified/untracked 条目。
- 是否存在 whitespace error 或 conflict marker。
- P9/P10 保护测试是否通过。
- 哪些条目需要人工确认纳入或排除。
- 是否明确没有执行任何 git 操作。

## 交付报告模板

```markdown
# P11-3 交付报告：发布冻结前最终检查单

验收日期：2026-06-28

## 生成文件

| 文件 | 内容 |
|---|---|

## 工作树摘要

| 项 | 数量/结果 |
|---|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 人工确认项

## 遗留风险
```
