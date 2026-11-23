# DeepSeek 返修指令：P13-2-2-2A readiness 真实门禁闭环

## 任务目标

关闭 P13-2-2-2A 的 `READY` 假绿，使正式 CLI 只从受控文件/secret provider 消费真实输入，严格区分“缺输入 exit2”与“输入已提供但无效 exit1”。当前没有真实输入，返修后的正式结果仍应为 `BLOCKED_INPUT_REQUIRED/exit2`；不得伪造输入以追求 READY。

## 当前已确认根因

1. 直接信任 `eligible_count`，没有与候选数组长度及授权完整行数对账。
2. `authorization_incomplete_rows` 只记录不阻断，0 条完整授权候选也能 READY。
3. roles/splits/test packs/PII 只有 test override，正式 CLI 不消费真实配置。
4. 未实现执行窗口、保留期限、允许访问角色门禁。
5. READY 不验证 dataset/pack/task hash、签名、精确文件集合和 A/B 访问边界。
6. 所有错误统一 exit2，安全违规没有 exit1。
7. 14 类负例存在错测、漏测和弱断言。
8. artifact SHA 自引用发布导致机器值、实际文件和报告三方漂移。

## 允许修改范围

- `scripts/p13_2_real_annotation_launch_readiness.py`
- `tests/test_p13_2_real_annotation_launch_readiness.py`
- 必要时新增仅服务于 readiness 的小型 schema/config helper 与测试 fixture。
- `docs/P13-2/` 下的真实输入 runbook/schema 示例；示例不得包含真实数据、秘密或可识别个人信息。
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`
- 本阶段交付报告。

不得重写或放宽 P13-2-2-1A 已验收的 pack trust、annotation importer、23/34 mutation、orchestrator和 committed verifier。若需验证签名/hash，必须复用 1A 的生产 verifier/契约单一真源，不得复制一个弱化版本。

## 必须实现

### 1. 真实候选重算，不信任自报 count

- 从实际候选记录重算 `row_count`、`authorization_complete_count`、`authorization_incomplete_count`。
- `eligible_count` 只能作为声明值；必须严格等于实际合格记录数，否则 `COUNT_RECOMPUTE_MISMATCH/exit1`。
- 合格数以逐行 schema + 授权校验后的记录为准，必须 ≥100 才能 READY。
- 候选数组缺失、类型错误、重复 sample/content hash、hash格式错误、URL/时间/adapter/version/授权/用途/PII字段错误均不得计入合格数。
- 明确定义字段类型：例如 `permitted_use` 为非空允许值列表，`pii_scanned` 与 `pii_redacted` 必须严格为 true，SHA-256必须为64位十六进制；不得把 bool/list 当字符串验证。
- `real_rejections` 必须读取并进行计数守恒与原因分布对账，不能只在 audit 中记录路径。

### 2. 正式 CLI 消费受控输入

提供明确的只读路径参数或单一 launch config，至少能引用：

- real candidate export 与 real rejections；
- dataset manifest、冻结 split manifest、pack manifest、四个签名 pack；
- A/B/adjudicator pseudonym 角色配置；
- 标注窗口、retention、允许访问角色配置；
- production secret provider/key id（密钥仍只从环境或 secret provider 注入，绝不写文件/日志）。

测试 override 不能成为 production 绕过通道。测试应通过与 CLI 相同的加载和校验主路径；若保留依赖注入，必须有明确 test-only 边界，production 环境不能用任意内存字典绕过文件与信任链。

### 3. READY 必须完整 AND

`READY_FOR_HUMAN_ANNOTATION/passed=true/exit0` 必须同时满足：

- 重算后真实授权合格候选 ≥100，声明 count 与实际一致；
- split 冻结且满足 50/25/25，无 sample/content/session/近重复跨 split；
- test ≥25，任务内容无任何模型答案泄漏；
- 双标数 ≥`max(20, ceil(n*20%))`；
- A/B/adjudicator三角色独立，A/B任务包访问边界成立；
- 执行窗口有效、retention明确、允许访问角色非空且只含受控 role id；
- production key非test/fixture替代；
- 复用 1A verifier 验证 dataset hash、pack SHA/bytes/count、signature、task hash、run/batch/dataset identity和精确文件集合；
- fixture/test key/机器gold计数均为0；
- 所有 REQUIRED check 必须为严格 bool true，UNKNOWN/NOT_PROVIDED/null均不得 READY。

本阶段即使 READY，仍必须固定：`human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。

### 4. 退出码和状态分类

- 关键外部输入完全缺失：顶层 `status=BLOCKED_INPUT_REQUIRED`、`passed=false`、`exit_code=2`；细分缺失原因放在 `blockers[]`。
- 输入已提供但 schema、计数、授权、PII、split、盲标、角色、访问、签名或 hash 无效：顶层 `status=FAILED_INVALID_INPUT`（或等价稳定失败状态）、`passed=false`、`exit_code=1`；对应结构化 check target 必须存在且为 false。
- 所有输入及门禁有效：`READY_FOR_HUMAN_ANNOTATION/passed=true/exit0`。
- 不得把 test blind 泄漏、签名篡改等安全失败降级为“等待输入”。

### 5. readiness 机器证据

正式 JSON 至少稳定包含：

- status/passed/exit_code/errors/blockers/schema_version；
- dataset_id、batch_id、dataset manifest SHA、pack manifest SHA（缺输入时为 null并由对应check=false）；
- declared/recomputed/authorized/rejected counts及原因；
- dev/cal/test数量、跨split重复与盲标泄漏计数；
- double-label count/ratio；
- 三角色就绪与访问边界；
- 标注窗口、retention、access readiness（不得记录真实姓名）；
- production pack trust、key id、1A verifier结果；
- 三个阶段不变量。

不要把最终文件字节 SHA 自引用写回同一 JSON 后再声称它是最终 SHA。可选择：

1. 发布最终 JSON 后写独立 `.sha256` sidecar并读回核对；或
2. 明确定义“排除 artifact_sha 字段后的 canonical payload hash”，字段名与 scope 必须清楚，另在交付报告记录最终文件真实 SHA。

交付报告、sidecar/机器字段与 `sha256sum` 必须一致。

## 必须重写/补齐的负例

所有已提供但无效的负例必须通过真实生产判定主路径得到 `exit1`、`passed=false`，并断言指定结构化 target=false：

1. 实际99行但声明 `eligible_count=100`。
2. 100行但至少1行fixture污染。
3. 每个授权必填字段分别缺失/类型错误；完整合格数随之减少并阻断。
4. 未脱敏PII进入候选或任务包。
5. 相同 content hash、sample或session跨development/test；近重复策略也要有真实门禁证据。
6. test任意层级含preannotation/prediction/model/confidence等禁用字段。
7. 双标少于20或20%。
8. A/B pseudonym相同。
9. A包能读取B标签，及B包能读取A标签；不能再用角色碰撞替代。
10. production使用test/fixture key或test key与prod key相同。
11. 分别篡改pack signature、dataset hash、task hash，必须经复用的1A verifier阻断；不能用“缺密钥”替代。
12. 任一人工角色未就绪却尝试READY。
13. 输入/旧artifact试图把 `human_verified_count` 写为正数。
14. 输入/旧artifact试图把 `calibration_allowed` 写为true。
15. 缺执行窗口、retention或access配置时为exit2；已提供但非法时为exit1。
16. 最终artifact发布后SHA/sidecar被篡改，独立验证必须exit1。

测试不得只断言“发现了计数”而不检查最终 passed/exit/target。测试不得修改正式 evidence；聚焦和全量测试前后正式 artifact SHA 必须不变。

## 当前正式运行的正确预期

由于用户尚未提供真实授权候选、生产密钥、独立人工角色和执行窗口，返修完成后正式运行必须仍然：

```text
status=BLOCKED_INPUT_REQUIRED
passed=false
exit_code=2
human_verified_count=0
human_labels_complete=false
calibration_allowed=false
```

这不是要求制造 READY。只有临时受控测试 fixture 可验证正向路径；不得把 fixture 发布到正式 evidence或计入真实数量。

## 验收命令

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
git diff --check
```

另需在交付报告中给出上述16类负例的命令/测试名、真实返回码、结构化 target和正式 evidence 前后SHA。

## 完成边界

本次只返修 readiness。通过后也只是证明“门禁能诚实判定 READY 或 BLOCKED”，当前没有真实输入时仍停在 P13-2-2-2A。不得开始真实人工标签计数，不得进入 P13-2-2-2B或任何下游调优/校准/聚类/前端发布。

