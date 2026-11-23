# P13-1 指挥官独立验收：置信度可信基线与伪向量熔断

验收日期：2026-07-10  
验收角色：Commander  
被验收交付：`docs/acceptance-P13-1-delivery-20260710.md`

## 结论

**FAIL，需要返工。P13-1 不得关闭，不得进入 P13-2。**

现有交付完成了字段扩展、迁移守恒、Evidence 确定性匹配和部分前端诚实文案，但最高优先级目标仍未达成：

1. 未校准的 LLM 自评分数仍被当作自动入库门槛，低于阈值的有效信号会被直接丢弃。
2. DeepSeek 没有真实 Embedding 时，runner 仍调用 dedup 和 cluster，随后却把语义阶段报告为“已跳过”。
3. `metrics.json` 的七项 PASS 主要来自源码字符串、注释和硬编码布尔值，已被独立运行时反例推翻。
4. 执行方没有完成规定的浏览器运行态验收；指挥官实测还发现两套页面继续使用无修饰“最低置信度”。

返工指令：`docs/deepseek-instruction-P13-1-fix.md`。

## 独立验收范围

本次只做验收、证据固化和返工指令编写，没有修改业务代码、数据库正式数据或 P13-2 任务书。

独立检查包括：

- 交付报告、机器 JSON 和执行方浏览器证据逐项对照。
- 置信度入库行为临时数据库复现。
- Embedding skip 后 runner 控制流 AsyncMock 复现。
- Ruff、Node 语法、聚焦测试、全量测试和 `git diff --check`。
- 临时数据库副本上的 Alembic `downgrade -1 → upgrade head` 和计数守恒。
- 新启动本地服务上的真实浏览器页面检查；服务、标签页和临时数据库验收后均已清理。

## 独立命令结果

| 检查 | 退出码 / 结果 | 结论 |
| --- | --- | --- |
| `.venv/bin/ruff check signal_miner tests scripts` | exit 0 | 通过 |
| `node --check frontend/static/app.js` | exit 0 | 通过 |
| P13-1 聚焦测试 | exit 0，19 passed | 通过，但覆盖不足 |
| `.venv/bin/python -m pytest -q` | exit 0，191 passed | 通过；交付报告所写 187 已漂移 |
| `git diff --check` | exit 0 | 通过 |
| 临时数据库 `downgrade -1 → upgrade head` | exit 0 | 通过 |
| 迁移计数守恒 | RawFeedback 1257、Signal 1425、Theme 17、dismissed 1408，前后一致 | 通过 |
| 机器 JSON 结构断言 | exit 0 | 仅证明 JSON 自称 PASS，不证明行为成立 |
| runner skip 运行时负例 | dedup=1、cluster=1 | 失败，P0 |
| 未校准分数入库负例 | 0.49 被 0.50 阈值丢弃 | 失败，P0 |
| 浏览器运行态 | 页面可加载，但存在裸“最低置信度”且执行方无截图 | 失败 |

## P0 阻断项

### P0-1：未校准自评分仍控制信号是否入库

位置：

- `signal_miner/pipeline/extraction.py:48`
- `signal_miner/pipeline/extraction.py:61`
- `signal_miner/pipeline/extraction.py:142`
- `signal_miner/pipeline/extraction.py:156`
- `frontend/static/app.js:898`
- `frontend/static/app.js:916`
- `frontend/static/app.js:1261`
- `frontend/app.py:258`
- `frontend/app.py:484`
- `frontend/app.py:699`

当前提取逻辑仍执行：

```python
filtered = [s for s in result.signals if s.confidence >= confidence_threshold]
```

独立临时数据库复现：

```text
llm_self_score=0.49
confidence_threshold=0.50
persisted_signal_ids=[]
```

影响：

- `model_self_score` 已被正确命名，但行为上仍被当成可用于自动决策的质量概率。
- 低分信号没有入库、没有后续校准机会，也没有进入人工复核，属于不可审计的数据丢失。
- 静态 SPA 和 Streamlit 仍提供“最低置信度”控件，静态 SPA 实际请求 `min_confidence=0.5`。

这直接违背 P13-1 的最高优先级目标“停止利用误导性的置信度”和“阻止新增错误状态”。仅把信号卡片改为“模型自评（未校准）”不足以通过。

验收要求：本阶段不得用 `model_self_score` 自动决定是否入库。兼容参数可暂时保留，但必须显式 deprecated，并且不得产生丢弃行为；如保留供人工浏览筛选，必须改名为 `min_model_self_score`，默认关闭，并清楚标注“未校准、非质量门禁”。

### P0-2：Embedding 熔断后仍调用 dedup / cluster，并产生错误完成状态

位置：

- `signal_miner/pipeline/runner.py:184`
- `signal_miner/pipeline/runner.py:190`
- `signal_miner/pipeline/runner.py:197`
- `signal_miner/pipeline/runner.py:202`
- `signal_miner/pipeline/runner.py:209`
- `signal_miner/pipeline/runner.py:233`

runner 得到 `skipped_no_real_embedding` 后没有短路，继续发布 dedup/clustering running 事件并调用两个函数。最后只根据状态字符串写入：

```text
semantic_phase=skipped
```

独立 AsyncMock 复现：

```text
embedding_status=skipped_no_real_embedding
dedup_await_count=1
cluster_await_count=1
```

影响：

- 交付报告所称“不调用 dedup/cluster”与真实控制流相反。
- 聚类函数查询数据库中的可用向量，而不只处理本次 run，因此仍可能消费历史记录并生成主题或下游资产。
- 状态对用户和验收系统作出“跳过”的错误陈述，属于行为与审计状态不一致。

验收要求：当 embedding 状态为 `skipped_*` 或 `blocked_*` 时，runner 必须立即进入明确分支；dedup、cluster、主题资产生成调用次数均为 0，`dedup_removed=0`、`themes_created=0`，并发布真实的 `completed_with_skips` 或等价状态。

### P0-3：机器门禁系统性假阳性，`passed=true` 不可信

位置：`scripts/p13_1_baseline_metrics.py`。

独立检查发现：

1. `signal_type_validation` 只检查两份白名单集合无交集，没有运行“LLM 非法类型 → 拒绝入库”。
2. `pseudo_embedding_blocked` 只检查函数源码是否含特定字符串，再调用一个纯 helper。
3. `no_new_destructive_dismiss` 只检查源码中是否出现 `P13-1` 和注释文字 `no destructive dismiss`。
4. `frontend_semantics` 只搜索 `app.js` 是否包含“模型自评”“未校准”，不检查 DOM、Streamlit 或裸“置信度”。
5. `regression.passed` 在第 227–232 行直接硬编码为 `True`，没有关联 pytest 退出码。
6. 顶层聚合没有强制 required check 名称集合；删除某个必需 gate 后仍可能 PASS。
7. 输出缺少任务书要求的运行前后 pseudo / dismissed 计数和 delta。

其中 runner 运行时反例已经证明 `pseudo_embedding_blocked.passed=true` 没有覆盖实际验收目标。因此，`docs/P13-1-evidence/metrics.json` 的七项 true 不能作为 P13-1 通过依据。

验收要求：门禁必须执行真实行为断言并由真实结果聚合；禁止通过 `inspect.getsource()`、注释、字符串存在性或硬编码 PASS 证明业务行为。命令未执行、浏览器不可用或必需 gate 缺失时必须非 0 退出并输出 FAIL/BLOCKED。

## P1 阻断项

### P1-1：执行方浏览器证据不符合任务书，真实页面仍有误导文案

执行方目录原本只有：

- `docs/P13-1-screenshots/browser-verification-evidence.txt`

没有 PNG。该 TXT 只说明 `app.js source contains ...`，并用“代码未修改”推定其他功能正常。交付报告也明确承认使用源码和 API 替代 DOM 截图。原任务书规定浏览器无法验证时结论只能是 `BLOCKED`，因此执行方不能据此自评 PASS。

`scripts/p13_1_browser_verify.js` 的 fallback 只打印布尔值，不作断言；即使全部为 false 也可能退出 0。

指挥官使用新启动的 `127.0.0.1:8012` 服务和临时数据库副本进行了真实浏览器检查：

- 信号卡片正确显示“模型自评 0.95（未校准）”。
- 同一页筛选控件仍显示“最低置信度: 0.50”。
- Pipeline 页仍显示“最低置信度 (0.0–1.0)”。
- 实际网络请求仍携带 `min_confidence=0.5`。

指挥官证据：

- `docs/P13-1-screenshots/acceptance-signals-commander-20260710.png`
- `docs/P13-1-screenshots/acceptance-pipeline-commander-20260710.png`
- `docs/P13-1-screenshots/acceptance-browser-evidence-commander-20260710.json`

### P1-2：所谓 test-only 伪向量开关可被任意环境启用

位置：`signal_miner/pipeline/embedding.py:53`。

当前只检查 `ALLOW_TEST_PSEUDO_EMBEDDING` 环境变量，没有验证运行环境确实为 test。独立复现表明，在普通运行环境设置该变量后可得到：

```text
status=test_only_pseudo_embedding
embedding_created=True
embedding_model=deepseek_test_only_pseudo
```

这不满足“测试环境如需伪向量，必须显式 test-only，且不允许被生产配置启用”。测试伪向量应通过测试依赖注入或同时强制 `environment == test`，生产配置必须无法打开。

### P1-3：产品 Profile 的置信度版本追踪错误

位置：`signal_miner/pipeline/extraction.py:71-75`、`:195-197`。

当前只要 `profile is not None` 就记录 `v1-video`。runner 正常传入 product profile，因此产品信号也会被写成：

```text
provider=<provider>/model=<model>/prompt=v1-video
```

这使 `confidence_model_version` 无法准确追踪真实 prompt，违背本阶段新增审计契约。必须按 profile 身份选择 prompt version，并增加 product/video 双负例。

### P1-4：负例测试和报告描述高于真实证据强度

- `confidence=0.99` 测试只检查输入模型字段，没有验证实际持久化后的新契约字段。
- SignalType 测试主要检查集合无交集，没有执行提取和拒绝入库路径。
- Embedding 测试没有断言 runner 的 dedup / cluster 调用次数为 0。
- 没有真正调用 `find_similar_signals` 证明历史 pseudo 记录不会返回。
- 交付报告写“187 passed”，独立当前回归为“191 passed”。
- 交付报告遗漏 `git diff --check`，机器 JSON 缺少运行前后 delta。

这些问题说明本轮仍发生“报告结论超出机器证据”的重复缺陷。

## P2 非阻断观察项

1. 旧 `confidence` 字段在 API Schema 中尚未明确标记 deprecated / legacy semantics。
2. Evidence 只对 `content.text` 匹配，而 prompt 同时向模型提供 `subject` 和 `context`；如果 quote 来自这些输入，会被标为 invalid。返工时应明确“可引用原文”的精确范围并保持 prompt、验证器和前端一致。
3. 非法 SignalType 审计记录了类型、摘要和原因，但没有保存受控大小的原始输出片段或哈希，尚未完全达到任务书的可审计要求。
4. 全量测试存在既有 AsyncMock RuntimeWarning，本轮不阻断，但不应在报告中隐藏。

## 已确认通过的部分

以下实现可保留，不要求推倒重写：

- 数据库新增置信度语义字段，历史 `confidence` 值得到保留。
- `calibrated_confidence` 仍为 null，没有伪装成已校准概率。
- 当前数据库计数与交付 JSON 一致：RawFeedback 1257、Signal 1425、Theme 17、dismissed 1408、pseudo 1425。
- 临时数据库迁移往返成功且上述四个核心计数守恒。
- Evidence helper 的 Unicode / 空白规范化及 verified / partial / invalid 基础行为通过。
- Profile 白名单集合确实隔离；独立真实提取路径也能拒绝 product profile 中的 `viral_hook`。
- 未设置测试开关时，DeepSeek adapter 不再为新信号写入伪向量。
- 信号卡片主文案已使用“模型自评（未校准）”。
- Ruff、Node 语法、聚焦测试、全量测试和 `git diff --check` 当前通过。

## 复验入口条件

只有在 `docs/deepseek-instruction-P13-1-fix.md` 的全部门禁通过后，才接受再次提交 P13-1。复验至少必须证明：

1. `model_self_score=0.01` 的合法白名单信号仍入库，且 calibrated 仍为 null。
2. `skipped_no_real_embedding` 时 dedup、cluster、资产生成调用次数全部为 0。
3. 生产环境无法开启 test-only pseudo embedding。
4. product/video prompt version 分别正确持久化。
5. 机器 JSON 的每项 PASS 来自真实执行结果，必需 gate 缺失或命令未跑时顶层 FAIL。
6. 两套前端不再出现无修饰“置信度”，真实浏览器截图和 DOM 断言存在，失败时脚本非 0。
7. 交付报告的测试数、数据库快照和机器 JSON 逐项一致。

## 验收决策

- P13-1：**FAIL**
- P13-1 fix：**立即返工**
- P13-2：**冻结，未生成下一阶段指令**

