# P11-1 验收报告：发布候选变更清单与工作树整理

验收日期：2026-06-28

结论：不通过，需要返修。

## 已通过项

质量门禁本地复验通过：

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

## 阻断问题

### P1-1：工作树计数不符合当前代码事实

位置：`docs/release-candidate-P11-1-change-inventory-20260627.md:9`

问题：

文档写道 `git status --short` 输出 8 个修改文件和 48 个未跟踪条目。实际当前输出为 9 个修改文件和 51 个未跟踪条目。

证据：

```bash
git status --short | awk 'BEGIN{m=0;u=0} /^ M/{m++} /^\\?\\?/{u++} END{print "modified=" m; print "untracked=" u}'
```

实际结果：

```text
modified=9
untracked=51
```

影响：

P11-1 的核心交付物是发布候选变更清单，入口概览计数错误会直接误导后续提交、打包和归档判断。

验收要求：

修正工作树概览为当前事实：9 个修改文件、51 个未跟踪条目；并说明未跟踪条目分布为 48 个 `docs`、1 个 `signal_miner`、2 个 `tests`。

### P1-2：未跟踪生产代码/测试文件表述错误

位置：`docs/release-candidate-P11-1-change-inventory-20260627.md:83`、`docs/release-candidate-P11-1-change-inventory-20260627.md:85`

问题：

文档写道“两条链路的 48 个文档文件”以及“未发现未跟踪的生产代码或测试文件需要额外处理”。这不符合当前工作树事实。

当前 `??` 中包含：

```text
?? signal_miner/utils/
?? tests/test_connector_response_models.py
?? tests/test_source_clickthrough_contract.py
```

这些是 P9 预期范围内的未跟踪生产代码/测试文件，但不能写成没有未跟踪生产代码或测试文件。

影响：

会让发布准备阶段误以为未跟踪项只有文档，从而漏掉必须纳入或明确处理的运行时代码与测试文件。

验收要求：

修正发布候选建议：

- 明确 `??` 包含 48 个 docs 条目、1 个 `signal_miner/utils/` 生产代码目录、2 个测试文件。
- 明确这些未跟踪生产/测试文件属于 P9 预期范围，但仍需要在发布提交时人工确认纳入。
- 不再写“未发现未跟踪的生产代码或测试文件”。

### P2-1：变更分组摘要需同步计数

位置：`docs/release-candidate-P11-1-change-inventory-20260627.md:63` 至 `docs/release-candidate-P11-1-change-inventory-20260627.md:70`

问题：

当前摘要总计是 61，但实际工作树条目为 9 个修改文件 + 51 个未跟踪条目，共 60 个 `git status --short` 条目。文档的“生产代码/测试/文档”分组可以按逻辑文件归类，但需要明确它不是 `git status` 条目数量，避免和工作树概览冲突。

验收要求：

二选一修正：

- 将摘要改为按 `git status --short` 条目统计，并与 60 个条目一致。
- 或保留逻辑文件归类，但明确“该表按逻辑归属统计，不等同于 git status 条目数量”，并解释 `signal_miner/utils/` 目录在 status 中作为 1 个条目出现。

## 非阻断观察项

文档对 P9/P10 生产代码、测试文件的阶段归属大体正确；问题集中在计数与发布候选建议表述。

## 复验要求

返修后复验：

```bash
git status --short
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```
