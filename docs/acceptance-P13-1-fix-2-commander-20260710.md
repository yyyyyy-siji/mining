# P13-1 fix-2 验收报告：置信度可信基线与伪向量熔断

验收日期：2026-07-10

结论：不通过，需要小范围返修。P13-2 继续冻结。

## 验收范围

本次复验针对执行方交付报告：

- `docs/acceptance-P13-1-delivery-fix-2-20260710.md`
- `docs/P13-1-evidence/metrics.json`
- `docs/P13-1-evidence/behavior_probe.json`

重点复查 fix-1 遗留的三个 P0：

1. 真实 embedding 全部失败是否仍穿透 dedup / cluster / asset。
2. `metrics.json` 是否仍存在顶层 passed 与内部 observation 矛盾。
3. `completed_with_skips` 是否作为终态贯通后端、SSE、SPA、Streamlit。

## 已通过项

### 1. 真实 embedding 全失败熔断已修复

独立运行：

```bash
.venv/bin/python scripts/p13_1_behavior_probe.py
```

结果：

```text
Overall: PASS
all_real_embeddings_failed:
  stored_real_count=0
  dedup_await_count=0
  cluster_await_count=0
  asset_await_count=0
  semantic_phase=skipped
```

代码确认：

- `signal_miner/pipeline/embedding.py` 返回结构化 `EmbeddingResult`。
- `signal_miner/pipeline/runner.py` 读取 `emb_result.semantic_ready`，不再依赖字符串匹配。

### 2. 机器证据主链路已明显改善

独立运行：

```bash
.venv/bin/python scripts/p13_1_baseline_metrics.py
```

结果：

```text
Overall: PASS
```

追加严格 JSON 断言通过：

```text
strict metrics assertions passed
```

关键字段确认：

- `checks.confidence_contract.observations.persisted_count == 1`
- `model_self_score == 0.01`
- `calibrated_confidence == null`
- `all_real_embeddings_failed.dedup_await_count == 0`
- `all_real_embeddings_failed.cluster_await_count == 0`
- `all_real_embeddings_failed.asset_await_count == 0`
- `deltas.new_pseudo_embeddings == 0`
- `deltas.new_dismissed == 0`
- `deltas.new_themes == 0`

### 3. `completed_with_skips` 后端/SSE/SPA 主路径基本通过

代码确认：

- `signal_miner/routes/pipeline.py` SSE 终态包含 `completed_with_skips`。
- `frontend/static/app.js` 收到 `completed_with_skips` 后关闭 EventSource、恢复按钮、显示 warning。
- `frontend/app.py` 增加 `/pipeline/runs/{run_id}` 状态读取。

行为证据：

```text
frontend_semantics:
  terminal_status=completed_with_skips
  stream_closed=true
  subscriber_removed=true
```

### 4. 回归命令通过

独立运行：

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
.venv/bin/pytest -o addopts= -q tests/test_embedding_safety.py tests/test_confidence_contract.py tests/test_evidence_validation.py
.venv/bin/pytest -o addopts= -q
```

结果：

```text
ruff: All checks passed
node --check: 0
focused tests: 24 passed
full tests: 196 passed, 3 warnings
```

### 5. 实际 SPA DOM 验证通过

我启动本地服务：

```bash
APP_ENVIRONMENT=development API_PORT=8014 .venv/bin/python -m uvicorn signal_miner.main:app --host 127.0.0.1 --port 8014
```

浏览器实测：

```json
{
  "signals": {
    "hasBareMinConfidence": false,
    "hasModelSelfScoreFilter": true,
    "hasUncalibrated": true,
    "pipeConfidenceExists": false,
    "signalCardCount": 200,
    "sampleBadges": [
      "模型自评 0.95（未校准）"
    ]
  },
  "pipeline": {
    "hasPipeConfidence": false,
    "visibleConfidenceText": false,
    "hasPrimaryModel": true,
    "hasMultimodal": true,
    "hasAigcProfile": true
  }
}
```

截图证据：

- `docs/P13-1-screenshots/acceptance-fix2-pipeline-commander-20260710.png`

## 阻断问题

### P1-1：Streamlit 仍发送 legacy `confidence_threshold`

位置：

- `frontend/app.py:267-270`
- `frontend/app.py:713-716`

问题：

交付报告声明“Streamlit Pipeline 不再发送 `confidence_threshold`”，但代码仍在两个运行管线入口把该字段放入请求 payload。

证据：

```text
frontend/app.py:267 payload = {
frontend/app.py:269     "confidence_threshold": conf_threshold,

frontend/app.py:713 payload = {
frontend/app.py:715     "confidence_threshold": conf_threshold,
```

影响：

后端目前已忽略该字段，因此不是数据损坏级 P0；但这是 P13-1 置信度可信基线的契约收口问题。继续发送 legacy 字段会让前端、报告、OpenAPI 迁移状态不一致，并给后续 P13-2 校准入口制造歧义。

验收要求：

- Streamlit 所有 `/pipeline/run` 请求 payload 不再包含 `confidence_threshold`。
- 保留后端兼容接收和 deprecated OpenAPI 标记。
- 新增或更新测试/静态断言，确认 `frontend/app.py` 不再发送该字段。

### P1-2：浏览器验证脚本仍保留源码 fallback 且失败不返回非零

位置：

- `scripts/p13_1_browser_verify.js:13-18`
- `scripts/p13_1_browser_verify.js:78-97`
- `scripts/p13_1_browser_verify.js:97`

问题：

fix-2 指令要求浏览器证据不得退化为源码 token 检查；无浏览器能力时应明确 BLOCKED 或非零退出。当前脚本在 Playwright 不可用时仍抓取 `/app.js` 并检查字符串存在：

```text
Playwright not available, using alternative verification
return doSimpleVerify()
```

`doSimpleVerify()` 只检查源码中是否包含 `未校准`、`模型自评`、skip 文案，不检查真实 DOM、可见状态、EventSource 终态或截图。并且 `main().catch(console.error)` 不会把断言失败转换为非零退出。

影响：

本次我用内置浏览器补做了真实 DOM 验证，实际 SPA 是通过的；但执行方交付体系仍保留 false-positive 通道。该问题属于高频缺陷“浏览器证据退化为源码检查”的再次复发。

验收要求：

- 删除源码 fallback。
- Playwright 不可用时输出明确 BLOCKED JSON，并以非零退出，或由交付报告明确标记浏览器证据未通过。
- DOM 断言 false 时必须 `process.exit(1)`。
- 验证内容至少包括：信号页未校准文案、无 `#pipe-confidence`、Pipeline 页模型/多模态状态、AIGC profile。

### P1-3：交付报告仍有局部漂移

位置：

- `docs/acceptance-P13-1-delivery-fix-2-20260710.md`

问题：

报告声明：

```text
Streamlit Pipeline不再发送 confidence_threshold
```

实际代码仍发送。报告还将浏览器状态写为 BLOCKED，但仓库中的浏览器验证脚本仍可能以源码 fallback 给出非真实通过信号。

影响：

这说明“报告一致性门禁”仍未完全生效。虽然本次 metrics 主链路比 fix-1 明显改善，但报告不能继续包含未经代码验证的断言。

验收要求：

- 报告中每条“已修复”必须能被命令或代码行证据支持。
- 若浏览器不可用，应区分“执行方浏览器 BLOCKED”和“Commander 补充浏览器通过”，不能用源码 fallback 代替浏览器。

## 非阻断观察项

### OpenAPI deprecated 契约通过

独立检查 `/openapi.json`：

```json
{
  "RunPipelineRequest.confidence_threshold": {
    "deprecated": true,
    "description": "DEPRECATED P13-1: 未校准，已忽略，不参与入库或自动决策"
  },
  "SignalSummary.confidence": {
    "deprecated": true,
    "description": "DEPRECATED: legacy uncalibrated alias. Use model_self_score."
  },
  "GET /signals min_confidence": {
    "deprecated": true,
    "description": "DEPRECATED: use min_model_self_score instead (uncalibrated, view-only)."
  }
}
```

### 当前 fix-3 应保持窄范围

本次不要求重写 embedding、runner 或 metrics 主链路。核心 P0 已修复，下一轮只处理残留契约、浏览器脚本和报告一致性。

## 问题统计归类

| 类别 | 本次是否复发 | 说明 |
| --- | --- | --- |
| 验证脚本假阳性 | 部分复发 | metrics 主链路改善，但 browser verifier 仍可源码 fallback |
| 交付报告与代码漂移 | 复发 | Streamlit 不发送字段的声明不成立 |
| 浏览器源码 fallback | 复发 | `scripts/p13_1_browser_verify.js` 仍保留 fallback |
| 状态与控制流不一致 | 未复发 | `completed_with_skips` 主路径已修复 |
| 真实负例缺失 | 未复发 | all-real-embedding-failed 已覆盖 |

## 复验要求

fix-3 只允许修改：

- `frontend/app.py`
- `scripts/p13_1_browser_verify.js`
- 必要测试或证据脚本
- 交付报告

不得改动：

- `signal_miner/pipeline/embedding.py`
- `signal_miner/pipeline/runner.py`
- `signal_miner/routes/pipeline.py`
- 数据库迁移
- P13-2 校准实现

复验通过条件：

1. Streamlit 不再发送 `confidence_threshold`。
2. 浏览器脚本不存在源码 fallback，false/BLOCKED 均不能伪装为 PASS。
3. 交付报告与代码、JSON、命令输出一致。
4. 现有 P13-1 P0 回归继续通过。
