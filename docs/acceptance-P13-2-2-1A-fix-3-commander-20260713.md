# P13-2-2-1A fix-3 Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- 上一轮 P0 的直接反例已关闭：pack/annotation 顶层 `passed`、readiness invariant、annotation meta-negative 任一非严格 `true` 时会进入 `errors` 并使 final passed 为 false。
- Orchestrator 会先生成 run_id，再把同一 run_id 传给两个 gate；当前三份正式 evidence 的 run_id 一致。
- Commander 独立执行正式 orchestrator：23/23 pack mutation、34/34 annotation mutation，两个子进程 exit 0。
- Ruff：通过。
- 三组聚焦契约测试：78 passed。
- 全量回归：302 passed，3 warnings。
- P13-1 behavior probe：PASS。
- P13-2 goldset validator：READY / passed=true。
- 三份 evidence JSON、`git diff --check`：通过。

## 阻断问题

### P0-1：Orchestrator 不验证必需 mutation / invariant 身份集合，门禁可缩减后假绿

位置：`scripts/p13_2_pack_trust_contract_metrics.py` 的逐行检查与 count consistency。

问题：实现只验证“声明数量等于当前 results 长度”和当前行格式，不验证必需 mutation 名称集合、重复项、精确数量或 readiness invariant 身份。任意未知 mutation 只要行格式正确，就可替代全部正式门禁。

Commander 独立反例：两个伪 gate 各只包含一条名为 `arbitrary_unrecognized_probe` 的 mutation，pack readiness invariants 为空；两者自行声明 `passed=true`，子进程模拟 exit 0。

结果：

```json
{
  "exit_code": 0,
  "final_passed": true,
  "pack_mutations_accepted": 1,
  "annotation_mutations_accepted": 1,
  "pack_invariants_accepted": 0,
  "mutation_name": "arbitrary_unrecognized_probe"
}
```

影响：23 类 pack mutation、34 类 annotation mutation和状态不变量可以被删除或替换，最终 evidence 仍显示 PASS；这是安全门禁覆盖收缩的确定性假阳性。

验收要求：由版本化机器契约声明精确必需集合；orchestrator 校验名称集合精确相等、无重复、数量固定、每项结果满足严格契约。至少固定当前 23 类 pack mutation、34 类 annotation mutation、2 类 pack readiness invariant、1 类 annotation readiness invariant、5 类 annotation meta-negative。新增缺一项、多一项、重复、改名、用未知项替换的端到端负例。

### P0-2：SHA 在复制前计算，复制后不复核，证据可被 TOCTOU 篡改后继续绿灯

位置：`scripts/p13_2_pack_trust_contract_metrics.py` 的 artifact SHA snapshot 与 gate evidence copy。

问题：脚本先对临时 gate 文件计算 SHA，之后再次从路径读取并用 `write_text` 复制；两次读取之间文件可变化。目标文件写完后未复算 SHA，也没有真正使用临时文件 + `os.replace` 的原子发布。

Commander 独立反例：在 pack gate SHA 计算完成后、复制之前，把临时 gate 的 `passed` 改为 false。

结果：

```json
{
  "exit_code": 0,
  "final_passed": true,
  "copied_gate_passed": false,
  "tamper_marker": true,
  "recorded_sha_matches_copied_artifact": false
}
```

影响：最终 metrics 可以记录旧 SHA 和 `passed=true`，实际落盘 gate 却是另一份 `passed=false` 内容；三份机器证据内部不一致仍可绿灯。

验收要求：每个 gate 只读取一次不可变 bytes snapshot；解析、验证、SHA 和目标写入必须基于同一份 bytes。目标使用同目录临时文件、flush/fsync、`os.replace` 发布，发布后重新读取并核对 SHA、run_id 和 passed。最终 metrics 必须最后发布，并以其 run_id 作为 commit marker；任一不一致 exit 1 / passed=false。

### P1-1：新增测试复制验证逻辑，没有执行真实 `main()`，且遗漏任务书强制负例

位置：`tests/test_p13_2_pack_trust_metrics_contract.py`。

问题：测试辅助函数重新手写了一套 `_check_*` 和 `final_passed = len(errors) == 0`，没有让真实 orchestrator `main()`消费伪 gate 输出。其正例明确允许 1 条 pack mutation、1 条 annotation mutation和 0 条 invariant。任务书要求的“子命令非零但JSON伪绿、SHA前后变化、旧新 evidence 混用”没有进入真实主路径测试。

影响：测试可以全绿而生产 orchestrator 仍存在 cardinality 和 SHA 假阳性；本次 13 项测试没有证明交付报告声称的完整证据闭环。

验收要求：测试必须调用真实 `main()`或可注入依赖的唯一生产验证函数，不得复制 final passed 逻辑；覆盖 P0-1、P0-2 以及 fix-3 任务书全部强制元负例。

## 非阻断观察项

- gate JSON 目前没有任务书要求的自身 `command`、`exit_code` 和 schema version；只有最终 metrics 记录子进程 exit。fix-4 应一并补齐并由 orchestrator 核对，避免继续形成报告与 artifact 漂移。
- `orchestrator_started_at` 已存在，但建议补 `orchestrator_finished_at`，不要让消费者把通用 `generated_at` 猜作完成时间。

## 问题统计归类

- 验证脚本假阳性 / 关键覆盖未参与顶层 passed：P0，2 项复发。
- 契约测试缺少真实负例：P1，1 项复发。
- 交付报告与实现漂移：报告称“原子拷贝”和完整 12 类元负例，实际均未成立。

## 复验要求

只复验 evidence orchestrator、两个 gate 的 evidence 元数据与对应契约测试；不得扩展到业务导入、数据库、API、前端或 P13-2-2-2。

