# P11-1 发布候选变更清单

验收日期：2026-06-27

---

## 工作树概览

`git status --short` 输出 9 个修改文件（` M`）和 53 个未跟踪条目（`??`）。未跟踪条目分布：50 个在 `docs/`，1 个在 `signal_miner/utils/`（生产代码目录），2 个在 `tests/`。

---

## 一、P9 来源点击链路 — 生产代码

| 文件 | 变更主题 | 对应保护测试 |
|---|---|---|
| `frontend/app.py` | 新增 `_render_source_link()`，对 source URL 做 HTML escaping 后渲染可点击链接 | `tests/test_source_clickthrough_contract.py` |
| `frontend/static/app.js` | 运行时 source URL 渲染、feedback detail 中 source 链接的可点击展示 | `tests/test_source_clickthrough_contract.py` |
| `signal_miner/routes/assets.py` | 响应模型中补充 `source_url` 字段，传递到前端 | `tests/test_source_clickthrough_contract.py` |
| `signal_miner/routes/feedback.py` | raw feedback 列表/详情响应增加 source 相关字段 | `tests/test_source_clickthrough_contract.py` |
| `signal_miner/routes/signals.py` | signal 响应模型中补充可追溯的 source 信息 | `tests/test_source_clickthrough_contract.py` |
| `signal_miner/routes/connectors.py` | 新增 `ConnectorListResponse` / `GitHubFetchResponse` 响应模型 | `tests/test_connector_response_models.py` |
| `signal_miner/utils/url_templates.py` | URL 模板辅助工具（新文件） | `tests/test_source_clickthrough_contract.py` |
| `signal_miner/utils/__init__.py` | 包初始化（空文件） | — |

## 二、P9 来源点击链路 — 测试

| 文件 | 归属阶段 | 变更主题 |
|---|---|---|
| `tests/test_source_clickthrough_contract.py` | P9-1/2 | 前端 source link 可点击性与 runtime 渲染契约 |
| `tests/test_connector_response_models.py` | P9-3/4 | connector 响应模型字段契约 |

## 三、P9 来源点击链路 — 文档

| 类别 | 文件数 | 说明 |
|---|---|---|
| 最终验收报告 (final-pass) | 8 | P9-1 至 P9-7 各阶段 + P9 总结 |
| 指令文档 (deepseek-instruction) | 8 | P9-1 至 P9-7 各阶段指令 |
| 验收/交付报告 (delivery/acceptance) | 6 | 各阶段详细验收范围与交付报告 |
| 截图 (screenshots) | 1 目录 | `docs/P9-2-screenshots/` (8 文件) |

## 四、P10 PRD 链路 — 生产代码

| 文件 | 变更主题 | 对应保护测试 |
|---|---|---|
| `signal_miner/pipeline/prd_generator.py` | P10-4: `opportunities_context` 注入 prompt → P10-5: 输出结构要求 `## 关联机会与痛点` → P10-6: evidence `source_url`/`external_url` 进入 Markdown 链接 | `tests/test_prd_generator.py` |

## 五、P10 PRD 链路 — 测试

| 文件 | 归属阶段 | 变更主题 |
|---|---|---|
| `tests/test_prd_routes.py` | P10-1/2 | PRD 路由 500 修复 + 响应字段/format/错误路径契约 |
| `tests/test_prd_generator.py` | P10-3/4/5/6 | generator 持久化/审计 + 机会痛点 context + 输出结构 + 证据来源链接 |

## 六、P10 PRD 链路 — 文档

| 类别 | 文件数 | 说明 |
|---|---|---|
| 最终验收报告 (final-pass) | 8 | P10-1 至 P10-7 各阶段 + P10 总结 |
| 指令文档 (deepseek-instruction) | 9 | P10-1 至 P10-7、P10-7-fix、P11-1 指令 |
| 验收/交付报告 (delivery/acceptance) | 7 | 各阶段交付报告与详细验收范围 |

## 七、变更分组摘要

按 `git status --short` 条目统计（`M` = 已修改，`??` = 未跟踪）：

| 分组 | 生产/测试 (M) | 生产/测试 (??) | 文档 (??) | 状态条目合计 |
|---|---|---|---|---|
| P9 来源点击链路 | 6 | 3 | 23 | 32 |
| P10 PRD 链路 | 3 | 0 | 23 | 26 |
| P11 清单 | 0 | 0 | 4 | 4 |
| **总计** | **9** | **3** | **50** | **62** |

> 注：P9 `??` 包含 `signal_miner/utils/`（生产代码目录，1 条目）和 2 个测试文件；文档列含 `P9-2-screenshots/` 截图目录。该表按 git status 条目统计，与工作树概览的 `modified=9, untracked=53, total=62` 一致。

## 八、验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py` | 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 通过 | 18 passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 通过 | 43 passed, 1 StarletteDeprecationWarning（非阻塞） |

## 九、发布候选建议

- **P9 来源点击链路** 与 **P10 PRD 链路** 的生产代码和测试均已完成契约验收，可以作为发布候选推进。
- 两个链路的 50 个文档条目（含指令、验收报告、截图）全部为验收/指令/截图辅助物，不影响运行时行为，可选择性纳入仓库归档。
- `StarletteDeprecationWarning` 来自 Starlette TestClient / httpx 兼容性弃用，非本项目的运行时变更，不阻塞。
- 未跟踪条目中包含 1 个生产代码目录（`signal_miner/utils/`）和 2 个测试文件（`tests/test_connector_response_models.py`、`tests/test_source_clickthrough_contract.py`），均属于 P9 来源点击链路预期范围，但在发布提交时需人工确认纳入。

## 十、需要人工确认

| 文件/目录 | 问题 | 建议 |
|---|---|---|
| `docs/P9-2-screenshots/` | 截图二进制文件（8 个），是否纳入仓库 | 建议归入 `docs/assets/` 或 git-lfs |
| `docs/acceptance-P10-7-final-summary.md` | P10-7 初版文档（已被 `acceptance-P10-final-summary-20260627.md` 取代） | 可删除或明确标注为 superseded |
| `signal_miner/utils/__init__.py` | 空文件，仅标记包 | 确认是否需要保留（当前只被 `url_templates.py` 使用） |

## 十一、遗留风险

- 所有文档尚未 `git add`，当前工作树状态不是提交就绪态。本清单仅作为变更盘点，不包含 git 操作。
- PRD generator 的 LLM 调用始终以 mock 覆盖生成层契约；真实 LLM 输出质量需人工审查。
