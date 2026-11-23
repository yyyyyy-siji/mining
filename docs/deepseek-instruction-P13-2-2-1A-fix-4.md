# DeepSeek 返工指令：P13-2-2-1A fix-4 门禁集合与原子证据发布闭环

## 任务目标

关闭 fix-3 新确认的两个假绿路径：门禁集合可缩减/替换，以及 gate 文件在 SHA 计算后被篡改仍最终 PASS。测试必须直接覆盖真实 orchestrator 主路径。

## 背景 / 当前问题

正常正式运行得到 23/23 + 34/34，但 orchestrator 接受任意 1/1 未知 mutation和 0 个 pack invariant并输出 passed=true；同时它先算临时文件 SHA、后重新读取复制，复制后不复核，存在确定性 TOCTOU 假绿。

## 允许修改范围

- `scripts/p13_2_pack_trust_contract_metrics.py`
- `scripts/p13_2_pack_trust_mutation_gate.py` 的 evidence 元数据输出
- `scripts/p13_2_annotation_mutation_gate.py` 的 evidence 元数据输出
- 一个版本化的 P13-2 gate contract manifest / Python 常量模块
- `tests/test_p13_2_pack_trust_metrics_contract.py`
- P13-2 三份机器 evidence 和本次交付报告

## 禁止修改范围

- Pack trust、dataset manifest、annotation importer/validator 的业务规则
- 生产 pipeline、数据库、API、前端、模型或后续阶段
- 通过降低 23/34/2/1/5 的必需集合来让测试通过
- 在测试中复制一套 orchestrator 判定逻辑
- 用普通 `write_text` 顺序覆盖三份最终 evidence 后宣称原子发布
- 手改 JSON 让 run_id、SHA 或 passed 看起来一致

## 实现要求

### 1. 版本化精确门禁契约

建立单一机器可读契约，至少声明：

- 23 个 pack mutation 的精确唯一名称集合
- 34 个 annotation mutation 的精确唯一名称集合
- 2 个 pack readiness invariant 的精确名称集合
- 1 个 annotation readiness invariant 的精确名称集合
- 5 个 annotation meta-negative 的精确名称集合
- 每类行的必需字段、严格类型和预期值
- contract schema version 与 contract SHA-256

两个 gate 和 orchestrator 必须引用同一契约单一真源。Orchestrator 对每个集合执行 exact-set equality：缺失、多余、重复、改名、未知替换均失败。不能只比较声明 count 与当前数组长度。

每个 gate evidence 必须包含 `schema_version`、`contract_sha256`、`run_id`、`generated_at`、安全的 command 描述、`exit_code`、phase、完整结果集合。Orchestrator 必须验证这些字段的严格类型和值，并核对子进程真实退出码。

### 2. 单一 bytes snapshot 与原子发布

子进程完成后，对每个 gate 输出：

1. 一次读取 immutable bytes snapshot。
2. JSON 解析、字段验证和 SHA-256 全部基于这同一份 bytes。
3. 不得在算 SHA 后再次从源路径读取作为发布内容。
4. 在 evidence 目录写同目录临时文件，flush + fsync 后使用 `os.replace`。
5. 发布后重新读取目标，验证 SHA、run_id、contract SHA、passed 与已验证 snapshot 完全一致。
6. 两个 gate 发布并复核成功后，最后原子发布 contract metrics；metrics 是本次 evidence commit marker。

若任一步失败，正式 CLI 必须 exit 1，最终 metrics（如可安全写出）必须 `passed=false` 并列出结构化 errors；不得留下本次 run_id 的绿色 commit marker。

需考虑进程在两个 gate 替换之间中断的情况：消费者/validator必须因 metrics run_id 与 gate run_id 不一致而拒绝混合 evidence。

### 3. Final passed 完整闭包

Final passed 至少 AND：

- 两个真实子进程 exit 0，且与各自 evidence `exit_code` 一致
- 三份 evidence run_id一致且时间在本次窗口内
- schema version 与 contract SHA一致
- 23/34/2/1/5 五个集合 exact match、无重复
- 所有 mutation 行严格满足 child_exit=1、check_exists=true、target_passed=false、detected=true
- readiness/meta-negative 每个必需项目均满足其预期结果
- 两个已发布 gate artifact 的 SHA 与 metrics 记录完全一致
- fixture/human/calibration/production 状态不变量满足阶段要求
- errors 为空

任一字段缺失、null、错误类型、UNKNOWN或集合漂移必须 exit 1 / passed=false。

### 4. 契约测试必须进入真实主路径

重构为可注入 gate runner / clock / publish hook，但测试必须调用生产 `main()` 或与 CLI 共用的唯一 orchestrator 函数，并读取它实际写出的 metrics。禁止辅助函数重新实现 `_check_*` 和 final passed。

至少加入以下端到端元负例：

1. pack mutation 缺一项。
2. annotation mutation 缺一项。
3. mutation 多一项未知名称。
4. mutation 名称重复但 count 伪装正确。
5. 用未知 mutation 替换必需项。
6. pack 2 个 readiness invariant 缺一项。
7. annotation readiness invariant 缺失。
8. annotation 5 个 meta-negative 缺一项或伪造 top-level true。
9. 子进程 exit 非0但 evidence 伪造 exit_code=0 / passed=true。
10. evidence exit_code 与真实子进程退出码不一致。
11. run_id 缺失、不同或旧新混用。
12. generated_at 窗口外、缺失、naive timezone或错误类型。
13. gate source 在 snapshot/SHA 前后发生变化。
14. 目标 artifact 发布后内容或 SHA 被改变。
15. 第二个 gate 发布前失败，不能生成本次绿色 metrics commit marker。
16. Commander 反例：1/1 arbitrary mutation + 0 pack invariant必须 exit 1 / passed=false。

正例必须使用完整 23/34/2/1/5 契约数据，禁止使用 1/1 空壳正例。

## 验收标准

### 语法 / 静态检查

```bash
.venv/bin/ruff check signal_miner tests scripts
git diff --check
```

### 功能验证

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_metrics_contract.py
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/pack-trust-mutation-gate.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/human-annotation-mutation-gate.json >/dev/null
```

正式结果必须为 23/23、34/34、2/2、1/1、5/5；三份 run_id、contract SHA一致；metrics 内两个 artifact SHA必须与实际文件相等。

### 回归验证

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
```

### 交付前质量门禁

- 交付报告中的 run_id、测试数、集合计数、SHA 必须由本次最终 metrics/命令输出自动读取，不能手写。
- 报告必须逐项列出 16 类端到端元负例的 exit code、final passed和 errors。
- 提供 Commander 两个反例的机器 JSON：coverage shrink 与 SHA race。
- 报告不得使用“原子”一词，除非代码确实使用同目录临时文件、fsync、`os.replace`和发布后复核。

## 交付报告模板

```markdown
# P13-2-2-1A fix-4 交付报告

## 结论
## 修改文件
## 版本化门禁契约与 contract SHA
## 23/34/2/1/5 exact-set 验证
## Immutable snapshot 与原子发布流程
## 16 类真实主路径元负例
## Commander coverage-shrink 反例
## Commander SHA-race 反例
## 三份 evidence run/SHA 一致性
## 回归结果
## 未覆盖风险
```

## 完成边界

fix-4 通过仍只证明 P13-2-2-1A 的外部 pack 信任根工具和 evidence 发布链可信。真实授权候选仍为 0 时，P13-2-2-2 与校准继续冻结。

