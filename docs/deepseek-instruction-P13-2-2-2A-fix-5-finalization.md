# DeepSeek 执行指令：P13-2-2-2A fix-5 最终收口与低返工交付

指令日期：2026-07-15

优先级：P0

状态：当前唯一有效的 fix-5 指令。本文件替代尚未完成交付的 `docs/deepseek-instruction-P13-2-2-2A-fix-5.md`；不得升级为 fix-6，也不得进入 P13-2-2-2B。

## 任务目标

本轮不是重新设计 readiness，也不是增加新能力。只完成以下闭环：

1. 精确证明源 candidate 缺失 `near_duplicate_group_id` 时正式主路径必定失败；
2. 精确证明非空 `near_duplicate_group_id` 跨 split 时正式主路径必定失败；
3. 证明 fix-4 已通过能力没有回退；
4. 生成与当前代码、测试、正式 evidence 完全一致的 fix-5 交付报告。

## Commander 当前预检事实

以下只代表“存在候选实现”，不代表阶段已验收：

| 项目 | 当前事实 |
| --- | --- |
| readiness 脚本 SHA-256 | `b036663c4fde458c0fcbf0fdaaa7cdaa80f0a0ab355017d84bf2ef60a945cd5f` |
| 聚焦测试 SHA-256 | `7819bcd54a88f0a4ddf3c30207cb8633f2b16f7c754515d6906dda45878af0db` |
| focused Ruff | exit 0 |
| focused pytest | 44 passed |
| fix-5 交付报告 | 缺失 |

当前脚本已经出现 `has_near_duplicate_group_id` 和 near-duplicate 跨 split 检查。除非下述冻结门禁失败，不得重写这些实现。

## 冻结验收契约

本轮验收范围到此为止。Commander 不再为 fix-5 增加新的业务要求。

| 编号 | 场景 | 必须结果 | 必须观测 |
| --- | --- | --- | --- |
| P1 | 完整受控签名输入 | `exit0 / READY_FOR_HUMAN_ANNOTATION / passed=true` | `group_isolation=true`、`missing_group_rows=[]`、`cross_split_groups=[]` |
| N1 | 删除一个源 candidate 的 `near_duplicate_group_id` 键 | `exit1 / FAILED_INVALID_INPUT / passed=false` | `group_isolation=false`，`missing_group_rows`必须包含被删字段的准确 `sample_id` |
| N2 | development 与 test 使用同一非空 `near_duplicate_group_id=nd_group_shared_001` | `exit1 / FAILED_INVALID_INPUT / passed=false` | `group_isolation=false`，`cross_split_groups`必须明确包含字段名、group值、development和test |
| R1 | 删除一个candidate的session或conversation | `exit1 / FAILED_INVALID_INPUT` | `group_isolation=false` |
| R2 | naive governance datetime | `exit1 / FAILED_INVALID_INPUT` | `annotation_governance=false`，不得出现`unexpected`或空`check_passed` |
| R3 | governance、roles、rejections分别变化 | 保持READY | 每次变化后的`batch_id`必须与基线不同 |
| D1 | 当前正式环境没有真实授权输入 | `exit2 / BLOCKED_INPUT_REQUIRED / passed=false` | `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false` |

状态、返回值和报告内 `exit_code` 必须一致：

```python
assert returned_exit_code == report["exit_code"]
```

任何负例都必须同时断言顶层 `passed`、`status`、`exit_code`、目标 `check_passed` 和目标 observation。只断言“非零退出”或“列表非空”不算完成。

## 允许修改范围

- `tests/test_p13_2_real_annotation_launch_readiness.py`
- `scripts/p13_2_real_annotation_launch_readiness.py`，仅当冻结契约中的某个用例实际失败时允许最小修改
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`
- `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
- `docs/acceptance-P13-2-2-2A-delivery-fix-5-20260715.md`

## 禁止修改范围

- 不得修改 P13-2-2-1A 信任链实现或已验收报告；
- 不得修改候选数量、split比例、双标门槛、签名策略或batch组件集合；
- 不得新增 fixture 后门、测试密钥生产兜底、内存 override 正式READY路径；
- 不得生成或伪造真实人工标签；
- 不得进入 P13-2-2-2B、主动学习、置信度拟合、P13-3或前端概率发布；
- 不得为了让测试通过而弱化已有check、删除回归测试或改变正式默认`exit2`。

## 开发方法与要求

### 1. 先补精确断言，不先改生产代码

现有两个测试必须强化：

#### `test_ndg_field_missing_single_candidate`

至少断言：

```python
assert exit_code == report["exit_code"] == 1
assert report["status"] == "FAILED_INVALID_INPUT"
assert report["passed"] is False
assert report["check_passed"]["group_isolation"] is False
assert "smp_development_0000" in report["checks"]["group_isolation"]["missing_group_rows"]
```

#### `test_ndg_cross_split`

至少断言：

```python
assert exit_code == report["exit_code"] == 1
assert report["status"] == "FAILED_INVALID_INPUT"
assert report["passed"] is False
assert report["check_passed"]["group_isolation"] is False
```

并对 `cross_split_groups` 做内容断言，必须同时证明：

- 字段是 `near_duplicate_group_id`；
- 值是 `nd_group_shared_001`；
- splits包含`development`和`test`。

不得只写 `len(cross_split_groups) >= 1`。

### 2. READY正例必须证明无假阻断

READY测试除已有断言外，必须补充：

```python
assert exit_code == report["exit_code"] == 0
assert report["check_passed"]["group_isolation"] is True
assert report["checks"]["group_isolation"]["missing_group_rows"] == []
assert report["checks"]["group_isolation"]["cross_split_groups"] == []
```

受控正例允许 `near_duplicate_group_id=None` 表示“已明确声明无近重复组”；源键本身必须存在。不得把“源字段缺失”和“显式null”归并为同一状态。

### 3. 必须攻击正式唯一主路径

关键用例必须调用 `scripts/p13_2_real_annotation_launch_readiness.py` 中生产使用的 `main()`，不得复制一套判定逻辑，也不得只调用 `_check_group_isolation()` 后声称正式路径通过。

### 4. 失败时停止提交

如果任一冻结契约失败：

- 只修复该失败；
- 从第一条门禁重新运行全部命令；
- 在全部通过前不得写“已完成”；
- 无法完成时应报告`BLOCKED`、失败命令、退出码和最后20行输出，不得提交绿色交付报告。

## 验收命令与固定顺序

所有命令从项目根目录执行，并记录真实退出码。不得用旧日志、旧测试数或手工推测代替。

### 1. 三个核心用例

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py -k "full_signed_packs_ready or ndg_field_missing_single_candidate or ndg_cross_split"
```

预期：3 passed，exit 0。

### 2. 静态检查

```bash
.venv/bin/ruff check scripts/p13_2_real_annotation_launch_readiness.py tests/test_p13_2_real_annotation_launch_readiness.py
```

预期：exit 0。

### 3. 聚焦回归

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
```

预期：不少于当前44项，全部通过，exit 0。报告必须填写实际数量，不能预写44。

### 4. 全量回归

```bash
.venv/bin/python -m pytest -o addopts= -q
```

预期：全部通过，exit 0。报告必须填写同次命令的实际passed与warnings。

### 5. 正式无输入默认行为

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py
```

预期：`BLOCKED_INPUT_REQUIRED`，exit 2。exit 2是本场景的通过结果，不得写成命令失败，也不得改成exit 0。

### 6. 正式evidence只读校验

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

预期：`verify-evidence: PASS`，exit 0。

### 7. diff检查

```bash
git diff --check
```

预期：exit 0。

### 8. 最终SHA

所有命令完成且不再修改文件后执行：

```bash
shasum -a 256 scripts/p13_2_real_annotation_launch_readiness.py tests/test_p13_2_real_annotation_launch_readiness.py docs/P13-2-evidence/real-annotation-launch-readiness.json docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256
```

然后在 `docs/P13-2-evidence/` 目录验证sidecar：

```bash
shasum -a 256 -c real-annotation-launch-readiness.json.sha256
```

预期：`real-annotation-launch-readiness.json: OK`。

写入交付报告后不得再次修改脚本、测试或evidence；如果修改，所有门禁和SHA必须重跑。

## 提交资格门禁

只有以下条件全部满足，才允许向用户回复“已完成，进行验收”：

- fix-5交付报告文件真实存在；
- 脚本或测试已经形成满足精确断言的当前内容；
- 三个核心用例、Ruff、聚焦、全量、evidence verifier、diff check全部达到预期；
- 正式默认无输入真实返回exit 2；
- 报告中的测试数、warnings、状态、退出码和SHA来自最后一次实际运行；
- 报告明确区分“受控输入READY”和“真实输入仍缺失”；
- 报告没有声称人工标注、校准或P13-2-2-2B已完成。

缺少任何一项都只能回复`未完成/BLOCKED`，不能回复“完成”。

## 交付报告

必须新增：

```text
docs/acceptance-P13-2-2-2A-delivery-fix-5-20260715.md
```

报告至少包含：

1. 修改文件清单与最终SHA；
2. 冻结契约P1、N1、N2、R1、R2、R3、D1逐项结果；
3. N1的准确`missing_group_rows`；
4. N2的准确`cross_split_groups`；
5. 每条验收命令、退出码、实际测试数和warnings；
6. 正式默认`BLOCKED_INPUT_REQUIRED/exit2`证据；
7. 未覆盖风险；若风险会导致READY假绿，不能声明完成；
8. 明确声明“未进入P13-2-2-2B，未产生真实人工标签，未进行校准”。

## 交付报告模板

```markdown
# P13-2-2-2A fix-5 交付报告

结论：完成 / BLOCKED

## 修改文件与SHA

## 冻结契约结果

| 编号 | 状态/exit | 顶层passed | 目标check | 关键observation | 结果 |
| --- | --- | --- | --- | --- | --- |

## 命令证据

| 命令 | exit | 实际输出摘要 | 结果 |
| --- | ---: | --- | --- |

## 正式环境边界

## 未覆盖风险

## 阶段边界声明
```

## 完成边界

fix-5通过只表示readiness能够安全判断是否具备启动真实人工标注的条件。当前真实授权候选仍为0时，正式状态必须继续是`BLOCKED_INPUT_REQUIRED/exit2`。Commander独立复验通过前，不得进入下一阶段。
