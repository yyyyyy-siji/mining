# DeepSeek 执行指令：P11-5 提交前最终人工复核

## 任务目标

在人工执行 `git add` / `git commit` 之前，完成一次不修改代码、不修改索引的最终复核，并输出给人工操作者使用的最终口头/文本结论。

本阶段不要求新增交付文档，避免继续制造新的工作树计数漂移。

## 背景 / 当前问题

P11-4 发布交接包已通过验收。但 P11-4 最终验收报告和本指令写入后，工作树未跟踪文档数量会再次增加。

因此真正提交前，不能直接复用 P11-4 交接包里的数量作为最终提交事实；必须重新读取当前工作树。

## 允许操作

只允许执行只读检查命令：

- `git status --short`
- `git diff --stat`
- `git diff --check`
- `git diff --cached --stat`
- 既有门禁命令

允许输出一份文本交付报告，但不要新增或修改仓库文件。

## 禁止操作

禁止执行：

- `git add`
- `git commit`
- `git reset`
- `git checkout`
- 修改 `frontend/`
- 修改 `signal_miner/`
- 修改 `tests/`
- 新增或修改 `docs/`
- 任何会修改工作树或索引的命令

## 必须执行的检查

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
git diff --cached --stat
```

重新执行门禁：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```

## 验收标准

- 不新增、不修改任何仓库文件
- 不执行任何暂存、提交、回滚操作
- `git diff --check` 通过且无输出
- `git diff --cached --stat` 无输出
- 全部门禁命令通过
- 输出中明确列出最终 `modified`、`untracked`、`total`、docs 分布、P9/P10/P11 文档数量
- 输出中明确提示人工操作者：最终提交范围必须以该次 `git status --short` 为准

## 交付报告模板

```markdown
## P11-5 提交前最终复核报告

结论：通过 / 不通过

### 当前工作树

- modified:
- untracked:
- total:
- 未跟踪分布：

### 文档分类

- P9:
- P10:
- P11:
- 常规文档:
- 截图目录:

### 门禁

| 命令 | 结果 |
|---|---|
| git diff --check | 通过 / 不通过 |
| git diff --cached --stat | 无输出 / 有输出 |
| ruff check ... | 通过 / 不通过 |
| pytest PRD | 通过 / 不通过 |
| pytest P9/P10 回归 | 通过 / 不通过 |
| compileall | 通过 / 不通过 |
| node --check | 通过 / 不通过 |

### 操作声明

未执行 git add、git commit、git reset、git checkout。
```
