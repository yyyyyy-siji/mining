# DeepSeek 执行指令：P13-2-2-1 授权样本接入、人工标注导入与一致性工具

## 任务目标

建立真实人工标注的接入、隔离、导入、验证、分歧记录和一致性计算工具，使授权标注员可以完成assisted-review与blind A/B任务。

本阶段只建设工具和机器门禁。当前真实候选为0，因此允许fixture验证代码，但**禁止用DeepSeek、其他LLM、规则标签或fixture冒充真实人工标注，禁止把业务状态写成COMPLETE。**

## 当前状态

- P13-2-1已通过。
- fixture：100条，development/calibration/test=50/25/25。
- 真实数据库：0条合格，1,257条因缺失显式授权与source platform被拒绝。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。

P13-2-2拆为：

1. **P13-2-2-1（本次）**：授权候选接入、人工任务包、标签导入和一致性工具。
2. P13-2-2-2：真实人工标注执行、至少100条验证、25条test盲标、≥20%双标和分歧裁决验收。

## 允许修改范围

- `signal_miner/evaluation/`下新增人工标注schema与一致性模块
- 新增`scripts/p13_2_prepare_human_tasks.py`
- 新增`scripts/p13_2_import_human_annotations.py`
- 新增`scripts/p13_2_validate_human_annotations.py`
- 新增`scripts/p13_2_annotation_mutation_gate.py`
- 新增`tests/test_p13_2_human_annotation_contract.py`
- `docs/P13-2/`人工标注操作说明
- `sample_data/p13_2/annotations/`明确标记为fixture的正负例
- `docs/P13-2-evidence/`机器证据和交付报告

## 禁止修改范围

- 生产pipeline、prompt、LLM adapter、Embedding、去重、聚类
- 数据库模型、迁移、API、前端
- P13-1与P13-2-1已通过契约
- 真实历史数据的授权字段批量回填
- P13-2-3指标调优和P13-2-4概率校准
- P13-3及后续阶段

## 实现要求

### 1. 授权候选接入

- 只接受通过P13-2-1 exporter/validator的candidate dataset。
- 每条必须有显式`authorization_basis`、`source_platform`、`capture_method`和冻结content hash。
- 禁止根据公开URL、capture method或来源名称推导授权。
- 当前真实候选为0时输出`BLOCKED_WAITING_AUTHORIZED_DATA/exit2`，不得使用fixture补足真实状态。
- 外部授权数据只能先进入独立输入文件，经P13-2-1全部门禁后生成新dataset version；不得直接修改历史DB记录伪造授权。

### 2. 人工任务包

生成四类任务：

- development assisted-review
- calibration assisted-review
- test A blind
- test B blind

规则：

- assisted-review允许显示明确标记的suggestion，但隐藏模型身份、provider、prompt和任何score。
- test A/B不得包含任何prediction、suggestion、模型或confidence字段。
- A/B任务相互隔离，不能包含对方标签、完成状态或备注。
- 每个任务含`dataset_id`、`sample_id`、`annotator_slot`、`task_hash`和冻结文本hash。
- 真实标注员身份只保存不可逆`annotator_pseudonym`，不得写姓名、邮箱或账号。

### 3. 人工标签schema

至少包含：

- `dataset_id`
- `sample_id`
- `annotator_slot`
- `annotator_pseudonym`
- `annotation_mode`
- `has_signals`
- `signal_count`
- `signals[]`
- assisted-review的`review_action=accepted|modified|rejected`
- `started_at`、`completed_at`
- `task_hash`

每条signal：

- `signal_type`
- `summary`
- `evidence_spans`
- `implicit_need`
- `implicit_need_has_basis`
- `hallucination`
- `notes`

必须严格`extra="forbid"`，所有signal type使用生产profile单一真源。

### 4. 导入与完整性验证

- `sample_id/dataset_id/task_hash/content hash`必须与冻结任务一致。
- `signal_count == len(signals)`。
- `has_signals=false`时signals必须为空；为true时至少一条。
- evidence必须满足`redacted_text[start:end] == text`。
- summary不得为空；evidence不得为空。
- annotator slot必须与任务包一致。
- 同一标注员不得同时承担同一样本A和B。
- A/B原始标签不可覆盖；裁决产生独立记录。
- 重复导入同一annotation hash幂等；同ID不同内容必须冲突失败。

### 5. 一致性与分歧

对双标样本至少计算：

- `has_signals` Cohen's kappa
- signal count exact agreement
- signal type集合Jaccard或等价指标
- evidence span exact/overlap agreement
- 分歧样本数量与字段列表

状态规则：

- 双标不足`max(20, ceil(n×20%))`：BLOCKED。
- `has_signals` kappa <0.70：`BLOCKED_GUIDELINE_REVISION`。
- 分歧未裁决：`BLOCKED_PENDING_ADJUDICATION`。
- fixture指标只能标记`FIXTURE_PASS`，不能改变真实`human_verified_count`。

### 6. 人工计数单一真源

`human_verified_count`只能由通过全部验证的真实人工annotation去重计算，不能来自manifest手写值。

只有同时满足以下条件才允许P13-2-2-2完成：

- 真实人工验证≥100；
- test blind≥25；
- 双标达到20%且不少于20；
- kappa≥0.70；
- 分歧已裁决；
- fixture、LLM、规则和测试标签计数为0。

本阶段不得设置`calibration_allowed=true`。

## 必须存在的负例

新增mutation gate，至少覆盖：

1. fixture标签计入真实人工数量。
2. LLM suggestion直接复制为gold且无人工action。
3. test包含prediction/model/confidence。
4. A能读取B标签或反向。
5. 同一pseudonym同时标A和B。
6. task hash或content hash篡改。
7. dataset ID/sample ID不存在。
8. signal count与signals长度不一致。
9. `has_signals=false`但signals非空。
10. 非法signal type。
11. 中文Unicode evidence offset错误。
12. evidence为空或summary为空。
13. 同annotation ID不同内容重复导入。
14. 双标比例不足。
15. kappa低于0.70仍标READY。
16. 分歧未裁决仍标COMPLETE。
17. annotation含未知字段。
18. 人工姓名/邮箱泄漏到artifact。
19. `calibration_allowed=true`。
20. 当前0真实候选被fixture补齐为READY。

每个mutation必须运行正式CLI，child exit=1，指定target check存在且false；等待真实授权数据属于exit2/BLOCKED，不算契约错误。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
git diff --check
```

要求：

- fixture工具链PASS，但明确`fixture_only=true`。
- 真实候选接入当前应诚实BLOCKED/exit2。
- 20类annotation mutation全部捕获。
- 所有测试使用临时目录，交付artifact SHA零变化。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`保持不变。

## 交付物

1. `docs/acceptance-P13-2-2-1-delivery-20260712.md`
2. `docs/P13-2-evidence/human-annotation-contract-metrics.json`
3. `docs/P13-2-evidence/human-annotation-mutation-gate.json`
4. `docs/P13-2-evidence/human-annotation-readiness.json`
5. `docs/P13-2/human-annotation-operations-v1.md`

## 交付报告模板

```markdown
# P13-2-2-1交付报告：人工标注接入与一致性工具

## 结论

- fixture工具链：PASS / FAIL
- 真实候选：READY / BLOCKED / FAIL
- 人工标签：NOT_STARTED / IN_PROGRESS / COMPLETE
- annotation mutation：PASS / FAIL
- 校准发布：NOT_ALLOWED

## 修改文件

## 授权候选接入

## Assisted与blind任务隔离

## 人工标签schema与导入幂等

## A/B一致性与分歧

## Mutation结果

## Artifact SHA守恒

## P13-1/P13-2-1回归

## 外部阻断与下一步人工动作
```

## 完成边界

本阶段通过只代表人工标注工具可信。没有真实授权数据和人工A/B标签时，P13-2-2-2不得开始，P13-2-3/2-4继续冻结。
