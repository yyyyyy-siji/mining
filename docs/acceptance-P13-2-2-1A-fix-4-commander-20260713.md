# P13-2-2-1A fix-4 Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- 23/34/2/1/5 版本化精确集合已建立；缺失、多余、重复、未知替换和上一轮 1/1 coverage shrink 反例均被拒绝。
- Gate 解析、校验、SHA 和发布使用同一份 bytes snapshot。
- `_publish_atomic` 已使用同目录临时文件、fsync、`os.replace` 和单次发布后的 SHA 复核。
- Commander 独立执行 Ruff：通过。
- 三组聚焦契约测试：83 passed。
- 全量回归：307 passed，3 warnings。
- Commander 独立执行正式 orchestrator：23/23 pack mutation、34/34 annotation mutation、2/2 + 1/1 invariant、5/5 meta-negative，exit 0。
- P13-1 behavior probe：PASS；P13-2 goldset validator：READY / passed=true。
- 正式 orchestrator 重跑后的两个 gate artifact SHA 与 metrics 记录一致。

## 阻断问题

### P0-1：Gate 发布后、metrics commit 前被篡改，仍发布绿色 commit marker

位置：`scripts/p13_2_pack_trust_contract_metrics.py:323-385`。

问题：每个 gate 的 `_publish_atomic` 只在自身返回前复核一次。两个 gate 发布完成后，metrics commit 前没有再次读取并验证已发布 artifact；因此第一个 gate 在 `_publish_atomic` 返回后被改动，final passed 仍使用旧 snapshot 和旧 SHA。

Commander 主路径反例：在 pack gate `_publish_atomic` 正常返回后、metrics 发布前，把已发布 gate 的 `passed` 改为 false。

```json
{
  "exit": 0,
  "final_passed": true,
  "gate_passed": false,
  "sha_matches": false
}
```

交付测试 MN16 并未阻断该问题：它先要求 orchestrator exit 0，再在 orchestrator 完成后篡改文件，最后只断言 SHA 不同。交付报告也明确记录 `exit 0 → tamper`，却将其描述为“sha race detected”。

影响：正式 metrics 可以作为绿色 commit marker落盘，而它引用的 gate 已经是另一份失败内容；P0-2 的证据一致性目标仍未实现。

验收要求：在 final metrics commit 前，对两个已发布 gate 重新读取，严格复核 run_id、contract SHA、passed 和 artifact SHA；测试通过生产注入点在 gate publish 与 metrics commit 之间篡改，必须 exit 1、不得留下本次绿色 metrics。另提供独立 committed-evidence verifier，任何提交后的篡改都必须使 verifier exit 1。

### P0-2：Final metrics 发布失败仍 exit 0 / 打印 PASS

位置：`scripts/p13_2_pack_trust_contract_metrics.py:380-398`。

问题：`final_passed` 在 metrics 发布前计算；`errs_metric` 只追加到 errors，既不重算 final passed，也不改变返回码。

Commander 主路径反例：强制 final metrics 的 `_publish_atomic` 返回 `forced metrics publish failure`。

```json
{
  "exit": 0,
  "metrics_exists": false
}
```

控制台同时打印 `Orchestrator: PASS` 和 `ERROR: forced metrics publish failure`。

影响：没有 commit marker 的失败交付会被自动化调用方当作成功，是确定性机器门禁假阳性。

验收要求：任何 gate/metrics publish、fsync、replace、post-verify 错误都必须 exit 1；PASS 文本只能在最终 commit 成功且重新验证后输出。返回码必须基于最终提交结果，而不是提交前的业务检查结果。

### P0-3：畸形 evidence 触发未捕获异常，旧绿色 metrics 保留

位置：`scripts/p13_2_pack_trust_contract_metrics.py:255-275` 等直接索引列表行的代码。

问题：例如 mutation 行缺少 `mutation` 时，`[r["mutation"] for r in pt_results]` 抛出 `KeyError`。主流程只有 `finally`，没有统一失败状态闭环；旧 OUT 不会被替换为本次 failed/running marker。

Commander 主路径反例：预置上一轮 `passed=true/run_id=stale-green` metrics，再输入缺 `mutation` 的行。

```json
{
  "exception": "KeyError",
  "stale_metrics_passed": true,
  "stale_run_id": "stale-green"
}
```

影响：本次运行失败后，操作者或后续程序仍可能读取旧绿色结果并误认为本次通过。

验收要求：启动时先原子写入本次 run_id 的非绿色 RUNNING marker；所有外部 payload 先做容器/行/字段严格类型校验，禁止未捕获 KeyError/TypeError。任何 Exception 必须 best-effort 原子写本次 `passed=false/status=FAILED/errors` 并 exit 1；旧绿色 marker不能代表本次运行。

### P0-4：契约测试把 fake runner 结果写入正式 evidence，制造未运行真实 gate 的绿色证据

位置：`tests/test_p13_2_pack_trust_metrics_contract.py`。

问题：测试调用真实 main，但没有把 `EVIDENCE_DIR/OUT` 注入 `tmp_path`。每个 fake runner 用例都会覆盖 `docs/P13-2-evidence`；最后的 `test_restore_evidence` 仍使用 `_make_runner()` fake 数据，而不是真实 gate。

Commander 证据：聚焦/全量测试结束后，正式 evidence 的两个 gate `generated_at` 只相差约 0.0001 秒，内容是测试 helper 合成的统一五字段 mutation 行；metrics 为 `passed=true`，但真实 23/34 gate 根本没有运行。Commander 已随后重跑正式 orchestrator，恢复真实 evidence。

影响：仅执行 pytest 就能生成看似完整、run_id/SHA一致的绿色机器证据，破坏 evidence 的来源真实性。

验收要求：所有测试必须将 evidence store、OUT 和 run directory注入 pytest `tmp_path`；增加正式 evidence 三文件 SHA 前后不变断言；删除 fake “restore evidence”测试。只有正式 CLI 可以更新 `docs/P13-2-evidence`。

## P1 问题

### P1-1：Gate 元数据声明存在但未严格校验

`_validate_gate_payload` 只校验 contract SHA、run_id 和时间，不校验 `contract_schema_version`、`phase`、`command`。Commander 将两个 gate 的三项都改成错误值，主流程仍 exit 0 / passed=true。

验收要求：两个 gate 的 schema version、phase、command、exit_code均须严格类型和值匹配；naive timezone、错误容器类型、缺字段和 null都必须结构化失败而不是异常。

### P1-2：交付报告与机器结果漂移

- 报告写全量 306 passed，Commander 隔离重跑为 307 passed。
- 报告声称 MN16 会阻断 SHA race，实际测试要求 orchestrator先 exit 0，仅证明事后 SHA 不同。
- 报告称 16 类元负例，实际 MN14 是正常 roundtrip 正例，MN13 是 contract SHA mismatch，不是注释声明的 snapshot TOCTOU。

## 问题统计归类

- 验证脚本假阳性 / 失败状态未进入最终返回码：P0，3 项复发。
- 测试污染正式证据 / 伪证据可冒充真实运行：P0，1 项。
- 契约字段未完整验证：P1，1 项。
- 交付报告与代码/机器结果漂移：P1，再次复发。

## 复验要求

只复验 orchestrator 提交协议、committed-evidence verifier、失败 marker、测试隔离与 gate 元数据；不得修改 pack trust、annotation 业务规则或进入 P13-2-2-2。

