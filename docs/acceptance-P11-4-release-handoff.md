# P11-4 验收报告：发布交接包

验收日期：2026-06-29

结论：不通过，需要返修。

## 已通过项

交付物存在：

- `docs/release-candidate-P11-4-release-handoff-20260629.md`

代码与测试门禁实际通过：

```text
git diff --check
```

通过，exit=0，无输出。

```text
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

通过：

```text
All checks passed!
```

```text
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

通过：

```text
18 passed
```

```text
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

通过：

```text
43 passed, 1 StarletteDeprecationWarning
```

```text
.venv/bin/python -m compileall signal_miner frontend/app.py
```

通过。

```text
node --check frontend/static/app.js
```

通过，exit=0，无输出。

## 阻断问题

### P0-1：交接包工作树摘要没有计入交接包自身

位置：

- `docs/release-candidate-P11-4-release-handoff-20260629.md` 第 13-24 行

问题：

交接包写入：

```text
modified=9
untracked=73
total=82
docs=70
signal_miner=1
tests=2
```

验收时当前仓库事实为：

```text
modified=9
untracked=74
total=83
```

未跟踪分布为：

```text
71 docs
1 signal_miner
2 tests
```

证据：

```bash
git status --short | awk 'BEGIN{m=0;u=0} /^ M/{m++} /^\?\?/{u++} END{print "modified=" m; print "untracked=" u; print "total=" m+u}'
git status --short | sed -n '/^??/p' | awk '{print $2}' | sed 's#/.*##' | sort | uniq -c
```

影响：

P11-4 的核心目标是给人工提交前使用的最终交接包。如果交接包没有计入自身，提交前清点会少一项，不能作为最终交接依据。

验收要求：

返修时重新执行命令，并让交接包中的工作树摘要与返修完成后的最新输出一致。

### P0-2：P11 文档分类数量错误

位置：

- `docs/release-candidate-P11-4-release-handoff-20260629.md` 第 27-35 行
- `docs/release-candidate-P11-4-release-handoff-20260629.md` 第 67-74 行

问题：

交接包写 P11 文档合计为 24，但验收时当前事实为 25。

证据：

```bash
git status --short | sed -n '/^?? docs\/.*P11/p' | wc -l
```

输出：

```text
25
```

当前常规文档小计为：

```text
P9=22
P10=23
P11=25
常规文档=70
截图目录=1
docs 分布=71
```

影响：

文档归档分组数量与实际不一致，会误导人工提交范围。

验收要求：

返修后 P9、P10、P11、常规文档、截图目录、docs 分布必须全部互相一致。

### P1-1：门禁结果记录与实际输出不一致

位置：

- `docs/release-candidate-P11-4-release-handoff-20260629.md` 第 91-92 行

问题：

交接包记录 P9/P10 回归命令为：

```text
47 passed, 1 StarletteDeprecationWarning
```

验收时执行同一组命令实际输出为：

```text
43 passed, 1 StarletteDeprecationWarning
```

影响：

虽然测试通过，但交接包作为最终人工交接依据，不能记录错误的门禁数量。

验收要求：

重新执行门禁并记录实际输出，不允许复用旧报告中的测试数量。

## 非阻断观察项

- `StarletteDeprecationWarning` 仍为非阻断风险，当前不影响本阶段验收。
- `git diff --stat` 与 `git diff --check` 当前记录正确。

## 复验要求

返修时不要直接复制本报告中的数量。本报告和返修指令写入后，工作树会新增文档条目。

复验前必须重新执行：

```bash
git status --short
git status --short | awk 'BEGIN{m=0;u=0} /^ M/{m++} /^\?\?/{u++} END{print "modified=" m; print "untracked=" u; print "total=" m+u}'
git status --short | sed -n '/^??/p' | awk '{print $2}' | sed 's#/.*##' | sort | uniq -c
git status --short | sed -n '/^?? docs\/.*P9/p' | grep -v '^?? docs/P9-2-screenshots/' | wc -l
git status --short | sed -n '/^?? docs\/.*P10/p' | wc -l
git status --short | sed -n '/^?? docs\/.*P11/p' | wc -l
git status --short | sed -n '/^?? docs\//p' | grep -v '^?? docs/P9-2-screenshots/' | wc -l
git diff --stat
git diff --check
```

并重新执行全部门禁命令。
