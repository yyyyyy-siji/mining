# P13-1 fix-1 指挥官独立复验报告

验收日期：2026-07-10

验收对象：`docs/acceptance-P13-1-delivery-20260710.md` 及 fix-1 实现

验收角色：Commander

## 结论

**FAIL，需要继续返工。P13-1 不得关闭，不得进入 P13-2。**

执行方把浏览器子项自评为 BLOCKED，这一点符合“无法验证不得自评 PASS”的规则；但本次还存在多个与浏览器环境无关的确定性失败，因此整体不能只记为 BLOCKED：

1. 支持真实 Embedding 的 adapter 如果全部 `embed()` 调用失败，系统仍返回 `embeddings_generated`，并继续执行 dedup、cluster 和 asset。
2. `metrics.json` 再次出现顶层 `passed=true`，但同一文件内部 `low_score_persists=false`、测试计数为 0，且缺少任务书规定的前后 delta。
3. `completed_with_skips` 没有贯通 SSE 和 SPA 终态，浏览器会继续等待，无法可靠展示“跳过后完成”。
4. 当前 Ruff 实际失败、全量测试实际为 196 项，均与交付报告不一致。

下一次返工指令：`docs/deepseek-instruction-P13-1-fix-2.md`。

## 独立验收结果

| 验收项 | 独立结果 | 判定 |
| --- | --- | --- |
| 合法低分信号入库 | 0.01 分 + legacy threshold 0.99，真实入库 | 通过 |
| 置信度字段 | `model_self_score=0.01`、`calibrated_confidence=None` | 通过 |
| DeepSeek 直接无 Embedding | `skipped_no_real_embedding` 时 dedup/cluster/asset 为 0 | 通过 |
| 真实 Embedding 全部失败 | dedup/cluster/asset 均为 1，最终 status=completed | **失败，P0** |
| Embedding 阶段抛异常 | 三类调用为 0，但 `semantic_phase=completed`、完成文案错误 | **失败** |
| SSE `completed_with_skips` | 首条事件收到后流仍保持打开 | **失败，P0** |
| 机器 JSON 严格断言 | `low_score_persists=false`，且缺少要求的 delta 字段 | **失败，P0** |
| Ruff | exit 1，3 个错误 | **失败** |
| Node 语法 | app.js / browser verifier 均 exit 0 | 通过 |
| `git diff --check` | exit 0 | 通过 |
| 聚焦回归 | 43 passed | 通过 |
| 全量回归 | 196 passed，3 warnings | 通过；报告数字漂移 |
| Alembic 临时库往返 | downgrade -1 → upgrade head，计数守恒 | 通过 |
| 信号页真实浏览器 DOM | 显示“模型自评（未校准）”，默认筛选 0 | 通过 |
| Pipeline 页真实浏览器 DOM | 可见阈值控件已移除，但仍存在隐藏 0.5 input | 部分通过 |
| Pipeline 动态 skip 结果 | SSE/SPA 不识别新终态 | 失败 |

## P0 阻断问题

### P0-1：真实 Embedding 全部失败仍穿透熔断

位置：

- `signal_miner/pipeline/embedding.py:87-137`
- `signal_miner/pipeline/runner.py:193-247`

问题：

`generate_embeddings_for_signals()` 只要发生过调用，不论成功数是否为 0，最后都返回：

```text
embeddings_generated
```

runner 仅检查该字符串，因而把“0 条真实向量写入、1 条失败”当作可进入语义阶段。

独立临时数据库反例：

```text
embedding=None
embedding_model=None
dedup_await_count=1
cluster_await_count=1
asset_await_count=1
final_status=completed
semantic_phase=completed
embedding_status=embeddings_generated
```

影响：

- fix-1 只覆盖了 adapter 明确 `supports_embedding=False` 的情况，没有覆盖真实 provider 运行失败。
- 系统仍可能在没有本次真实向量的情况下读取历史向量、执行去重/聚类并生成下游资产。
- 最终状态继续对用户报告“全部完成”，属于 false safety/live status。

验收要求：

- `success_count == 0` 时不得返回 `embeddings_generated`。
- 返回结构化结果，至少包含 requested、stored、failed、skipped_existing 和 status。
- 只有 `stored_count > 0`，且本次待处理信号均满足明确的真实向量可用条件时，runner 才能进入语义阶段。
- 新增“真实 adapter 全部失败”和“部分失败”两类 runner 集成测试。

### P0-2：机器门禁仍是假阳性，严格断言无法通过

位置：

- `scripts/p13_1_baseline_metrics.py`
- `docs/P13-1-evidence/metrics.json`

当前 JSON 同时写出：

```text
confidence_contract.passed=true
confidence_contract.observations.test_count=0
confidence_contract.observations.low_score_persists=false
regression.passed=true
regression.observations.test_count=0
```

具体问题：

1. `_count_tests()` 只解析 `N passed`，但脚本自身又追加 `-q`，项目配置形成更安静的输出；解析失败返回 0，却不让 gate 失败。
2. `low_score_persists` 明确为 false，但顶层只看 pytest 退出码，仍将 gate 标为 true。
3. dedup/cluster/asset 的 `await_count=0` 不是脚本捕获的运行值，而是只要 breaker pytest 返回 0 就直接填 0。
4. `frontend_semantics` 仍通过读取 `app.js` 并搜索字符串判断，不是浏览器或 DOM 行为门禁。
5. `no_new_destructive_dismiss` 对应测试把数据库结果固定为空，没有真实重复信号和 dismissed 前后计数。
6. `compute_deltas()` 只读取正式数据库当前总数；字段名虽叫 `deltas`，却没有 before、after 或 delta。
7. `singleton_themes` 直接等于主题总数，不是按主题 signal_count 计算。
8. 任务书规定的 `new_pseudo_embeddings`、`new_dismissed`、`new_themes` 完全不存在。

原 fix-1 指令中的严格机器断言实际失败，而交付报告却写“exit 0”。这属于“验证脚本假阳性”和“报告高于证据”再次复发。

验收要求：

- 任一关键 observation 为 false、0/UNKNOWN（当预期非 0 或必须被观测）时，相应 gate 必须 false。
- 真实行为 probe 将观测结果直接写入 JSON，不得根据 pytest 退出码推断 await count。
- 临时数据库实际执行 no-real/all-failed 流程并生成 before/after/delta。
- 前端机器 gate 不得退化为源码 token 搜索。
- 提供一条独立 mutation test，证明错误返回 `embeddings_generated` 时脚本非 0。

### P0-3：`completed_with_skips` 没有成为完整终态

位置：

- `signal_miner/routes/pipeline.py:132-140`
- `frontend/static/app.js:1384-1404`
- `frontend/app.py:739-752`

问题：

- SSE route 只在 `completed` 或 `failed` 时结束，不识别 `completed_with_skips`。
- SPA 只处理 `data.status === 'completed'` 和 `failed`，收到 `completed_with_skips` 后不会恢复按钮、关闭 EventSource 或显示终态 toast。
- Streamlit 仍通过 Signal/Theme 数量猜测进度，可能显示“信号已提取，正在聚类”，没有读取真实 run status。

独立 SSE 探针：

```text
input_status=completed_with_skips
first_event_received=true
stream_still_open_after_completed_with_skips=true
```

影响：

后端 runner 虽产生新状态，实际客户端并未消费这个契约。用户看到的是一直运行或错误“正在聚类”，本阶段要求的诚实 skip 展示仍不可达。

验收要求：route、SPA、Streamlit 和测试统一终态集合；`completed_with_skips` 必须关闭流、恢复控件并显示“文本提取完成，语义阶段未执行”。

## P1 阻断问题

### P1-1：Embedding 异常路径的最终统计和文案错误

当 embedding 函数抛异常时，runner 的调用熔断有效，但第 259–266 行仍只按字符串是否含 `skipped` / `blocked` 判断最终语义状态。

独立输出：

```text
status=completed_with_skips
embedding_status=embedding_failed
semantic_phase=completed
message=Pipeline complete: 1 signals, 0 themes, ...
```

同一事件内部互相矛盾。最终状态和文案必须直接使用 `semantic_allowed` 或结构化 embedding result，不得再次用字符串包含关系推导。

### P1-2：legacy confidence API 契约未真正废弃

位置：

- `signal_miner/routes/pipeline.py:35-43`
- `signal_miner/routes/signals.py:18-51`
- `frontend/static/app.js:1260-1321`
- `frontend/app.py:258-270`
- `frontend/app.py:706-716`

独立 OpenAPI 结果：

```text
RunPipelineRequest.confidence_threshold: default=0.5，无 deprecated/ignored 描述
SignalSummary.confidence: 无 legacy/deprecated 描述
GET /signals min_confidence: 无 deprecated 标记
```

静态 SPA 仍读取隐藏 `pipe-confidence=0.5` 并发送 `confidence_threshold`；Streamlit 两个入口也仍发送。可见控件虽然删除，但契约和请求并未删除或正式废弃。

### P1-3：部分前端仍未完整表达“未校准”

- SPA Evidence Chain：`frontend/static/app.js:1199` 只显示“模型自评 0.xx”，缺少“未校准”。
- Streamlit Evidence Chain：`frontend/app.py:656-660` 仍显示裸百分比。

信号主卡片已修正，但“所有活跃展示区域”尚未收口。

### P1-4：浏览器脚本仍不能作为门禁

`scripts/p13_1_browser_verify.js`：

- Playwright 不存在时仍退化为 `app.js` 源码检查。
- 三个布尔值即使全为 false，也不会非 0 退出。
- Playwright 分支只打印布尔值，不执行失败断言。
- `main().catch(console.error)` 不设置失败退出码。
- 没有真正运行一次 no-real-embedding pipeline 并验证终态。

执行方把该子项标为 BLOCKED 是诚实的，但脚本本身仍违反 fix-1 指令，必须修复后才能复验。

### P1-5：报告与当前工作区漂移

- 报告写 Ruff exit 0；独立实际 exit 1，错误全部位于 `scripts/p13_1_baseline_metrics.py`。
- 报告写全量 193 passed；独立实际为 196 passed、3 warnings；机器 JSON 又写 0。
- 报告写严格机器断言通过；独立断言因 observation false / delta 缺失失败。
- 报告写“所有 gate 无字符串搜索”，但 frontend gate 明确读取源码 token。

## 已确认通过的修复

以下修复有效，可保留：

1. 0.01 分合法信号在 legacy threshold 0.99 下能够真实入库。
2. 持久化字段为 `model_self_score=0.01`、`calibrated_confidence=None`、`confidence_method=llm_self_reported`。
3. Product profile 的 `viral_hook` 真实提取路径会被拒绝。
4. `supports_embedding=False` 的 DeepSeek 直接路径会短路 dedup/cluster/asset。
5. development + `ALLOW_TEST_PSEUDO_EMBEDDING=true` 仍被阻断。
6. prompt version 实现已按 profile.name 区分 product=v1、video=v1-video。
7. SPA 信号页默认筛选为 0，主卡片显示“模型自评（未校准）”。
8. Pipeline 页不再显示可见“最低置信度”控件。
9. 聚焦 43 项、全量 196 项测试通过。
10. 临时数据库迁移往返后 RawFeedback 1257、Signal 1425、Theme 17、dismissed 1408，计数守恒。

## 浏览器独立证据

执行方没有提供 fix-1 PNG。指挥官已使用新启动的 `127.0.0.1:8013` 和临时数据库副本补做静态页面 DOM 验证：

- `docs/P13-1-screenshots/acceptance-fix1-signals-commander-20260710.png`
- `docs/P13-1-screenshots/acceptance-fix1-pipeline-commander-20260710.png`
- `docs/P13-1-screenshots/acceptance-fix1-browser-evidence-commander-20260710.json`

页面基础文案部分通过，但动态 skip 流程因终态契约缺陷失败。验收后浏览器标签、本地服务和临时数据库均已清理。

## 复验要求

fix-2 交付后必须全部满足：

1. 真实 Embedding 全失败时 stored=0，dedup/cluster/asset 均为 0，终态为 completed_with_skips。
2. Embedding 异常、无能力、全失败三种路径使用同一结构化状态，不出现 `semantic_phase=completed`。
3. SSE 和两套前端都把 completed_with_skips 当作终态。
4. 严格 JSON 断言原样 exit 0；内部不得再出现 passed=true 与 false observation 并存。
5. before/after/delta 来自隔离临时数据库真实运行。
6. Ruff、Node、聚焦测试、全量测试全部真实 exit 0，报告数字与命令一致。
7. 浏览器脚本实际 DOM 断言失败时非 0，不能源码 fallback。

## 问题统计归类

- 验证脚本假阳性：再次复发，原门禁判定无效。
- 交付报告与机器结果漂移：再次复发，原门禁判定无效。
- 负例覆盖遗漏：从“adapter 无能力”修到一半，遗漏“adapter 有能力但全调用失败”。
- UI 状态契约未端到端贯通：新增高风险类别。

## 验收决策

- P13-1 fix-1：**FAIL**
- P13-1 fix-2：**立即返工**
- P13-2：**继续冻结**
