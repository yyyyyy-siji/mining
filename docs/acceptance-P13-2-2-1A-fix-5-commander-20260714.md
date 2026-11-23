# P13-2-2-1A fix-5 Commander 独立验收报告

验收日期：2026-07-14

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- fix-4 的 23/34/2/1/5 exact-set 和 immutable bytes snapshot 保持有效。
- Pre-commit gate tamper 会被 reverify 阻断并写入非绿色状态。
- Final COMMITTED metrics 发布失败会使主流程 exit 1，不再打印 PASS。
- 畸形顶层、results、row、bool和时间字段均结构化失败，不再泄漏 KeyError/TypeError。
- Gate phase、command、contract schema version和exit code已进入严格校验。
- 独立 committed-evidence verifier 能发现提交后的单文件篡改。
- Fake runner测试已全部注入 `tmp_path`；Commander在聚焦测试前后独立计算正式三文件SHA，完全不变。
- Ruff：通过。
- 三组聚焦契约测试：96 passed（metrics 31 + pack trust 22 + annotation 43）。
- 全量回归：320 passed，3 warnings。
- Commander独立执行正式 orchestrator：23/23 pack、34/34 annotation，exit 0。
- 正式 committed-evidence verifier：PASS / exit 0。
- P13-1 behavior probe：PASS；P13-2 goldset validator：READY / passed=true。
- JSON解析和 `git diff --check`：通过。

## 阻断问题

### P0-1：RUNNING marker 发布错误被丢弃，状态机可在未进入 RUNNING 时继续执行并成功

位置：`scripts/p13_2_pack_trust_contract_metrics.py:431-501`。

问题：`_write_running_marker()` 调用 `_publish_atomic()`，但没有检查其返回的 errors。由于 `_publish_atomic()` 用返回列表表示失败而不是抛异常，`main()` 外层的 try/except不会发现失败，仍然启动两个 gate。

Commander独立主路径反例：仅让第一次 `_publish_atomic`（RUNNING marker）返回 `forced RUNNING marker publish failure`，后续写入正常。

```json
{
  "exit_code": 0,
  "gate_calls_after_running_marker_failure": 2,
  "final_status": "COMMITTED",
  "final_passed": true,
  "running_publish_error_was_ignored": true
}
```

影响：交付报告声明“RUNNING marker在任何gate运行前原子发布”，实际不成立。长达约30秒的真实gate运行期间，磁盘可能继续暴露上一轮COMMITTED绿色结果，自动化调用方无法从evidence文件识别新任务正在运行。

验收要求：`_write_running_marker` 必须返回并强制检查errors，或遇到非空errors立即抛受控异常；RUNNING提交未成功时必须 exit 1 且 gate call count=0。只有 RUNNING marker 成功落盘后，本次run才算开始。

### P0-2：Marker持续写失败时旧绿色结果保留，控制台却声称“no green metrics left”

位置：`_write_failed_marker()`、`_finalize_failed()`和 `_print_summary()`。

问题：`_write_failed_marker()` 使用 `contextlib.suppress(Exception)`并丢弃 `_publish_atomic()` errors；`_finalize_failed()`不知道 FAILED marker是否真正写入，却无条件让summary打印“FAILED (no green metrics left)”。

Commander独立反例：预置旧 `COMMITTED/passed=true/run_id=old-green-run`，强制所有metrics marker写入返回错误，gate artifact写入仍正常。

```json
{
  "exit_code": 1,
  "gate_calls": 2,
  "remaining_run_id": "old-green-run",
  "remaining_status": "COMMITTED",
  "remaining_passed": true
}
```

实际控制台同时输出：

```text
status: FAILED (no green metrics left)
```

影响：机器文件和控制台陈述直接矛盾；旧绿色evidence仍存在，属于高频“报告/状态与真实落盘不一致”。

验收要求：FAILED marker API必须返回成功/失败和errors。只有重新读取并确认本次run_id、status=FAILED、passed=false后，才能打印“no green metrics left”。若FAILED marker也无法发布，必须明确打印 `FAILED_MARKER_WRITE_FAILED`，不得宣称旧绿已清除；最终始终exit 1。

## 非阻断观察项

- `CURRENT_NAME`、`RUNS_SUBDIR` 常量当前未被使用，也没有 `current.json` 或 run-specific目录。fix-5任务书将该结构列为推荐而非强制，因此本次不单独阻断；交付报告后续不要把固定三文件实现描述成已存在的current commit目录协议。
- 正式 metrics 的 `finished_at` 在gate结束后生成，早于artifact commit/verifier完成时间。后续可改为 `gates_finished_at`并在最终成功后生成真正的 `committed_at`，本阶段不阻断。

## 问题统计归类

- 验证脚本假阳性 / 关键发布错误未进入顶层返回码：P0，再次复发。
- 状态文字与真实落盘结果不一致：P0，再次复发。
- 契约测试缺少真实负例：未覆盖 RUNNING marker发布失败和FAILED marker发布失败。

## 复验要求

只复验 RUNNING/FAILED marker API、错误传播、gate call count和控制台陈述。不得重写orchestrator、修改23/34/2/1/5契约、业务gate或进入P13-2-2-2。

