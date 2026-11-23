# DeepSeek 返工指令：P13-2-2-1 mutation 假阳性与退化 κ 修复

## 目标

修复 Commander 在 2026-07-12 独立验收确认的四个阻断项，使人工标注工具的机器门禁不能假绿。本次仅为 P13-2-2-1 fix，不进入 P13-2-2-2。

## 允许修改

- `signal_miner/evaluation/human_annotation.py`
- `scripts/p13_2_validate_human_annotations.py`
- `scripts/p13_2_annotation_mutation_gate.py`
- `tests/test_p13_2_human_annotation_contract.py`
- 为阶段策略输入所必需的 P13-2 fixture/schema 文件
- `docs/P13-2-evidence/`、P13-2 操作文档及本次交付报告

禁止修改生产 pipeline、LLM/Embedding、去重聚类、数据库/API/前端、P13-1/P13-2-1 契约，也禁止生成或伪造真实人工标签。

## 必修项

### 1. 删除 mutation 特殊放行

- 所有计入 mutation 分母的案例统一使用同一判定函数：
  - `child_exit == 1`
  - target check 存在
  - `target_check.passed is false`
- 禁止运行后反转/覆盖 `detected`。
- 禁止把 `exit 0`、`exit 2`、异常或缺失 check 计作 detected。
- `zero_real_candidates -> exit2/BLOCKED` 改为独立 readiness invariant，不计入 mutation 捕获数；但其结果仍须写入 metrics，并要求 exit 2。

### 2. 让 calibration mutation 真实命中正式边界

- 不得用 `cal_allowed=False` 常量自证安全。
- 为 validator 增加明确的冻结阶段策略输入或等价单一真源，合法 fixture 值为 `calibration_allowed=false`。
- 将其变异为 true 后，正式 validator 必须 exit 1，`calibration_not_allowed` 必须存在且 `passed=false`。
- 缺失、类型错误、未知值也必须失败；不得从 store 中静默忽略后算通过。

### 3. 阻断退化 κ

- 当 A/B 的 `has_signals` 标签没有类别变化、导致 Cohen's κ 分母退化时，不得返回 1.0 并满足 READY。
- 输出必须明确区分“不可计算/退化”与正常数值；validator 将其判为 `BLOCKED_GUIDELINE_REVISION` 或更明确的非 READY 状态。
- 增加至少两个正式 CLI mutation：全 true、全 false。两者均须 exit 1，指定 target check=false。
- 保留正常非退化高 κ、低 κ、样本不足的测试。

### 4. 补齐真实机器证据

- 正式生成 `docs/P13-2-evidence/human-annotation-contract-metrics.json`。
- metrics 必须记录每条 mutation 的 exit、target check、target passed、detected，以及独立 readiness invariant。
- 顶层 `passed` 必须由逐项真实结果复算；缺文件、缺 check、数量不符或矛盾 observation 均非 0。
- 交付报告中的测试数、mutation 数、状态与 JSON 必须来自同一次运行，不得手写漂移。

## 强制负例

在原有有效负例基础上，至少证明：

1. calibration policy=true：exit 1、`calibration_not_allowed=false`。
2. calibration policy缺失或类型错误：exit 1、明确 target=false。
3. A/B 全 true：exit 1、agreement/readiness target=false。
4. A/B 全 false：exit 1、agreement/readiness target=false。
5. 任意 mutation 子进程 exit 0 时，聚合器整体失败。
6. 任意 mutation 子进程 exit 2 时，聚合器整体失败。
7. target check缺失或仍为 true 时，聚合器整体失败。
8. 零真实候选独立输出 exit 2/BLOCKED，但不增加 mutation detected_count。
9. 删除 contract metrics 后，交付聚合命令失败。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/human-annotation-contract-metrics.json >/dev/null
git diff --check
```

通过条件：

- 所有计数内 mutation 严格满足 exit 1 + target存在 + target false。
- readiness invariant 单列，零真实候选为 exit 2/BLOCKED。
- 退化 κ 不得使状态 READY。
- fixture 仍为 `FIXTURE_PASS`；真实计数仍为 0；`calibration_allowed=false`。
- 测试和 gate 使用临时目录，除本次明确输出外不污染冻结 artifact。

## 交付物

1. `docs/acceptance-P13-2-2-1-delivery-fix-20260712.md`
2. `docs/P13-2-evidence/human-annotation-contract-metrics.json`
3. `docs/P13-2-evidence/human-annotation-mutation-gate.json`
4. `docs/P13-2-evidence/human-annotation-readiness.json`

交付报告必须逐项回应 Commander 的 P0-1、P0-2、P1-1、P1-2，并列出命令真实退出码。

## 完成边界

本 fix 通过只代表 P13-2-2-1 工具可信。真实授权候选仍为 0 时，P13-2-2-2、P13-2-3 和 P13-2-4继续冻结。
