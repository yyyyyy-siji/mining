# P11-3 发布冻结前最终检查单

验收日期：2026-06-28

> 本检查单用于人工执行暂存/提交前的最终核对。已明确不执行任何 `git add`、`git commit` 或会修改工作树/索引的操作。

---

## 一、工作树摘要

| 项 | 数量/结果 |
|---|---|
| modified 文件 (` M`) | 9 |
| untracked 条目 (`??`) | 71 |
| git status 总条目 | 80 |
| 未跟踪分布 | docs 68、signal_miner/utils 1、tests 2 |
| `git diff --stat` | 9 files, +506 −63 |
| `git diff --check` | 通过，exit=0 |

---

## 二、P9 来源点击链路 — 文件清单

| 文件 | 状态 | 检查 | 备注 |
|---|---|---|---|
| `frontend/app.py` | M | ✓ 通过 lint | `_render_source_link` 安全渲染 |
| `frontend/static/app.js` | M | ✓ node --check OK | 运行时 source link 展示 |
| `signal_miner/routes/assets.py` | M | ✓ | `source_url` 响应字段 |
| `signal_miner/routes/connectors.py` | M | ✓ | 响应模型 |
| `signal_miner/routes/feedback.py` | M | ✓ | raw feedback 响应 |
| `signal_miner/routes/signals.py` | M | ✓ | signal 响应 |
| `signal_miner/utils/` | ?? | ✓ | url_templates.py + __init__.py |
| `tests/test_source_clickthrough_contract.py` | ?? | ✓ | 前端 source link 契约 |
| `tests/test_connector_response_models.py` | ?? | ✓ | connector 响应模型契约 |

---

## 三、P10 PRD 链路 — 文件清单

| 文件 | 状态 | 检查 | 备注 |
|---|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | M | ✓ | opportunities_context / output structure / evidence source links |
| `tests/test_prd_generator.py` | M | ✓ | generator 持久化/审计/context/结构/链接 |
| `tests/test_prd_routes.py` | M | ✓ | PRD 路由响应/format/错误路径 |

---

## 四、文档/截图/可排除项 — 人工确认清单

| 类别 | 条目 | 建议动作 | 状态 |
|---|---|---|---|
| P9 验收报告 + 指令 | 22 | 纳入仓库存档 | 待人工确认 |
| P10 验收报告 + 指令 | 23 | 纳入仓库存档 | 待人工确认 |
| P11 验收报告 + 指令 + release-candidate | 22 | 纳入仓库存档 | 待人工确认 |
| **常规文档小计** | **67** | | |
| `docs/P9-2-screenshots/` | 1 目录 (8 文件) | 人工确认后纳入，建议 `docs/assets/` 或 git-lfs | 待人工确认 |
| **文档总计** | **68** | | |

> P10 验收报告中 `acceptance-P10-7-final-summary.md` 和 P11 验收报告中 `acceptance-P11-1-change-inventory.md` 已被后续版本取代，建议提交时标注 superseded 或单独排除。

---

## 五、验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py` | 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 通过 | 18 passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 通过 | 43 passed, 1 StarletteDeprecationWarning (非阻塞) |
| `.venv/bin/python -m compileall signal_miner frontend/app.py` | 通过 | 所有模块编译成功 |
| `node --check frontend/static/app.js` | 通过 | JS 语法无错误 |
| `git diff --check` | 通过 | exit=0，无输出 |

---

## 六、建议人工提交顺序

| 顺序 | 提交范围 | 文件数 | 验证命令 |
|---|---|---|---|
| 1 | P9 source clickthrough 生产代码 + 测试 | 9 | `pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py -q` |
| 2 | P10 PRD pipeline 生产代码 + 测试 | 3 | `pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` |
| 3 | P9/P10/P11 验收与指令文档 | 67 | — |
| 4 | 截图资产（人工确认后） | 1 目录 | — |

---

## 七、不执行 git 操作声明

本检查单未执行以下操作：
- `git add`
- `git commit`
- `git reset`
- `git checkout`
- 任何会修改工作树或索引的 git 命令

---

## 八、遗留风险

| 风险 | 说明 |
|---|---|
| `StarletteDeprecationWarning` | TestClient/httpx 兼容性弃用，非本项目运行时变更 |
| 工作树持续增长 | 封存提交前需以最新 `git status --short` 为最终依据 |
