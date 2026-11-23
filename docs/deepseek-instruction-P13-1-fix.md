# DeepSeek 执行指令：P13-1 fix-1 置信度门禁与语义熔断返工

## 任务性质

这是 **P13-1 返工**，不是 P13-2。

失败验收报告：

- `docs/acceptance-P13-1-confidence-trust-baseline-commander-20260710.md`

本轮只修复该报告中的阻断项。不得开始概率校准、真实 Embedding 选型、去重/聚类算法重写、历史 dismissed 清洗或数据生命周期功能。

## 最高优先级目标

停止把未校准的 LLM 自评分数用于自动数据丢弃，并保证 DeepSeek 没有真实 Embedding 时语义阶段在控制流上真正熔断。

完成后必须同时满足：

1. 合法白名单信号无论 `model_self_score` 高低都可以入库；`calibrated_confidence` 仍为 null。
2. `skipped_no_real_embedding` / `blocked_no_real_embedding` 时，dedup、cluster 和下游主题资产生成调用次数均为 0。
3. 机器证据由运行时行为和真实命令退出码产生，不再检查注释、源码字符串或硬编码 PASS。
4. 静态 SPA、Streamlit、API 参数和浏览器页面都明确使用“模型自评（未校准）”语义。

## 执行原则

- 先写会失败的负例，再修改实现。
- 每完成一个阶段先运行该阶段聚焦测试；不要把所有问题混到最后一次调试。
- 所有数据库验证使用临时数据库或正式库副本，不得在唯一正式数据库上回滚或跑测试管线。
- 不得覆盖、回滚或格式化无关用户改动。
- 不得降低历史测试断言、删除测试、把失败改成 skip，或在报告中手写未经命令证明的 PASS。
- 如果浏览器、迁移或全量回归无法执行，交付结论必须为 BLOCKED，不得自评 PASS。

## 允许修改范围

只允许按本指令需要修改：

- `signal_miner/pipeline/extraction.py`
- `signal_miner/pipeline/prompts.py`（仅删除未校准分数门槛指令）
- `signal_miner/pipeline/runner.py`
- `signal_miner/pipeline/embedding.py`
- `signal_miner/routes/pipeline.py`
- `signal_miner/routes/signals.py`
- `signal_miner/models/feedback.py`
- `signal_miner/settings.py`（仅兼容 / deprecated 配置说明）
- `frontend/static/app.js`
- `frontend/app.py`
- `tests/test_confidence_contract.py`
- `tests/test_embedding_safety.py`
- `tests/test_pipeline.py`
- `tests/test_pipeline_integration.py`
- 如确有必要，新增一个 P13-1 路由契约测试文件
- `scripts/p13_1_baseline_metrics.py`
- `scripts/p13_1_browser_verify.js`
- `docs/P13-1-evidence/metrics.json`
- `docs/P13-1-screenshots/` 下本轮真实浏览器证据
- `docs/acceptance-P13-1-delivery-20260710.md`

如需修改列表外文件，先停止并在交付报告列出“文件、原因、无法在允许范围完成的证据”，不得自行扩展。

## 禁止修改范围

- 不得新增或修改 P13-2 及后续任务书。
- 不得修改数据来源连接器、采集适配器和来源跳转逻辑。
- 不得引入真实 Embedding 模型、向量数据库或临时相似度算法。
- 不得修改 PRD 生成器、痛点/机会/需求算法。
- 不得新增数据库迁移，除非指挥官另行批准。
- 不得批量改变历史 1,425 条 Signal、1,408 条 dismissed 或 17 个 Theme。
- 不得把历史 pseudo embedding 删除、回填为真实 embedding 或重新聚类。

## 分阶段开发任务

### 阶段 A：取消未校准自评分的自动入库门禁

#### 开发方法

先增加真实提取集成测试：使用临时数据库和 fake LLM，让 product profile 返回一个合法类型、`confidence=0.01` 的信号；即使调用方传入旧 `confidence_threshold=0.99`，该信号仍必须入库。

然后修改实现：

1. `extract_signals()` 不得再使用 `confidence` / `model_self_score` 过滤 LLM 输出。
2. `signal_miner/pipeline/prompts.py` 删除两套 prompt 中 `Only include signals with confidence >= ...` 的指令。
3. 旧 `confidence_threshold` 调用参数可以为兼容保留，但必须：
   - 不影响持久化；
   - 在代码和 API Schema 中标为 deprecated / ignored for trust decisions；
   - 不得继续以 0.5 作为隐形质量门槛。
4. `max_signals`、SignalType 白名单、Evidence 验证和质量门逻辑保持有效。
5. 旧 `confidence` 继续作为 legacy alias 返回；`model_self_score` 保存原始自评，`calibrated_confidence=None`。

#### 前端与查询契约

1. Pipeline 页面删除“最低置信度”输入，不再向 `/pipeline/run` 发送该字段；若为兼容保留控件，必须禁用且明确说明“不参与自动决策”，但优先删除。
2. 信号列表如保留人工查看筛选：
   - 参数改为 `min_model_self_score`；
   - 默认值为 0，不默认隐藏低分信号；
   - 文案为“最低模型自评分（未校准，仅查看筛选）”；
   - 旧 `min_confidence` 仅作为 deprecated API alias，不在前端发送。
3. SPA、Streamlit、Evidence 展示区域不得再出现无修饰“置信度 XX%”或“最低置信度”。
4. API Schema 中 legacy `confidence` 和兼容参数必须带 deprecated / legacy semantics 描述。

#### 阶段 A 验收标准

- `confidence=0.01`、旧阈值 0.99 的合法信号实际入库。
- 持久化字段为：`model_self_score=0.01`、`calibrated_confidence is None`、`confidence_method=llm_self_reported`。
- 非法 `viral_hook` 仍不会进入 product profile。
- 两套 active prompt 不再要求模型按自评分阈值删信号。
- 页面默认查询不携带 `min_confidence=0.5`。

### 阶段 B：在 runner 控制流上真正熔断语义阶段

#### 开发方法

先在 `tests/test_embedding_safety.py` 或 `tests/test_pipeline_integration.py` 增加 AsyncMock 负例：

- `generate_embeddings_for_signals()` 返回 `skipped_no_real_embedding`；
- `deduplicate_signals`、`cluster_signals_into_themes`、`generate_assets_from_themes` 都替换为 AsyncMock；
- 运行真实 `run_mining_pipeline()` 控制流；
- 断言三个 mock 的 `await_count == 0`。

然后修改 runner：

1. 定义明确的可继续状态集合，例如只有 `embeddings_generated` 且本次有真实 embedding 才能进入 dedup/cluster。
2. `skipped_*`、`blocked_*`、异常或“真实 embedding 全部失败”都进入熔断分支。
3. 熔断分支不得发布 dedup/clustering `running` 事件。
4. 熔断分支固定：`dedup_removed=0`、`themes_created=0`、资产统计为空。
5. 最终 run / SSE 必须同时表达：
   - 文本提取完成；
   - 语义阶段未执行；
   - 真实原因；
   - 总状态为 `completed_with_skips`、`partial` 或项目内等价的非“全部成功”状态。
6. 静态 SPA 和 Streamlit 都从真实 run 状态展示“文本提取完成；语义去重/聚类未执行”，不得用轮询数量猜测“正在聚类”。

#### 阶段 B 验收标准

- no-real-embedding 负例中 dedup / cluster / asset 调用次数全部为 0。
- 本次 run 不新增 dismissed、Theme、pseudo embedding。
- 事件流中没有 dedup/clustering `running` 事件。
- UI 不显示“语义阶段成功”或无修饰“Pipeline 全部成功”。

### 阶段 C：收紧 test-only 边界和审计版本

#### 开发方法

1. 伪向量 fixture 优先改为测试依赖注入，不让生产代码读取一个可直接开启伪向量的环境变量。
2. 如果必须暂时保留 `ALLOW_TEST_PSEUDO_EMBEDDING`：必须同时强制 `environment == "test"`，并增加 production/development 设置该变量仍不可生成向量的负例。
3. `confidence_model_version` 按实际 profile 选择 prompt version：
   - product feedback → product prompt version；
   - AIGC video → video prompt version。
4. 增加真实持久化断言，不得只测试常量或 Pydantic 输入对象。

#### 阶段 C 验收标准

- production/development + `ALLOW_TEST_PSEUDO_EMBEDDING=true` 仍返回 blocked/skipped，数据库不写 embedding。
- test 环境的 fixture 路径可用，但只服务测试。
- product 和 video 各持久化一条信号，`confidence_model_version` 的 prompt 部分分别正确。

### 阶段 D：重写机器证据为真实行为门禁

#### 开发要求

重写 `scripts/p13_1_baseline_metrics.py`，禁止使用以下方法判定 PASS：

- `inspect.getsource()`；
- 搜索注释或任意字符串是否存在；
- 硬编码 `passed=True`；
- 执行方在脚本外口头声称 pytest 已通过。

脚本必须：

1. 强制 required gate 精确存在：
   - `confidence_contract`
   - `signal_type_validation`
   - `evidence_validation`
   - `pseudo_embedding_blocked`
   - `no_new_destructive_dismiss`
   - `frontend_semantics`
   - `regression`
2. 每个 gate 保存 `method`、真实命令或 fixture 名称、退出码、关键观测值和 `passed`。
3. `regression.passed` 来自本次脚本实际启动的 pytest 子进程退出码；未运行时必须 false。
4. 在隔离临时数据库执行 no-real-embedding 负例，保存运行前后：Signal、pseudo、dismissed、Theme 数量与 delta。
5. `pseudo_embedding_blocked` 保存 dedup / cluster / asset 调用次数，三者必须为 0。
6. `signal_type_validation` 运行真实 fake-LLM 提取路径并验证非法类型不入库。
7. `confidence_contract` 运行低分合法信号持久化负例。
8. required gate 缺失、任一 false、命令未运行或证据解析失败时，顶层 `passed=false` 且进程非 0。
9. 输出继续写入 `docs/P13-1-evidence/metrics.json`，不得修改正式数据库。

#### 阶段 D 验收标准

- 故意恢复 runner 的错误调用时，脚本必须非 0 且 `pseudo_embedding_blocked.passed=false`。
- 故意恢复 0.5 自评分过滤时，脚本必须非 0 且 `confidence_contract.passed=false`。
- 故意删除一个 required gate 时，顶层必须 FAIL。
- 故意让 pytest 子进程失败时，`regression.passed=false`。

这些 mutation 可通过 monkeypatch / 专用失败 fixture 证明，不要求真的改坏工作树后提交。

### 阶段 E：真实浏览器验收与交付报告同步

#### 开发方法

1. 使用临时数据库副本启动本次代码对应的本地服务，记录实际 host、port、启动时间和进程退出状态。
2. 在真实浏览器中检查并保存 PNG：
   - `#signals`：卡片、查看筛选、Evidence、来源按钮；
   - `#pipeline`：不再存在自动置信度门槛；执行 no-real-embedding 流程后显示真实 skip 状态；
   - AI 模型状态卡：DeepSeek 主模型和多模态入口仍显示；
   - AIGC profile 切换仍可见。
3. 浏览器证据必须包含 DOM 断言结果和截图路径。源码字符串检查不得作为 fallback。
4. 浏览器不可用、截图失败或 DOM 断言失败时，脚本必须非 0；交付自评必须为 BLOCKED/FAIL。
5. 更新 `docs/acceptance-P13-1-delivery-20260710.md`：
   - 明确这是 fix-1；
   - 记录实际命令、退出码和由命令产生的测试数；
   - 与同一次生成的 `metrics.json` 数值逐项一致；
   - 删除已被指挥官反例推翻的旧结论；
   - 不得宣称 calibrated confidence、真实语义去重或可靠聚类已经完成。

## 必须新增或加强的测试

至少覆盖以下行为：

1. `confidence=0.01` + legacy threshold 0.99：合法信号仍真实入库。
2. 低分信号新契约字段真实持久化。
3. product profile 返回 `viral_hook`：真实提取路径拒绝，不入库。
4. product / video 分别记录正确 prompt version。
5. no-real-embedding：dedup / cluster / asset `await_count == 0`。
6. no-real-embedding：Signal、pseudo、dismissed、Theme 的前后 delta 均为 0，除允许新增的文本信号外不得新增错误状态；应分别报告“文本信号新增量”和“错误状态新增量”。
7. production/development 不能开启 test-only pseudo embedding。
8. 实际调用 `find_similar_signals` 时历史 pseudo 记录不返回。
9. Pipeline run / SSE 返回非“全阶段完成”的 skip 状态。
10. API Schema 明确标记 legacy `confidence` / `confidence_threshold` / `min_confidence`。

## 验收命令

### 静态检查

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
node --check scripts/p13_1_browser_verify.js
git diff --check
```

### 聚焦测试

```bash
.venv/bin/python -m pytest \
  tests/test_confidence_contract.py \
  tests/test_evidence_validation.py \
  tests/test_embedding_safety.py \
  tests/test_pipeline.py \
  tests/test_pipeline_integration.py -q
```

### 全量回归

```bash
.venv/bin/python -m pytest -q
```

### 机器证据

```bash
.venv/bin/python scripts/p13_1_baseline_metrics.py
.venv/bin/python - <<'PY'
import json
from pathlib import Path

required = {
    "confidence_contract",
    "signal_type_validation",
    "evidence_validation",
    "pseudo_embedding_blocked",
    "no_new_destructive_dismiss",
    "frontend_semantics",
    "regression",
}
data = json.loads(Path("docs/P13-1-evidence/metrics.json").read_text(encoding="utf-8"))
assert set(data["checks"]) == required
assert all(data["checks"][name]["passed"] is True for name in required)
assert data["checks"]["pseudo_embedding_blocked"]["dedup_await_count"] == 0
assert data["checks"]["pseudo_embedding_blocked"]["cluster_await_count"] == 0
assert data["checks"]["pseudo_embedding_blocked"]["asset_await_count"] == 0
assert data["checks"]["regression"]["exit_code"] == 0
assert data["deltas"]["new_pseudo_embeddings"] == 0
assert data["deltas"]["new_dismissed"] == 0
assert data["deltas"]["new_themes"] == 0
assert data["passed"] is True
print("P13-1 fix-1 behavioral gates passed")
PY
```

### 迁移守恒

虽然本轮禁止新增迁移，仍需在临时数据库副本复跑：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

报告迁移前后 RawFeedback、Signal、Theme、dismissed 数量；不得只写“成功”。

### 文案自查

以下命中必须逐条解释；当前活动页面不得保留裸“最低置信度”：

```bash
rg -n "最低置信度|Min confidence|Only include signals with confidence|confidence >= confidence_threshold" \
  frontend/static/app.js frontend/app.py signal_miner/pipeline/extraction.py signal_miner/pipeline/prompts.py
```

## 交付物

必须同时提交：

1. 更新后的 `docs/acceptance-P13-1-delivery-20260710.md`
2. 更新后的 `docs/P13-1-evidence/metrics.json`
3. `docs/P13-1-screenshots/` 下真实 PNG 和 DOM 断言证据

交付报告必须包含：

- 修改文件与目的；
- 各阶段实现说明；
- 低分合法信号入库证据；
- runner 三个调用次数；
- test-only 环境边界负例；
- product/video prompt version；
- 数据库前后计数和 delta；
- 每条命令实际退出码与测试数；
- 浏览器 URL、DOM 区域、截图路径；
- 未覆盖风险。

## 完成回复格式

完成后只回复：

```text
P13-1 fix-1 completed.

Changed:
- <file>: <summary>

Behavioral evidence:
- low-score persisted: <value>
- dedup/cluster/asset await_count: <0/0/0>
- new pseudo/dismissed/themes delta: <0/0/0>
- regression: <exit code, test count>
- browser: <URL and screenshot paths>

Artifacts:
- docs/acceptance-P13-1-delivery-20260710.md
- docs/P13-1-evidence/metrics.json
- docs/P13-1-screenshots/<files>

Remaining blockers:
- None, or list exact blocker.
```

不要生成 P13-2 指令；等待指挥官独立复验。

