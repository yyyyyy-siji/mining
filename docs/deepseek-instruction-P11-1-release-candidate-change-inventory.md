# DeepSeek 执行指令：P11-1 发布候选变更清单与工作树整理

## 任务目标

在 P9/P10 验收完成后，整理当前工作树的发布候选变更清单，明确哪些文件属于 P9 来源点击链路、哪些属于 P10 PRD 链路、哪些只是验收文档，辅助后续提交、打包或人工发布决策。

## 背景 / 当前问题

当前工作树包含多阶段修改与大量未跟踪验收文档。P10-7 已通过总回归，但工作树仍未整理成清晰的发布候选清单。下一步不应继续改业务逻辑，而应做发布前变更归档。

## 允许修改范围

- `docs/release-candidate-P11-1-change-inventory-20260627.md`

## 禁止修改范围

- 不修改生产代码。
- 不修改测试代码。
- 不移动、删除或重命名已有 P9/P10 验收文档。
- 不执行 `git add`、`git commit`、`git reset`、`git checkout` 等会改变 git 索引或工作树状态的命令。

## 实现要求

1. 读取当前工作树状态：

```bash
git status --short
```

2. 生成变更清单，至少分为：

- P9 来源点击链路相关生产代码。
- P9 来源点击链路相关测试/验收文档。
- P10 PRD 链路相关生产代码。
- P10 PRD 链路相关测试。
- P10 指令、交付报告、最终验收报告。
- 非 P9/P10 或需要人工确认的文件。

3. 对每个生产代码文件写明：

- 文件路径。
- 归属阶段。
- 变更主题。
- 对应保护测试。

4. 记录最终建议：

- 是否可以作为发布候选继续推进。
- 需要人工确认的未跟踪文件或归档文件。
- 不要声称已经提交或发布。

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
# P11-1 交付报告：发布候选变更清单与工作树整理

验收日期：2026-06-27

## 生成文件

| 文件 | 内容 |
|---|---|

## 变更分组摘要

| 分组 | 文件数 | 说明 |
|---|---:|---|

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 需要人工确认

## 遗留风险
```
