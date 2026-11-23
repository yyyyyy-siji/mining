# P11-3 第四次返修指令：同步冻结检查单的最新工作树事实

目标文件：

- `docs/release-candidate-P11-3-freeze-checklist-20260628.md`

本轮只允许修改上述检查单文档。不要修改生产代码、测试代码或其他验收报告。不要执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 背景

三次返修后，代码侧门禁已经通过：

- `git diff --check` 通过且无输出
- ruff 通过
- PRD 路由与 P9/P10 回归 pytest 通过
- compileall 通过
- `node --check frontend/static/app.js` 通过

但检查单仍使用过期工作树摘要：

- 检查单写 `untracked=67`，验收时实际为 `69`
- 检查单写 `total=76`，验收时实际为 `78`
- 检查单写 docs 未跟踪条目 `64`，验收时实际为 `66`
- 检查单写 `git diff --stat` 为 `9 files, +507 -64`，验收时实际为 `9 files changed, 506 insertions(+), 63 deletions(-)`
- 检查单写 P11 文档小计 `18`，验收时实际 P11 未跟踪条目为 `20`

注意：上述数值是本次验收报告写入前的事实。当前返修时必须重新跑命令，不能直接复制这些数值。

## 必须执行的检查

在修改检查单前，重新执行：

```bash
git status --short
git status --short | awk 'BEGIN{m=0;u=0} /^ M/{m++} /^\\?\\?/{u++} END{print "modified=" m; print "untracked=" u; print "total=" m+u}'
git status --short | sed -n '/^??/p' | awk '{print $2}' | sed 's#/.*##' | sort | uniq -c
git status --short | sed -n '/^?? docs\/.*P11/p' | wc -l
git diff --stat
git diff --check
```

然后重新跑门禁：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 必须修改的检查单内容

请按最新命令输出同步：

1. 第 13-18 行的工作树摘要：
   - modified 文件数量
   - untracked 条目数量
   - git status 总条目
   - 未跟踪分布
   - `git diff --stat`
   - `git diff --check`

2. 第 52-57 行的文档统计：
   - P9 文档数量
   - P10 文档数量
   - P11 文档数量
   - 常规文档小计
   - 文档总计

3. 第 65-72 行的验证结果：
   - 保留最新门禁执行结果
   - `git diff --check` 必须写为通过、exit=0、无输出

4. 第 98-103 行遗留风险：
   - 保留 `StarletteDeprecationWarning` 为非阻塞风险
   - 保留“工作树持续增长”风险，但不要用它掩盖当前检查单必须同步最新事实的要求

## 验收标准

返修后必须满足：

- `docs/release-candidate-P11-3-freeze-checklist-20260628.md` 中的数量与最新 `git status --short` 完全一致
- `git diff --stat` 摘要与最新输出一致
- P11 文档小计与最新 `git status --short | sed -n '/^?? docs\/.*P11/p' | wc -l` 一致
- `git diff --check` 通过且无输出
- 全部门禁命令通过

交付时只回复：P11-3 第四次返修完成。
