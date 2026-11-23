# DeepSeek 返工指令：P13-2-2-1A fix-3 证据Orchestrator与顶层Passed闭环

## 任务目标

修复contract metrics忽略输入gate失败并硬编码passed=true的问题；建立真实的同次run_id证据链。

## 允许修改范围

- `scripts/p13_2_pack_trust_contract_metrics.py`
- 两个mutation gate的CLI参数与evidence元数据
- 新增独立orchestrator或将聚合器升级为orchestrator
- 对应聚焦测试、evidence和交付报告

## 禁止修改范围

- Pack trust、dataset manifest、密钥边界、annotation导入业务逻辑
- 手工给旧JSON补相同run_id后宣称同次运行
- `passed=True`常量或仅依赖计数推导所有子gate通过
- 忽略任何输入gate的top-level/invariant/meta-negative字段
- 生产pipeline、数据库、API、前端和后续阶段

## 实现要求

### 1. 单一Orchestrator生成同次证据

正式CLI必须：

1. 生成唯一run_id和started_at。
2. 依次启动pack trust mutation gate与annotation mutation gate，并把run_id作为参数传入。
3. 两个gate把相同run_id、各自generated_at、command/exit code写入输出JSON。
4. Orchestrator只读取本次指定临时/输出路径，不读取无法证明时序的历史默认JSON。
5. 校验两个子进程exit均为0、run_id相等、生成时间在本次started/finished窗口内。
6. 记录两个输入evidence的SHA-256。
7. 验证通过后原子写最终contract metrics。

可保留当前脚本名，但其行为必须是“运行并聚合”，而不是给任意历史文件补一个新UUID。

### 2. 顶层Passed必须完整复算

最终passed必须至少AND以下条件：

- pack gate `passed is true`
- pack所有mutation严格契约通过
- pack `readiness_invariants_passed is true`
- annotation gate `passed is true`
- annotation计数与逐行detected一致
- annotation `readiness_invariants_passed is true`
- annotation `meta_negatives_passed is true`
- 两个子命令exit=0
- run_id/时间窗口/SHA检查通过
- 所有状态不变量符合阶段要求

任一false、null、缺失、错误类型、UNKNOWN均exit1并输出passed=false。禁止硬编码 `"passed": True`。

### 3. 必须新增的元负例

至少覆盖：

1. pack gate `passed=false`，逐行仍全true。
2. annotation gate `passed=false`，逐行仍全true。
3. annotation `meta_negatives_passed=false`。
4. annotation `readiness_invariants_passed=false`。
5. pack `readiness_invariants_passed=false`。
6. 任一关键字段缺失或字符串`"true"`。
7. 两个gate run_id不同。
8. 一个gate没有run_id。
9. 一个gate generated_at早于本次started_at或晚于finished_at。
10. 子命令exit非0但JSON伪造passed=true。
11. evidence在聚合前后SHA变化。
12. 使用上一轮旧gate JSON搭配本轮新JSON。

所有元负例必须使orchestrator/聚合器exit1、final passed=false。

### 4. Artifact职责

最终三个JSON应明确包含：

- 同一run_id
- 各自generated_at
- phase/schema version
- child command和exit
- actual counts
- artifact SHA引用

交付报告中的数字和run_id必须来自最终metrics，不得手写。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_metrics_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/pack-trust-mutation-gate.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/human-annotation-mutation-gate.json >/dev/null
git diff --check
```

Orchestrator若已内部运行两个gate，验收不再额外先跑旧gate命令，防止制造不同run证据。

## Commander强制元负例

将临时annotation gate设为：

```json
{
  "passed": false,
  "meta_negatives_passed": false,
  "readiness_invariants_passed": false
}
```

即使34/34 mutation仍为detected，聚合器必须exit1、final passed=false且列出三个失败原因。

## 回归要求

- 省略dataset manifest继续exit1。
- fixture缺pack manifest继续exit1。
- production/development/空/staging测试密钥继续拒绝。
- production/test缺对应key的readiness exit2不回退。
- 23类pack mutation、34类annotation mutation和状态不变量保持。

## 交付报告模板

```markdown
# P13-2-2-1A fix-3交付报告

## 结论
## 修改文件
## 同次run orchestrator
## Final passed复算表
## Commander false-input元负例
## Run ID/时间/SHA证据
## 行为安全回归
## 状态不变量
```

交付文件：`docs/acceptance-P13-2-2-1A-delivery-fix-3-20260713.md`。

## 完成边界

通过仍只表示外部pack信任根工具和证据链可信。真实授权候选为0时，P13-2-2-2及校准继续冻结。
