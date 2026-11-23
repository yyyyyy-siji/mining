# P11-2 最终验收报告：发布候选暂存计划二次返修

验收日期：2026-06-28

结论：通过。

## 验收范围

本次复验覆盖 `docs/release-candidate-P11-2-staging-plan-20260628.md` 的二次返修项：

- 工作树快照计数。
- 未跟踪条目分布。
- G5 文档归档分类表。
- G6/G7 作为 G5 子项且不重复计数的口径。
- P9/P10 质量门禁。

## 文档核查

- `docs/release-candidate-P11-2-staging-plan-20260628.md:14` 至 `docs/release-candidate-P11-2-staging-plan-20260628.md:16` 已记录复验时点 `modified=9`、`untracked=60`、`total=69`，并标明 docs=57、`signal_miner/utils`=1、tests=2。
- `docs/release-candidate-P11-2-staging-plan-20260628.md:96` 至 `docs/release-candidate-P11-2-staging-plan-20260628.md:98` 已覆盖 P11 验收报告、P11 指令文档和 P11 release-candidate 文档。
- `docs/release-candidate-P11-2-staging-plan-20260628.md:99` 已记录 G5 分类表合计 56。
- `docs/release-candidate-P11-2-staging-plan-20260628.md:129` 至 `docs/release-candidate-P11-2-staging-plan-20260628.md:130` 明确 G6/G7 是 G5 子项，不重复计入 total。
- `docs/release-candidate-P11-2-staging-plan-20260628.md:133` 已说明 G5 为 57 个 docs 条目，计算口径为 56 个文档文件 + 1 个截图目录。

## 验证结果

```bash
git status --short
```

复验时点结果：9 个修改文件，60 个未跟踪条目，总计 69；未跟踪分布为 57 个 `docs/`、1 个 `signal_miner/`、2 个 `tests/`。

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

结果：18 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：43 passed，1 个 `StarletteDeprecationWarning`，非阻塞。

## 回归确认

P9 来源点击链路和 P10 PRD 链路保护集均保持通过。P11-2 只修正文档盘点口径，未修改生产代码或测试代码，也未执行任何 git 索引或提交操作。

## 最终结论

P11-2 二次返修复验通过。暂存计划已可作为发布候选人工分组和提交准备的参考；后续新增验收/指令文档后，仍需以最新 `git status --short` 重新冻结清单。

## 后续建议

下一阶段建议做发布冻结前最终检查，重新读取最新工作树，执行 `git diff --check`、语法检查和完整保护集，生成不执行 git 操作的最终冻结检查单。
