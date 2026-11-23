# P13-2-2-2A fix Commander 独立验收报告

验收日期：2026-07-14

结论：**不通过，需要 fix-2；当前业务状态继续为 `BLOCKED_INPUT_REQUIRED`，不得进入 P13-2-2-2B。**

本轮关闭了上一轮的候选 count 伪报、授权缺字段不阻断、顶层 BLOCKED 状态不稳定和当前 artifact/sidecar 不一致。但 READY 主路径仍未接入 P13-2-2-1A 信任链，并可在没有任何有效任务包的情况下确定性假绿。

## 已通过项

- 正式零输入运行：`BLOCKED_INPUT_REQUIRED / passed=false / exit2`。
- 声明100、实际99的候选计数伪报现在为 `FAILED_INVALID_INPUT / exit1`。
- 授权字段缺失/类型错误会使 `real_candidates=false`。
- test blind禁用字段泄漏现在为 `FAILED_INVALID_INPUT / exit1`。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`保持有效。
- 当前 readiness JSON 实际 SHA 与 sidecar均为 `a844c819943db671695dcfb3b908b5b513e3153e0034dd86e329254968fb90b8`。
- Ruff：通过。
- readiness聚焦测试：61 passed。
- 全量回归：389 tests，全部通过，3 warnings。
- `git diff --check`：通过。

## 阻断问题

### P0-1：READY 完全未验证 dataset/pack manifest、签名和 task hash

位置：`scripts/p13_2_real_annotation_launch_readiness.py:954-1097, 1102-1159, 1217-1362`。

问题：launch config没有 `dataset_manifest_path`、`pack_manifest_path`、`task_dir`或签名验证输入；`assess_readiness()`没有 pack trust check，也没有调用已验收的 `signal_miner.evaluation.pack_trust.verify_manifest_file()`。`dataset_id`、`batch_id`、`dataset_manifest_sha256`、`pack_manifest_sha256`在 READY 时仍被硬编码为null。

Commander通过正式CLI提供100条候选、角色/split/governance和生产密钥，但完全不提供dataset manifest、pack manifest或任何签名pack，程序仍返回：

```text
cli_exit=0
P13-2-2-2A readiness: READY_FOR_HUMAN_ANNOTATION
passed: True
```

影响：P13-2-2-1A建立的外部信任根没有进入本阶段READY判定；签名、dataset hash、task hash或精确文件集合都可以不存在，更不可能阻断篡改。

### P0-2：空任务包、无关split和自报双标/访问边界均可通过

位置：`scripts/p13_2_real_annotation_launch_readiness.py:521-641, 688-864`。

Commander同一正式CLI反例同时包含：

```json
{
  "signed_pack_count": 0,
  "actual_test_task_count": 0,
  "candidate_ids_represented_in_splits": 0,
  "allowed_access_matches_roles": false
}
```

仍然READY的原因：

- `test_blind_count`计算JSON文件数量，不计算唯一test任务数；25个空对象即可满足25。
- split只检查三个字符串列表的长度和交集，不要求ID来自候选集，也不核对content/session/near-duplicate group。
- `double_label_plan_count`和`total_candidate_count`直接信任roles配置，没有从签名任务分配重算。
- A/B访问隔离只信任 `a_b_access_isolation=true` 自报布尔值，没有检查A/B pack内容、slot、label字段或访问配置。

影响：READY表示不了“真实任务包可以安全发给人工标注员”。

### P0-3：候选来源、rejections与治理字段仍为弱校验

位置：`scripts/p13_2_real_annotation_launch_readiness.py:66-100, 181-430, 869-949`。

Commander反例中：

- `captured_at="not-a-timestamp"`；
- export自报 `rejected_count=999`，实际 `real_rejections=[]`；
- governance时间仅为 `a < b < c`，不是ISO-8601；
- `allowed_access_role_ids=["nobody"]`，与A/B/裁决角色完全不匹配；
- 未提供任务书要求的source adapter/version。

以上均未阻断READY。实现注释声称real_rejections参与count conservation，但代码只读取列表长度，不执行任何守恒或原因分布对账；治理时间使用字符串字典序比较，没有解析时间。

### P0-4：N11与N16再次没有按返修指令进入生产判定主路径

位置：`tests/test_p13_2_real_annotation_launch_readiness.py:1-35, 556-566, 672-718, 864-905`。

- 测试文件头声明N11覆盖pack signature/dataset hash/task hash篡改，实际 `test_n11_missing_production_key` 仍只是“缺生产密钥”。
- N16只在测试里计算“篡改后SHA与旧sidecar不同”，没有调用独立生产 verifier，也没有证明其exit1。
- 正向 `test_launch_config_consumed` 明确在没有manifest、签名和真实task pack的情况下要求READY，反而把P0-1假绿固化为正确行为。
- 生产 `main()`保留 `_test_mode=True` 即可在 `environment="production"` 使用任意内存override的旁路，未达到“production不能用override绕过文件与信任链”的要求。

因此61项全绿仍是“测试与弱实现共同同意”，不是信任链已闭环。

### P1-1：交付报告仍有同文件SHA漂移

交付报告前文三方对账记录正确值 `a844c819...`，但“机器证据 / Sidecar”代码块仍保留旧值：

```text
d93050044393aa0008970cd586bc65235c7898bd598d8eee5ad6637dc76ab9a5
```

当前实际JSON与sidecar均为 `a844c819...`。根据Commander归档规则，任何交付/hand-off文档中的旧SHA都属于证据漂移，不能宣告P1-1完全关闭。

## Commander 正式 CLI 反例

本次反例不是调用内部check，也不是复制判定逻辑，而是启动正式脚本CLI。输入同时具备：

- 100行通过当前弱schema的候选；
- 生产环境变量密钥；
- 三角色配置；
- 50/25/25但与候选零交集的split；
- 25个空JSON文件，实际test task为0；
- 无dataset manifest、pack manifest、签名或task hash；
- rejections声明999、实际0；
- 非法治理时间和不匹配访问角色。

实际结果：`READY_FOR_HUMAN_ANNOTATION / passed=true / exit0`。

期望结果：至少因缺少信任链为 `BLOCKED_INPUT_REQUIRED/exit2`；若相应文件已提供但内容无效，则为 `FAILED_INVALID_INPUT/exit1`。不得READY。

## 问题统计归类

- 验证脚本假阳性 / 关键check未参与passed：P0，再次复发。
- 测试没有执行所声明负例、正例反而固化假绿：P0，再次复发。
- Markdown报告与最终artifact SHA漂移：P1，再次复发。

## 复验要求

只复验 P13-2-2-2A READY主路径的1A信任链复用、任务/split/双标/访问重算、来源与治理严格校验、N11/N16真实生产负例及报告SHA。不得修改P13-2-2-1A现有信任链实现，不得生成真实人工标签，不得进入P13-2-2-2B或下游阶段。

