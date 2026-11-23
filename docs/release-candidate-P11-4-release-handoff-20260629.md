# P11-4 发布交接包

验收日期：2026-06-29

> 本交接包供人工执行最终暂存、提交和归档前使用。**不执行任何 `git add`、`git commit`、`git reset`、`git checkout` 或会修改索引/工作树的命令。**

---

## 一、当前工作树摘要

| 项 | 数量/结果 |
|---|---|
| modified 文件 (` M`) | 9 |
| untracked 条目 (`??`) | 76 |
| git status 总条目 | 85 |
| `git diff --stat` | 9 files, +506 −63 |
| `git diff --check` | 通过，exit=0，无输出 |

### 未跟踪条目分布

```
 73 docs
  1 signal_miner
  2 tests
```

### 文档分类

| 阶段 | 验收报告 | 指令文档 | 发布候选文档 | 合计 |
|---|---|---|---|---|
| P9 | 14 | 8 | — | 22 |
| P10 | 15 | 8 | — | 23 |
| P11 | 11 | 12 | 4 | 27 |
| 截图 (`P9-2-screenshots/`) | — | — | — | 1 |
| **合计** | **40** | **28** | **4** | **73** |

---

## 二、推荐提交分组

### Commit 1 — P9 来源点击链路

| 文件 | 状态 |
|---|---|
| `frontend/app.py` | M |
| `frontend/static/app.js` | M |
| `signal_miner/routes/assets.py` | M |
| `signal_miner/routes/connectors.py` | M |
| `signal_miner/routes/feedback.py` | M |
| `signal_miner/routes/signals.py` | M |
| `signal_miner/utils/` | ?? |
| `tests/test_source_clickthrough_contract.py` | ?? |
| `tests/test_connector_response_models.py` | ?? |

验证：`pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py -q`

### Commit 2 — P10 PRD 链路

| 文件 | 状态 |
|---|---|
| `signal_miner/pipeline/prd_generator.py` | M |
| `tests/test_prd_generator.py` | M |
| `tests/test_prd_routes.py` | M |

验证：`pytest tests/test_prd_generator.py tests/test_prd_routes.py -q`

### Commit 3 — 文档归档

| 类别 | 数量 | 建议 |
|---|---|---|
| P9 文档 | 22 | 纳入 |
| P10 文档 | 23 | 纳入 |
| P11 文档 | 27 | 纳入 |
| `docs/P9-2-screenshots/` | 1 目录 (8 文件) | 人工确认后纳入，建议 `docs/assets/` 或 git-lfs |

### Superseded 文档清单（建议标注或排除）

| 文件 | 说明 |
|---|---|
| `docs/acceptance-P10-7-final-summary.md` | 已被 `acceptance-P10-final-summary-20260627.md` 取代 |
| `docs/acceptance-P11-1-change-inventory.md` | 已被返修复验报告覆盖 |

---

## 三、门禁结果

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过，exit=0，无输出 |
| `ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py` | 通过 |
| `pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 18 passed |
| `pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 43 passed, 1 StarletteDeprecationWarning (非阻塞) |
| `compileall signal_miner frontend/app.py` | 全部模块编译成功 |
| `node --check frontend/static/app.js` | 通过 |

---

## 四、不执行 git 操作声明

本交接包未执行：
- `git add`
- `git commit`
- `git reset`
- `git checkout`
- 任何会修改工作树或索引的命令

---

## 五、遗留风险

- `StarletteDeprecationWarning`：Starlette TestClient/httpx 兼容性弃用，非本项目运行时变更，不阻塞。
- PRD generator 的 LLM 调用始终以 mock 覆盖生成层契约；真实 LLM 输出质量需人工审查。
- 文档持续增长：提交时应以最新 `git status --short` 为最终依据。
