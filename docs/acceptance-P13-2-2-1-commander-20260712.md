# P13-2-2-1 Commander 独立验收报告

日期：2026-07-12

结论：**FAIL / 阻断，不得进入 P13-2-2-2。**

fixture 工具链和常规回归通过，但 mutation gate 存在确定性假阳性，且人工一致性门槛可被恒定标签绕过。当前仍须保持：`human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。

## 独立复验结果

| 项目 | 结果 |
| --- | --- |
| Ruff | PASS |
| P13-2-2-1 聚焦测试 | PASS，18 passed |
| 全量回归 | PASS，242 passed，3 warnings |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | PASS / READY（fixture） |
| `git diff --check` | PASS |
| annotation mutation gate | 脚本报告 23/23 PASS，但独立审计判定为假阳性 |
| 必需 contract metrics | FAIL，文件不存在 |

## 阻断项

### P0-1：mutation gate 违反自身硬契约并产生假绿

任务书要求每个 mutation 必须满足：正式 CLI `child_exit=1`、指定 target check 存在且 `passed=false`；`exit2/BLOCKED` 不算契约错误。

实际实现存在两项特殊改写：

1. `calibration_flag_ignored` 的真实结果为 `child_exit=0`、`target_passed=true`，脚本随后手工把 `detected` 改为 true。
2. `zero_real_candidates_blocked_not_ready` 的真实结果为 `child_exit=2`，脚本把正常 BLOCKED 状态计作 detected。

因此 `23/23` 不能作为有效机器证据，顶层 PASS 必须撤销。

### P0-2：恒定标签可伪造高一致性并进入 READY

独立调用结果：

```text
cohens_kappa([True] * 20, [True] * 20)  = 1.0
cohens_kappa([False] * 20, [False] * 20) = 1.0
```

函数注释声明该退化情形返回 0.0，但实现返回 1.0。验证器仅检查 `kappa >= 0.70`，所以无标签区分度的双标数据可能错误满足 READY。退化 κ 必须被标记为不可计算/不合格，并由正式 CLI 阻断。

### P1-1：校准禁止项没有可变输入，mutation 实际未测试任何边界

验证器把 `cal_allowed=False` 硬编码后再断言其为 false。向 store 注入 `calibration_allowed=true` 会被静默忽略，不能证明来自阶段策略、manifest 或外部输入的非法发布标志会被拒绝。需要让正式 CLI 验证一个明确、冻结且可变异的阶段策略字段，并在 true 时返回 exit 1、target false。

### P1-2：交付报告与必需 artifact 漂移

交付报告把 `docs/P13-2-evidence/human-annotation-contract-metrics.json` 列为已新增交付物，但独立检查文件不存在。必须由正式验收命令生成，并让报告引用同一次运行的真实值。

## 非阻断通过项

- 真实候选为 0 时保持 BLOCKED/exit 2，没有冒充真实人工数据。
- fixture readiness 明确标记为 `FIXTURE_PASS`，真实人工计数仍为 0。
- 常规 schema、导入、A/B 包及 P13-1 回归未发现新增失败。

## 验收决定

本阶段退回一次聚焦修复。只修复上述证据契约、退化 κ 和缺失 artifact；不得开始真实标注、概率校准或后续业务优化。
