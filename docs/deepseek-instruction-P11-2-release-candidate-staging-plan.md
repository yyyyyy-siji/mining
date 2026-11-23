# DeepSeek 执行指令：P11-2 发布候选暂存计划

## 任务目标

在 P11-1 变更清单通过后，基于最新 `git status --short` 生成发布候选暂存计划，给出建议的分组提交范围和人工确认项。只写计划，不执行任何 git 索引或提交操作。

## 背景 / 当前问题

P11-1 已完成发布候选变更清单，但验收过程会继续新增文档，因此发布前必须重新读取最新工作树状态。下一步需要把 P9/P10/P11 文档和代码按可提交单元整理成清晰的暂存计划，辅助人工决定是否 `git add`、提交或拆分提交。

## 允许修改范围

- `docs/release-candidate-P11-2-staging-plan-20260628.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码。
- 不移动、删除或重命名已有文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 实现要求

1. 重新运行并记录：

```bash
git status --short
```

2. 按建议提交单元分组：

- P9 来源点击链路生产代码与测试。
- P10 PRD 链路生产代码与测试。
- P9/P10/P11 验收与指令文档。
- 截图或二进制资产。
- 需要人工确认或可排除项。

3. 每组必须列出：

- 文件/目录。
- 建议动作：纳入发布候选、人工确认后纳入、可排除、需要重命名或归档。
- 原因。
- 对应验证命令。

4. 明确不要声称已经暂存、提交或发布。

## 验收标准

```bash
git status --short
```

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

## 交付报告模板

```markdown
# P11-2 交付报告：发布候选暂存计划

验收日期：2026-06-28

## 生成文件

| 文件 | 内容 |
|---|---|

## 暂存分组摘要

| 分组 | 建议动作 | 文件/目录数 | 说明 |
|---|---|---:|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 人工确认项

## 遗留风险
```
