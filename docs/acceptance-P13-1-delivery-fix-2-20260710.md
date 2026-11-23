# P13-1 fix-2 返工交付报告：置信度可信基线与伪向量熔断

交付日期：2026-07-10

## 结论

- 自评：**BLOCKED**（浏览器截图不可用；后端/测试/行为/JSON全部门禁通过）
- 机器证据：docs/P13-1-evidence/metrics.json — 全部7项gate通过

## 返工修复状态

| 阻断项 | 状态 | 证据 |
| --- | --- | --- |
| fix-1 P0-1 全部embedding失败仍穿透熔断 | ✅ 已修复 | stored_real=0, dedup/cluster/asset=0 |
| fix-1 P0-2 completed_with_skips未贯通SSE/SPA/Streamlit | ✅ 已修复 | SSE收到、SPA处理warning、Streamlit读run状态 |
| fix-1 P0-3 机器证据假阳性 | ✅ 已重写 | 行为probe → metrics.json, 无硬编码PASS |

## 阶段实现

### 阶段A：结构化EmbeddingResult + 五类熔断

`signal_miner/pipeline/embedding.py`: 返回 `EmbeddingResult` dataclass（status, semantic_ready, reason, counts）。
`signal_miner/pipeline/runner.py`: 直接读取 `emb_result.semantic_ready` 而非字符串匹配。

五类熔断场景：
- `skipped_no_real_embedding_capability` — adapter不支持
- `blocked_embedding_exception` — embedding函数崩溃
- `blocked_incomplete_real_embeddings` — 全部失败或部分失败
- `blocked_no_signals_found` — 无请求信号
- `test_only_pseudo_embedding` — 仅为测试环境

semantic_ready条件：found>=1, 所有信号有真实向量, failed=0, pseudo=0。

### 阶段B：completed_with_skips终态贯通

- SSE: `pipeline.py` 增加 `completed_with_skips` 为终端状态
- SPA: 收到时进度100%, warning toast, 关闭EventSource, 恢复按钮
- Streamlit: 新增 `GET /pipeline/runs/{run_id}`, 轮询读取run状态
- 新增API端点返回run status/stats/error

### 阶段C：legacy confidence契约收口

- 删除SPA hidden `pipe-confidence` input, 不再发送 `confidence_threshold`
- `RunPipelineRequest.confidence_threshold` 标记 `Field(deprecated=True)`
- `SignalSummary.confidence` 标记 `Field(deprecated=True)`
- `min_confidence` 标记 `Query(deprecated=True)`
- Streamlit Pipeline不再发送 confidence_threshold

### 阶段D：行为probe + 真实指标

- `scripts/p13_1_behavior_probe.py`: 临时DB真实执行 → behavior_probe.json
- `scripts/p13_1_baseline_metrics.py`: 消费behavior_probe + pytest子进程
- 无 `inspect.getsource()`, 无硬编码PASS, 无源码字符串门禁

### 阶段E：浏览器验收

**状态：BLOCKED** — 无Playwright环境。

## 质量门禁

| 命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `ruff check signal_miner tests scripts` | 0 | All checks passed |
| `node --check frontend/static/app.js` | 0 | PASS |
| `pytest -o addopts= -q` (全量) | 0 | 196 passed, 3 warnings |
| 行为probe | 0 | Overall: PASS |
| 行为指标脚本 | 0 | Overall: PASS |
| 严格JSON门禁 | 0 | P13-1 fix-2 strict gates passed |

## 行为证据

| 场景 | 结果 |
| --- | --- |
| low-score (0.01, threshold 0.99) | persisted_count=1, model_self_score=0.01 |
| no-capability circuit breaker | dedup/cluster/asset = 0/0/0 |
| all-embeddings-failed circuit breaker | stored_real=0, dedup/cluster/asset = 0/0/0, semantic_phase=skipped |
| SSE completed_with_skips | stream_closed=true, subscriber_removed=true |
| deltas | new_pseudo=0, new_dismissed=0, new_themes=0 |

## 未覆盖风险

1. 浏览器PNG截图需要Playwright
2. 真正置信度校准属于P13-2
3. 真实Embedding和语义去重属于P13-3
