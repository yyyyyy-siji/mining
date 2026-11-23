# P13-1 最终验收报告：置信度可信基线与伪向量熔断

验收日期：2026-07-10

结论：**通过。P13-1 关闭，允许进入 P13-2-1 混合金标基础设施。**

## 验收范围

- `docs/acceptance-P13-1-delivery-fix-3-20260710.md`
- `docs/P13-1-evidence/metrics.json`
- `docs/P13-1-evidence/behavior_probe.json`
- fix-2 遗留的 Streamlit 请求契约、浏览器验证器和报告一致性问题
- P13-1 已接受能力的完整回归

## 独立验证结果

| 验收项 | 结果 | 独立证据 |
| --- | --- | --- |
| Streamlit 不再发送 `confidence_threshold` | PASS | 两处 `/pipeline/run` payload 均只含 `max_signals` 和 `profile`；强制静态断言通过 |
| 浏览器验证器无源码 fallback | PASS | 不含 `doSimpleVerify`、`app.js`、`http.get`；静态断言参与 metrics 顶层 `passed` |
| 浏览器不可用语义 | PASS | 本机缺少 Playwright 时输出 `status=BLOCKED`、`passed=false`，进程退出码为 2 |
| DOM 断言失败语义 | PASS | 验证器以 `allPassed ? 0 : 1` 结束；异常路径退出 1 |
| 真实低分信号入库 | PASS | 行为探针中 `model_self_score=0.01`、`calibrated_confidence=null`，记录真实持久化 |
| 无真实 Embedding 能力熔断 | PASS | dedup / cluster / asset await count 全部为 0 |
| 真实 Embedding 全失败熔断 | PASS | `stored_real_count=0`，三类语义调用均为 0，`semantic_phase=skipped` |
| SSE 降级终态 | PASS | `completed_with_skips` 被识别为终态，流关闭且订阅者清理 |
| 正式库计数守恒 | PASS | 新增 pseudo embedding、dismissed、theme 均为 0 |
| 聚焦测试 | PASS | `24 passed` |
| 全量回归 | PASS | `196 passed, 3 warnings`；由 metrics 脚本实际子进程执行并解析 |
| Ruff / Node / diff | PASS | Ruff、两个 Node 语法检查、`git diff --check` 均退出 0 |

## 真实浏览器复验

指挥官使用本次代码启动本地服务并检查静态 SPA 的真实 DOM：

- Signals 页不存在裸“最低置信度”，存在“最低模型自评分”和“未校准”限定语。
- Signals/Pipeline 页均不存在 `#pipe-confidence`。
- Pipeline 页不显示最低置信度控件，主模型、多模态入口和 AIGC profile 可见。
- 截图：`docs/P13-1-screenshots/acceptance-fix3-pipeline-commander-20260710.png`。

交付报告将浏览器证据标为 BLOCKED 是诚实表述；指挥官环境已补齐该项，因此不构成产品验收阻断。

## 回归确认

- `calibrated_confidence` 仍为空，不存在伪校准概率。
- 后端仅保留 deprecated 兼容字段，不再由两个前端作为挖矿决策参数发送。
- 未恢复基于未校准模型自评分的 destructive dismiss。
- 未对历史 1,425 条信号和 1,408 条 dismissed 记录做批量改写。
- P13-2、P13-3、P13-5 能力未被提前宣称完成。

## 非阻断观察

- `frontend/app.py` 仍有两个未使用的 `conf_threshold = 0.5` 局部变量。它们不进入 payload、决策或展示，不影响本阶段契约；后续前端整理时可删除。
- 当前正式库在本次 Signals 页复验时没有渲染信号卡，但筛选语义、未校准限定语和控件移除均可由真实 DOM 验证。卡片文案已在前一次 fix-2 实际 DOM 复验中覆盖。

## 最终结论

P13-1 的核心安全目标已经达到：未校准 LLM 自评分不再被伪装成概率或用于破坏性决策，伪向量/不可用真实向量不会继续驱动去重、聚类和资产生成；fix-3 的防复发门禁有效。

下一阶段仅开放 **P13-2-1：混合金标协议、脱敏导出、预标注隔离与冻结清单**。允许development/calibration使用机器suggestion降低人工成本，但冻结test必须盲标；在真实人工验证和独立测试集到位前，不得写入或展示校准概率。
