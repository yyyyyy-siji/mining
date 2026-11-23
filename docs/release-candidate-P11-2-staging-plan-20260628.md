# P11-2 发布候选暂存计划

验收日期：2026-06-28

> 本计划仅给出建议分组、动作与验证命令，不执行 `git add`、`git commit` 或任何会修改工作树或索引的操作。

---

## 工作树快照

`git status --short`（2026-06-28 时点，含 P11-2 复验/二次返修文档）：

```
modified = 9
untracked = 60
total = 69 条目  （docs = 57，signal_miner/utils = 1，tests = 2）
```

---

## 暂存分组

### G1 — P9 来源点击链路生产代码

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `frontend/app.py` | M | 纳入发布候选 | `_render_source_link` 安全链接渲染 |
| `frontend/static/app.js` | M | 纳入发布候选 | 运行时 source link 展示 |
| `signal_miner/routes/assets.py` | M | 纳入发布候选 | 响应模型 `source_url` |
| `signal_miner/routes/connectors.py` | M | 纳入发布候选 | `ConnectorListResponse` / `GitHubFetchResponse` |
| `signal_miner/routes/feedback.py` | M | 纳入发布候选 | raw feedback 响应 source 字段 |
| `signal_miner/routes/signals.py` | M | 纳入发布候选 | signal 响应 source 字段 |
| `signal_miner/utils/url_templates.py` | ?? | 纳入发布候选 | URL 模板辅助工具 |
| `signal_miner/utils/__init__.py` | ?? | 纳入发布候选 | 包标记（空文件） |

验证命令：
```bash
ruff check signal_miner/routes/assets.py
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py -q
```

---

### G2 — P9 来源点击链路测试

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `tests/test_source_clickthrough_contract.py` | ?? | 纳入发布候选 | 前端 source link 可点击性与运行时契约 |
| `tests/test_connector_response_models.py` | ?? | 纳入发布候选 | connector 响应模型字段契约 |

验证命令：
```bash
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py -q
```

---

### G3 — P10 PRD 链路生产代码

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | M | 纳入发布候选 | opportunities_context、输出结构、evidence 来源链接 |

验证命令：
```bash
ruff check signal_miner/pipeline/prd_generator.py
.venv/bin/python -m pytest tests/test_prd_generator.py -q
```

---

### G4 — P10 PRD 链路测试

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `tests/test_prd_generator.py` | M | 纳入发布候选 | generator 持久化/审计/context/结构/链接契约 |
| `tests/test_prd_routes.py` | M | 纳入发布候选 | PRD 路由响应/format/错误路径契约 |

验证命令：
```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

---

### G5 — P9/P10/P11 验收与指令文档（可存档）

| 类别 | 文件数 | 建议动作 | 原因 |
|---|---|---|---|
| P9 最终验收报告 (`docs/acceptance-P9-*-final-pass-*.md`) | 8 | 纳入仓库存档 | P9 各阶段验收结论 |
| P9 交付/验收范围报告 (`docs/acceptance-P9-*-source-clickthrough.md` 等) | 6 | 纳入仓库存档 | P9 详细验收范围 |
| P9 指令文档 (`docs/deepseek-instruction-P9-*.md`) | 8 | 纳入仓库存档 | P9 各阶段指令 |
| P10 最终验收报告 (`docs/acceptance-P10-*-final-pass-*.md`) | 8 | 纳入仓库存档 | P10 各阶段验收结论 |
| P10 交付/验收范围报告 (`docs/acceptance-P10-*-delivery-*.md` 等) | 7 | 纳入仓库存档 | P10 详细交付范围 |
| P10 指令文档 (`docs/deepseek-instruction-P10-*.md`) | 8 | 纳入仓库存档 | P10 各阶段指令 |
| P11 验收报告 (`docs/acceptance-P11-*.md`) | 4 | 纳入仓库存档 | P11-1 change-inventory + final-pass、P11-2 staging-plan + refail |
| P11 指令文档 (`docs/deepseek-instruction-P11-*.md`) | 5 | 纳入仓库存档 | release-candidate x2 + fix x3 |
| P11 发布候选文档 (`docs/release-candidate-P11-*.md`) | 2 | 纳入仓库存档 | 变更清单 + 暂存计划 |
| **分类表合计** | **56** | | |

---

### G6 — 截图/二进制资产

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `docs/P9-2-screenshots/` (8 文件) | ?? | 人工确认后纳入 | 运行时验证截图；建议划入 `docs/assets/` 或由 git-lfs 管理 |

---

### G7 — 需人工确认或可排除

| 文件 | 状态 | 建议动作 | 原因 |
|---|---|---|---|
| `docs/acceptance-P10-7-final-summary.md` | ?? | 可排除 | 已被 `acceptance-P10-final-summary-20260627.md` 取代 |
| `docs/acceptance-P11-1-change-inventory.md` | ?? | 可排除或标明 superseded | 验收报告非交付物，已被返修复验报告覆盖 |

---

## 暂存分组摘要

| 分组 | 建议动作 | 条目 | 构成 |
|---|---|---|---|
| G1 — P9 生产代码 | 纳入发布候选 | 7 | 6 modified + 1 untracked（`utils/` 目录在 status 中是 1 条目） |
| G2 — P9 测试 | 纳入发布候选 | 2 | 2 untracked |
| G3 — P10 生产代码 | 纳入发布候选 | 1 | 1 modified |
| G4 — P10 测试 | 纳入发布候选 | 2 | 2 modified |
| G5 — 文档归档 | 归档 | 57 | 57 untracked（含截图和可排除项） |
| 　 G6 — 截图资产 | G5 子项，人工确认 | (1) | `docs/P9-2-screenshots/`，不重复计入 total |
| 　 G7 — 可排除项 | G5 子项，可排除 | (2) | superseded 文档 x2，不重复计入 total |
| **总计** | — | **69** | modified=9 + untracked=60；与 `git status` 完全闭合 |

> G1–G4 合计 **12 个代码/测试条目**，是发布候选的运行时必需部分。G5 为 **57 个纯文档条目**（含 G6 截图 1 项 + G7 可排除 2 项），不影响运行时，建议纳入存档但可在 commit 粒度上拆分。G5 分类表各行合计 = 56 + G6 截图 1 = 57 = docs 总条目数。

---

## 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py` | 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 通过 | 18 passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 通过 | 43 passed, 1 StarletteDeprecationWarning (非阻塞) |
| `git status --short` | — | modified=9, untracked=60, total=69 |

---

## 人工确认项

1. **G6 截图目录** `docs/P9-2-screenshots/`：是否纳入仓库？如纳入，放入 `docs/` 还是 `docs/assets/`？
2. **G7 可排除项** `docs/acceptance-P10-7-final-summary.md` 和 `docs/acceptance-P11-1-change-inventory.md`：删除还是保留并标注 superseded？
3. **commit 粒度**：建议至少拆分为 "P9 source clickthrough"（G1+G2）和 "P10 PRD pipeline"（G3+G4）两个独立提交，文档可单独提交或归入最后一个提交。

## 遗留风险

- 本计划仅为建议，未执行任何 git 操作。发布前需由人工确认分组并执行 `git add`/`git commit`。
- 工作树会随后续验收/指令文档继续增长；发布冻结前需以最新 `git status --short` 为准。
