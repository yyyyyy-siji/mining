# DeepSeek 执行指令：P13-1 fix-2 全失败熔断与证据可信收口

## 任务目标

只修复 P13-1 fix-1 独立复验中仍未通过的项目：

1. 真实 Embedding 全部失败时仍穿透熔断。
2. `completed_with_skips` 未贯通 runner、SSE、SPA 和 Streamlit。
3. legacy confidence 参数仍被隐藏发送，OpenAPI 未正式标记 deprecated。
4. 机器 JSON 再次假阳性，报告与真实命令漂移。
5. 浏览器脚本仍可退化为源码检查并错误 exit 0。

失败报告：

- `docs/acceptance-P13-1-fix-1-commander-20260710.md`

这是 P13-1 fix-2，不是 P13-2。不得实现概率校准、真实 Embedding 选型、算法重写或历史数据清洗。

## 已通过能力保护

以下行为已经独立确认通过，不得回退：

- 0.01 分合法信号在 legacy threshold 0.99 下仍入库。
- `calibrated_confidence=None`。
- Product profile 拒绝 `viral_hook`。
- `supports_embedding=False` 时 dedup/cluster/asset 为 0。
- development 环境不能开启 test-only pseudo embedding。
- product / video prompt version 分别为 v1 / v1-video。
- 信号主卡片显示“模型自评（未校准）”，默认查看筛选为 0。
- 迁移计数守恒。

任何一项回退，本轮直接 FAIL。

## 允许修改范围

只允许修改：

- `signal_miner/pipeline/embedding.py`
- `signal_miner/pipeline/runner.py`
- `signal_miner/routes/pipeline.py`
- `signal_miner/routes/signals.py`
- `signal_miner/models/feedback.py`
- `signal_miner/settings.py`（仅 legacy 字段说明或移除未使用配置）
- `frontend/static/app.js`
- `frontend/app.py`
- `tests/test_embedding_safety.py`
- `tests/test_pipeline.py`
- `tests/test_pipeline_integration.py`
- `tests/test_confidence_contract.py`
- 可新增一个 P13-1 pipeline route / SSE 契约测试文件
- 可新增一个 P13-1 前端状态 fixture / 验收辅助文件
- `scripts/p13_1_baseline_metrics.py`
- `scripts/p13_1_browser_verify.js`
- 可新增 `scripts/p13_1_behavior_probe.py`
- `docs/P13-1-evidence/metrics.json`
- `docs/P13-1-screenshots/` 下 fix-2 证据
- `docs/acceptance-P13-1-delivery-20260710.md`

## 禁止修改范围

- 不得修改 P13-2 及后续任务书。
- 不得修改数据来源连接器、来源跳转、采集适配器。
- 不得修改迁移或正式数据库内容。
- 不得引入新的 Embedding provider、向量库或临时相似度算法。
- 不得重新设计 dedup / cluster 算法。
- 不得修改 PRD、痛点、机会和需求生成逻辑。
- 不得删除、恢复或重新 dismiss 历史信号。
- 不得通过删除测试、降低断言、改成 skip 或手写 JSON 获得 PASS。

## 开发方法与阶段

### 阶段 A：用结构化结果表达真实 Embedding 可用性

#### 先写失败测试

在临时数据库中创建真实 Signal，使用：

```python
supports_embedding = True

async def embed(...):
    raise RuntimeError("forced embedding failure")
```

通过真实 `run_mining_pipeline()` 控制流断言：

```text
stored_real_embeddings=0
dedup_await_count=0
cluster_await_count=0
asset_await_count=0
final_status=completed_with_skips
semantic_phase=skipped
```

测试不得只 patch `generate_embeddings_for_signals()` 返回预设字符串；必须让真实 embedding 函数执行并全部失败。

再增加部分失败测试：两个信号中一个成功、一个失败。P13-1 采取保守策略：本次语义阶段整体熔断，不得对不完整集合做自动决策。

#### 实现要求

1. `generate_embeddings_for_signals()` 不再只返回模糊字符串；返回结构化结果。可用 dataclass / Pydantic model，至少包含：

```text
status
requested_count
found_count
preexisting_real_count
stored_real_count
failed_count
pseudo_count
semantic_ready
reason
```

2. 建议状态：

- `ready_real_embeddings`
- `skipped_no_real_embedding_capability`
- `blocked_no_signals_found`
- `blocked_incomplete_real_embeddings`
- `blocked_embedding_exception`
- `test_only_pseudo_embedding`

命名可调整，但语义必须一一对应。

3. `semantic_ready` 只能在以下条件全部成立时为 true：

- 找到至少一个请求信号；
- 本次需要参与语义阶段的每条信号都有非 pseudo 的真实向量；
- 没有未处理的 embedding 失败；
- test-only pseudo 数量为 0。

4. `success_count == 0`、部分失败、异常、找不到信号、只有 pseudo 向量时，`semantic_ready=false`。
5. runner 只能读取 `semantic_ready`，不得再用字符串包含 `skipped` / `blocked` 或状态白名单二次推导。
6. `semantic_ready=false` 时不得发布 dedup/clustering running 事件，不得调用 dedup、cluster、asset。
7. final stats 必须包含结构化 embedding 计数和真实 reason。

#### 阶段 A 验收

- 无能力、全部失败、部分失败、函数异常、只有 pseudo 五条负例全部熔断。
- 全部真实向量成功时才允许 dedup/cluster。
- 每条负例同时断言数据库向量状态、调用次数、事件序列和最终 run row。

### 阶段 B：贯通 `completed_with_skips` 终态

#### 后端契约

1. runner 的所有熔断路径统一输出：

```text
status=completed_with_skips
semantic_phase=skipped
embedding_status=<真实结构化状态>
message=文本提取已完成；语义去重/聚类未执行：<原因>
```

2. `signal_miner/routes/pipeline.py` 的 SSE 在以下终态关闭：

- `completed`
- `completed_with_skips`
- `failed`
- 其他项目已存在的终态（如有）

3. 如 Streamlit 当前无法读取 run 状态，在同一文件新增只读 `GET /pipeline/runs/{run_id}`，返回 `PipelineRunRow.status/stats/error/completed_at`；不新增数据库表或迁移。

#### SPA

收到 `completed_with_skips` 时必须：

- 关闭 EventSource；
- 恢复“启动管线”按钮；
- 隐藏“停止”按钮；
- 进度显示 100%；
- 使用 warning 而非 success toast；
- 清楚展示文本提取完成、语义阶段未执行和原因。

#### Streamlit

- 禁止继续用 Signal/Theme 数量猜测“正在聚类”。
- 通过真实 run status endpoint 或等价真实状态读取完成结果。
- `completed_with_skips` 显示 warning，不显示“正在聚类”或“全部成功”。

#### 阶段 B 验收

新增测试必须证明：

```text
SSE receives completed_with_skips
SSE iterator terminates
subscriber is removed
SPA terminal handler includes completed_with_skips
Streamlit reads real run status
```

### 阶段 C：完成 legacy confidence 契约收口

1. 静态 SPA 删除隐藏 `pipe-confidence` input，不再读取或发送 `confidence_threshold`。
2. Streamlit 两个 Pipeline 入口不再发送 `confidence_threshold`。
3. `/pipeline/run` 为旧客户端保留该字段时：
   - 默认应为 null 或明确 ignored；
   - OpenAPI 必须有 `deprecated: true`；
   - description 明确“未校准，已忽略，不参与入库或自动决策”；
   - route 不再向 runner 转发。
4. `GET /signals` 的 `min_confidence` 使用 FastAPI/Pydantic 正式 deprecated 标记，不得只写注释。
5. `SignalSummary.confidence` 和共享 Signal model 的 legacy 字段在 JSON Schema 中标记 deprecated，并说明等价于未校准模型自评的兼容值。
6. `settings.extraction_confidence_threshold` 如已无消费者，删除；如为兼容保留，明确 deprecated/ignored，并增加无消费者断言。
7. 所有前端 Evidence Chain：
   - 显示“模型自评 0.xx（未校准）”；
   - 不显示裸百分比或无“未校准”的模型自评。

#### 阶段 C 验收

OpenAPI 机器断言至少验证：

```python
assert run_confidence_threshold["deprecated"] is True
assert min_confidence_parameter["deprecated"] is True
assert signal_confidence_schema["deprecated"] is True
```

并断言 SPA/Streamlit Pipeline 请求 payload 中不再包含 `confidence_threshold`。

### 阶段 D：机器证据必须来自直接观测

#### 行为 probe

建议新增 `scripts/p13_1_behavior_probe.py`，在临时数据库运行真实行为并输出 JSON。至少包含：

```json
{
  "low_score": {
    "persisted_count": 1,
    "model_self_score": 0.01,
    "calibrated_confidence": null,
    "passed": true
  },
  "no_capability": {
    "dedup_await_count": 0,
    "cluster_await_count": 0,
    "asset_await_count": 0,
    "passed": true
  },
  "all_real_embeddings_failed": {
    "stored_real_count": 0,
    "failed_count": 1,
    "dedup_await_count": 0,
    "cluster_await_count": 0,
    "asset_await_count": 0,
    "final_status": "completed_with_skips",
    "semantic_phase": "skipped",
    "passed": true
  },
  "sse_terminal": {
    "status": "completed_with_skips",
    "stream_closed": true,
    "subscriber_removed": true,
    "passed": true
  },
  "deltas": {
    "before": {},
    "after": {},
    "new_pseudo_embeddings": 0,
    "new_dismissed": 0,
    "new_themes": 0
  },
  "passed": true
}
```

任何 observation 不符合预期时，probe 必须非 0；不得把 pytest exit code转换成虚构的 await count。

#### `p13_1_baseline_metrics.py`

1. 读取行为 probe 的真实 JSON，并原样纳入 gate。
2. `low_score_persists=false` 时 confidence gate 必须 false。
3. test count 解析失败时 regression gate 必须 false，不能用 0 继续 PASS。
4. 运行 pytest 时使用能够稳定产生摘要的命令，例如：

```bash
.venv/bin/python -m pytest -o addopts='' -q
```

5. `deltas` 必须是隔离运行的 before、after 和数学差值，不得存放正式库当前总数冒充 delta。
6. `singleton_themes` 必须按真实 theme signal_count 计算，不能直接等于主题总数。
7. frontend gate 必须来自浏览器 DOM 结果 JSON，禁止读取 `app.js` token 作为 PASS 依据。
8. required gate 缺失、observation 矛盾、browser BLOCKED、Ruff 失败或命令未运行时，顶层 false 且进程非 0。

#### 反假阳性测试

必须新增自动测试，故意构造：

- gate `passed=true` 但 `low_score_persists=false`；
- all-failed await_count=1；
- 缺少 `new_dismissed`；
- regression test_count=0；
- frontend DOM result=false。

五种情况都必须使 metrics 聚合失败。

### 阶段 E：真实浏览器证据

1. `scripts/p13_1_browser_verify.js` 不得再有源码 fallback。
2. Playwright/浏览器不可用时：
   - 输出 `status=BLOCKED`；
   - 进程非 0；
   - 不生成 PASS JSON。
3. 所有 DOM 布尔断言都必须参与最终 passed；任一 false 时 exit 1。
4. `main().catch(...)` 必须设置非 0 退出码。
5. 使用临时数据库和 fake/no-embedding adapter 完成一次可重复的动态管线流程，不调用外部 LLM、不修改正式库。
6. 保存至少：
   - fix-2 信号页截图；
   - Pipeline `completed_with_skips` 终态截图；
   - AI 模型状态和多模态入口截图；
   - 来源按钮 / Evidence Chain / AIGC profile 证据。
7. DOM 结果 JSON 至少包含 URL、port、run_id、终态、可见文案、截图路径和 cleanup 状态。

如果执行环境确实没有浏览器，应如实交付 BLOCKED；不得以源码检查替代。Commander 可独立补验，但执行方机器 JSON 不得把 frontend gate 写 true。

## 验收标准与命令

### Ruff / 语法

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
node --check scripts/p13_1_browser_verify.js
git diff --check
```

四条必须分别记录真实退出码。当前 Ruff 已知失败，修复前不得交付。

### 聚焦测试

```bash
.venv/bin/python -m pytest -o addopts='' \
  tests/test_confidence_contract.py \
  tests/test_embedding_safety.py \
  tests/test_pipeline.py \
  tests/test_pipeline_integration.py \
  <新增route/SSE测试文件> -q
```

### 全量回归

```bash
.venv/bin/python -m pytest -o addopts='' -q
```

报告必须从本次命令复制测试数和 warning 数，不得沿用 193、196 或其他旧数字。

### 行为证据

```bash
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_1_baseline_metrics.py
```

### 严格 JSON 门禁

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("docs/P13-1-evidence/metrics.json").read_text(encoding="utf-8"))
required = {
    "confidence_contract",
    "signal_type_validation",
    "evidence_validation",
    "pseudo_embedding_blocked",
    "no_new_destructive_dismiss",
    "frontend_semantics",
    "regression",
}
assert set(data["checks"]) == required
assert data["passed"] is True
assert all(data["checks"][name]["passed"] is True for name in required)

conf = data["checks"]["confidence_contract"]["observations"]
assert conf["low_score_persists"] is True
assert conf["persisted_count"] == 1

emb = data["checks"]["pseudo_embedding_blocked"]["observations"]
for case in ("no_capability", "all_real_embeddings_failed", "embedding_exception"):
    assert emb[case]["dedup_await_count"] == 0
    assert emb[case]["cluster_await_count"] == 0
    assert emb[case]["asset_await_count"] == 0
    assert emb[case]["semantic_phase"] == "skipped"

assert data["checks"]["regression"]["observations"]["test_count"] > 0
assert data["checks"]["frontend_semantics"]["observations"]["evidence_type"] == "browser_dom"
assert data["checks"]["frontend_semantics"]["observations"]["terminal_status"] == "completed_with_skips"

d = data["deltas"]
assert "before" in d and "after" in d
assert d["new_pseudo_embeddings"] == 0
assert d["new_dismissed"] == 0
assert d["new_themes"] == 0
print("P13-1 fix-2 strict gates passed")
PY
```

### OpenAPI 契约

新增自动测试并在报告中保存摘要，至少断言：

- legacy `confidence` deprecated；
- `confidence_threshold` deprecated/ignored；
- `min_confidence` deprecated；
- 新前端请求不再发送 threshold。

### 迁移守恒

在临时数据库副本运行：

```bash
alembic downgrade -1
alembic upgrade head
```

报告前后：RawFeedback、Signal、Theme、dismissed；不得在正式库回滚。

## 交付物

必须更新：

1. `docs/acceptance-P13-1-delivery-20260710.md`
2. `docs/P13-1-evidence/metrics.json`
3. `docs/P13-1-screenshots/` 下 fix-2 浏览器结果或明确 BLOCKED 结果

交付报告必须逐项列出：

- 真实 Embedding 全失败/部分失败的计数和调用次数；
- no-capability、异常、pseudo 五类熔断状态；
- SSE 是否关闭、订阅者是否移除；
- OpenAPI deprecated 字段；
- before/after/delta；
- Ruff、Node、聚焦、全量命令的真实退出码；
- 本次实际测试数和 warning 数；
- 浏览器 URL、run_id、DOM 文案和截图；
- 未覆盖风险。

## 完成回复格式

```text
P13-1 fix-2 completed.

Behavioral evidence:
- no capability await counts: 0/0/0
- all real embeddings failed await counts: 0/0/0
- partial failure await counts: 0/0/0
- embedding exception await counts: 0/0/0
- SSE completed_with_skips closed: true
- deltas pseudo/dismissed/themes: 0/0/0
- regression: <actual count>, <warnings>, exit 0
- browser: PASS with paths, or BLOCKED with non-zero exit

Artifacts:
- docs/acceptance-P13-1-delivery-20260710.md
- docs/P13-1-evidence/metrics.json
- docs/P13-1-screenshots/<fix-2 artifacts>

Remaining blockers:
- None, or exact blockers.
```

不要生成 P13-2 指令。等待 Commander 独立复验。
