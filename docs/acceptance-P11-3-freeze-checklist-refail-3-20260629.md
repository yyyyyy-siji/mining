# P11-3 发布冻结前最终检查单验收报告（三次返修后）

验收日期：2026-06-29

结论：不通过。

本次返修已修复上一轮的 `git diff --check` 旧 warning：当前 `git diff --check` 通过且无输出，`tests/test_prd_routes.py` 文件尾部也不再存在额外空行。代码与测试门禁全部通过。

但交付物 `docs/release-candidate-P11-3-freeze-checklist-20260628.md` 的工作树摘要仍未按最新代码事实同步，作为“发布冻结前最终检查单”不能通过验收。

## 阻塞问题

### 1. 工作树摘要与当前 `git status --short` 不一致

检查单第 13-16 行写入：

| 项 | 检查单记录 |
|---|---:|
| modified 文件 (` M`) | 9 |
| untracked 条目 (`??`) | 67 |
| git status 总条目 | 76 |
| 未跟踪分布 | docs 64、signal_miner/utils 1、tests 2 |

本次验收执行结果为：

```text
modified=9
untracked=69
total=78
```

未跟踪分布为：

```text
66 docs
1 signal_miner
2 tests
```

差异：

- `untracked`：检查单 67，实际 69
- `total`：检查单 76，实际 78
- docs 未跟踪条目：检查单 64，实际 66

### 2. `git diff --stat` 摘要未同步

检查单第 17 行写入：

```text
9 files, +507 -64
```

本次验收执行结果为：

```text
9 files changed, 506 insertions(+), 63 deletions(-)
```

差异来自返修后删除文件尾部空行，但检查单没有同步更新。

### 3. P11 文档小计未同步

检查单第 54 行写入 P11 验收报告、指令和 release-candidate 为 18。

本次验收执行：

```text
git status --short | sed -n '/^?? docs\/.*P11/p' | wc -l
```

结果为：

```text
20
```

当前 P11 未跟踪条目包括上一轮验收生成的：

- `docs/acceptance-P11-3-freeze-checklist-refail-2-20260628.md`
- `docs/deepseek-instruction-P11-3-fix-3.md`

交付检查单未纳入这两个事实。

## 已通过项

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

## 验收结论

代码侧门禁通过，但 P11-3 交付物的核心目标是冻结前检查单本身。当前检查单仍包含过期的工作树数量、docs 分布、P11 文档小计和 `git diff --stat` 摘要，因此本轮验收不通过。

返修时不要直接抄本报告中的数量；本报告和下一份返修指令写入后，工作树还会继续增加。必须在返修时重新执行命令，并以当时最新输出更新检查单。
