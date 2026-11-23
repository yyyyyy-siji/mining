# P11-4 返修指令：同步发布交接包的最终工作树事实

目标文件：

- `docs/release-candidate-P11-4-release-handoff-20260629.md`

本轮只允许修改上述交接包文档。不要修改生产代码、测试代码、既有验收报告或其他 DeepSeek 指令。不要执行 `git add`、`git commit`、`git reset`、`git checkout`。

## 背景

P11-4 交接包已创建，但验收发现它没有计入交接包自身，导致工作树摘要和文档分类偏旧。

验收时发现的错误包括：

- 交接包写 `untracked=73`，验收时实际更高
- 交接包写 `total=82`，验收时实际更高
- 交接包写 docs 分布为 `70 docs`，验收时实际更高
- 交接包写 P11 文档合计为 `24`，验收时实际更高
- 交接包写 P9/P10 回归为 `47 passed`，验收时实际为 `43 passed`

注意：上述数值是本次验收报告写入前的事实。当前返修时必须重新执行命令，不能直接复制这些数值。

## 必须执行的检查

修改交接包前，重新执行：

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

重新执行门禁：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 必须修改的内容

在 `docs/release-candidate-P11-4-release-handoff-20260629.md` 中同步：

1. 当前工作树摘要：
   - modified 文件数量
   - untracked 条目数量
   - git status 总条目
   - `git diff --stat`
   - `git diff --check`

2. 未跟踪条目分布：
   - docs
   - signal_miner
   - tests

3. 文档分类：
   - P9 文档数量
   - P10 文档数量
   - P11 文档数量
   - 常规文档小计
   - 截图目录数量
   - docs 总分布

4. 推荐提交分组：
   - 文档归档分组中的 P9/P10/P11 数量必须与文档分类一致

5. 门禁结果：
   - `pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` 必须记录实际通过数量
   - 不允许写旧的 `47 passed`，除非本次重新执行后确实输出 `47 passed`

## 验收标准

返修后必须满足：

- 交接包中的数量与返修完成后的最新 `git status --short` 完全一致
- P9/P10/P11 文档分类与命令输出一致
- 常规文档小计、截图目录、docs 分布三者互相一致
- `git diff --check` 通过且无输出
- 全部门禁命令通过
- 门禁表记录的 passed 数量与实际输出一致
- 交接包仍明确声明未执行 git 暂存、提交、回滚操作

交付时只回复：P11-4 返修完成。
