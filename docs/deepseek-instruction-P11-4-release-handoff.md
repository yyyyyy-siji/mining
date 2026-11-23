# DeepSeek 执行指令：P11-4 发布交接包

## 任务目标

创建发布交接包，供人工执行最终暂存、提交和归档前使用。

目标交付物：

- `docs/release-candidate-P11-4-release-handoff-20260629.md`

## 背景 / 当前问题

P11-1 变更清单、P11-2 暂存计划、P11-3 冻结检查单已经通过验收。

但验收报告和本指令写入后，工作树未跟踪文档数量会继续增加。因此 P11-4 不应复写旧快照，而应生成一份面向人工提交的交接包，明确：

- 当前最终工作树状态
- 推荐提交分组
- 必须重新执行的门禁命令
- 哪些文档是 superseded，仅建议标注或排除
- 不执行任何实际 git 暂存或提交操作

## 允许修改范围

只允许新增：

- `docs/release-candidate-P11-4-release-handoff-20260629.md`

## 禁止修改范围

禁止修改：

- `frontend/`
- `signal_miner/`
- `tests/`
- 既有 `docs/release-candidate-P11-1-*`
- 既有 `docs/release-candidate-P11-2-*`
- 既有 `docs/release-candidate-P11-3-*`
- 既有验收报告和 DeepSeek 指令

禁止执行：

- `git add`
- `git commit`
- `git reset`
- `git checkout`
- 任何会修改索引或回滚工作树的命令

## 实现要求

在生成交接包前重新执行：

```bash
git status --short
git status --short | awk 'BEGIN{m=0;u=0} /^ M/{m++} /^\?\?/{u++} END{print "modified=" m; print "untracked=" u; print "total=" m+u}'
git status --short | sed -n '/^??/p' | awk '{print $2}' | sed 's#/.*##' | sort | uniq -c
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

交接包必须包含：

1. 当前工作树摘要
2. 当前未跟踪条目分布
3. 当前 `git diff --stat`
4. 门禁结果表
5. 推荐人工提交顺序
6. superseded 文档清单
7. 截图目录处理建议
8. 明确声明未执行 git 暂存、提交、回滚操作

## 验收标准

- 交接包中的数量必须与生成时最新命令输出一致
- `git diff --check` 必须通过且无输出
- 全部门禁命令必须通过
- 交接包不得声称已经完成提交或发布
- 交接包必须能让人工按分组完成最终审阅

## 交付报告模板

```markdown
## P11-4 交付报告

### 新增文件

| 文件 | 说明 |
|---|---|
| docs/release-candidate-P11-4-release-handoff-20260629.md | 发布交接包 |

### 验证结果

| 命令 | 结果 |
|---|---|
| git diff --check | 通过 / 不通过 |
| ruff check ... | 通过 / 不通过 |
| pytest PRD | 通过 / 不通过 |
| pytest P9/P10 回归 | 通过 / 不通过 |
| compileall | 通过 / 不通过 |
| node --check | 通过 / 不通过 |

### 风险

- ...
```
