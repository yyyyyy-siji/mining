# DeepSeek 执行指令：P13-2-2-2A 真实授权候选与人工标注启动准备

## 任务目标

使用已验收的 P13-2-2-1 / 1A 工具链，为真实人工标注建立可审计的启动批次、盲标任务包、双标分配和外部签名证据。本阶段只完成启动准备，不伪造或代替人工标注，不进行校准。

## 背景 / 当前问题

P13-2-2-1A 已通过，但当前 `human_verified_count=0`，没有真实授权候选或真实人工标签。P13-2-2-2要求至少100条真实人工验证、25条test盲标、双标不少于`max(20, ceil(n×20%))`、kappa≥0.70并完成分歧裁决。

这些条件依赖用户提供真实授权数据与人工角色，不能由DeepSeek自行生成。

## 启动前置输入

必须由用户或授权运营方提供：

1. 真实候选数据文件或明确可读取位置。
2. 每条候选的来源URL/来源标识、采集时间、授权或合法使用依据、内容hash和脱敏状态。
3. 外部生产pack签名密钥或secret provider；不得提交到仓库、日志或报告。
4. 相互独立的标注员A、标注员B和裁决员角色，仅使用受控pseudonym。
5. 标注执行窗口、数据保留期限和允许访问人员范围。

任一关键输入缺失时：

- 生成 `BLOCKED_INPUT_REQUIRED` readiness报告。
- CLI/门禁 exit 2。
- 列出缺失输入，但不得写入秘密或个人信息。
- 不得使用fixture、公开测试密钥、LLM标签或规则标签补齐。
- 不得生成 `READY`、不得开始P13-2-2-2真实计数。

## 允许修改范围

- `sample_data/p13_2/` 之外的受控真实数据挂载/引用配置；真实原文不得无必要复制进Git。
- `docs/P13-2/` 下的人工标注启动runbook和脱敏操作说明。
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`。
- 真实dataset manifest、冻结split manifest和签名task pack的受控输出位置。
- 如现有CLI对真实路径存在确定性阻断，仅允许最小修复并单独报告；不得重写已验收信任链。

## 禁止修改范围

- 伪造授权证明、来源URL、采集时间或真实人工身份。
- 由DeepSeek、其他LLM、规则或fixture生成最终gold label。
- 把机器预标注计入 `human_verified_count`。
- 在test包中包含prediction、模型身份、model score、confidence或preannotation。
- 同一pseudonym同时承担同一样本的A/B双标。
- 使用fixture/test签名密钥进入真实模式。
- 设置 `human_labels_complete=true` 或 `calibration_allowed=true`。
- 开始P13-2-3指标调优、P13-2-4校准、P13-3去重聚类优化或前端概率发布。

## 实现 / 执行要求

### 1. 授权与来源准入

每条真实候选必须具备：

- 稳定 `dataset_id`、`sample_id`、`raw_feedback_id`。
- canonical source URL或可审计来源标识。
- `captured_at`、source adapter/version和content SHA-256。
- 授权依据类别、授权记录引用和允许用途。
- PII扫描与脱敏结果；原文与脱敏文本hash分别记录。
- profile、language和来源层级。

授权依据缺失、来源不可追溯、PII未处理、内容hash冲突或来源跳转不可验证的候选必须进入 `real_rejections`，不能进入任务包。

### 2. 批次规模与冻结分割

- 合格真实候选最低100条。
- 推荐冻结为50 development、25 calibration、25 test。
- test必须至少25条并完全盲标。
- 分割必须确定性、可复跑且记录seed/算法版本。
- 同内容、近重复或同一会话泄漏不得跨split。
- 冻结后不得因模型结果重新分配样本。

不足100条时状态为 `BLOCKED_INSUFFICIENT_REAL_CANDIDATES/exit2`，不得用fixture补足。

### 3. 预标注与盲标隔离

- Development/calibration可以单独生成machine suggestion，但必须与human label分字段、分文件保存。
- Test任务包禁止任何prediction、model、prompt、confidence、suggestion字段或可推断模型答案的元数据。
- 所有人工任务隐藏模型自评分。
- Test盲标泄漏扫描必须是正式门禁，发现任一字段exit1。

### 4. 双标与角色独立

- 双标样本数不少于`max(20, ceil(总样本数×20%))`。
- 优先覆盖冻结test、难例、新来源和两种profile。
- A/B任务包独立生成并独立签名。
- A不能读取B标签，B不能读取A标签。
- 同一样本A/B pseudonym必须不同；裁决员不得改写原始A/B记录。
- 本阶段只验证分配和访问边界，不生成实际人工答案。

### 5. 生产Pack信任链

- 只允许真实环境生产密钥或外部secret provider。
- 生成dataset manifest、四个pack、pack manifest和签名。
- 正式 verifier必须验证dataset hash、pack SHA/bytes/count、签名、run_id和精确文件集合。
- 生产密钥缺失：`BLOCKED_MISSING_PACK_SIGNING_KEY/exit2`。
- 报告只记录key id和算法，不记录密钥。

### 6. 启动Readiness单一真源

生成 `docs/P13-2-evidence/real-annotation-launch-readiness.json`，至少包含：

- status、passed、exit_code和errors/blockers。
- dataset_id、batch_id、manifest SHA和pack manifest SHA。
- authorized candidate count、rejection count及原因分布。
- development/calibration/test数量。
- test blind leakage count。
- double-label计划数量和比例。
- A/B/adjudicator角色就绪状态（只存pseudonym或角色ID）。
- production pack trust结果和key id。
- `human_verified_count=0`。
- `human_labels_complete=false`。
- `calibration_allowed=false`。

顶层passed必须AND所有真实输入和门禁。缺失、UNKNOWN、fixture、test key或人工角色未就绪均不得passed=true。

## 必须存在的负例

至少覆盖：

1. 候选数99但手工把count写成100。
2. fixture混入真实候选。
3. source URL/授权依据/captured_at/content hash任一缺失。
4. 未脱敏PII进入任务包。
5. 重复内容跨development与test。
6. test包含preannotation、prediction、model或confidence。
7. 双标少于20或低于20%。
8. 同一pseudonym承担A/B。
9. A包可读取B标签或反向。
10. 生产使用测试签名密钥。
11. pack签名、dataset hash或task hash被修改。
12. 人工角色未就绪却标READY。
13. 无真实人工标签却把 `human_verified_count`写为正数。
14. 本阶段把 `calibration_allowed`设为true。

每个负例必须命中指定结构化check；exit1、target存在且false才算捕获。缺少外部输入属于exit2/BLOCKED，不计作实现失败。

## 验收标准

### 无真实输入时

```text
status=BLOCKED_INPUT_REQUIRED
passed=false
exit_code=2
human_verified_count=0
human_labels_complete=false
calibration_allowed=false
```

不得生成伪真实task pack或人工label。

### 输入齐备后的启动通过条件

- 合格真实授权候选≥100。
- development/calibration/test冻结分割满足50/25/25或经Commander批准的等价分层方案。
- test盲标≥25且泄漏数为0。
- 双标计划≥`max(20, ceil(n×20%))`。
- A/B/裁决角色独立且访问边界通过。
- 生产pack签名与dataset/pack/task hash链全部通过。
- fixture/test key/机器gold计数均为0。
- Readiness可以为 `READY_FOR_HUMAN_ANNOTATION`，但 `human_verified_count`仍为0，`calibration_allowed=false`。

### 回归命令

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
git diff --check
```

## 交付报告模板

```markdown
# P13-2-2-2A 交付报告：真实人工标注启动准备

## 结论：READY / BLOCKED
## 用户提供的输入清单（不含秘密）
## 授权与来源准入统计
## 冻结split与去重隔离
## Test盲标泄漏扫描
## 双标与角色独立计划
## 生产Pack信任链
## Readiness机器证据
## 14类负例
## human/calibration状态不变量
## 未覆盖风险与人工待办
```

## 完成边界

P13-2-2-2A通过只表示真实人工标注可以安全启动，不表示人工标注已完成。只有真实人工完成≥100条、test盲标≥25、双标达标、kappa≥0.70且分歧已裁决后，才能进入P13-2-2-2B验收；P13-2-3与P13-2-4继续冻结。

