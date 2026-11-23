# P13-2-2-1A fix-6 交付报告

## 结论

fix-6 已完成，关闭 fix-5 Commander 验收报告中的两个 P0 marker 错误传播拦截点：

- **P0-1 关闭**：`_write_running_marker` 现在返回 `MarkerWriteResult`，`main()` 强制检查 `.ok`。RUNNING 发布或 readback 失败 → exit 1、`gate_calls=0`、stderr 含 `RUNNING_MARKER_WRITE_FAILED`、明确文本 "this run did not start"。
- **P0-2 关闭**：`_write_failed_marker` 也返回 `MarkerWriteResult`。`_print_summary` 根据 `failed_marker_written` 真实值决定文本：只有 FAILED marker 真正落盘 readback 成功才打印 "no green metrics left"；否则打印 `FAILED_MARKER_WRITE_FAILED` 并明确"on-disk marker may be from a previous run"。

fix-5 已有效的全部能力（exact-set、commit 前再验证、metrics publish 错误返回码、畸形输入闭环、strict metadata、测试隔离、committed-evidence verifier）完全保留，未做任何改动。

## 修改文件

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `scripts/p13_2_pack_trust_contract_metrics.py` | 局部修改 | 新增 `MarkerWriteResult` 契约、`_publish_marker_with_readback`、`_fail_and_summarize`；改写 `_write_running_marker` / `_write_failed_marker` 返回值；`main()` 强制检查 RUNNING 结果并支持 `_gate_state` 注入；`_print_summary` 接受 `failed_marker_written` |
| `tests/test_p13_2_pack_trust_metrics_contract.py` | 新增类 | `TestFix6MarkerNegatives`（8 项真实主路径负例 + 正例） |
| `docs/P13-2-evidence/pack-trust-contract-metrics.json` | 重新生成 | status=COMMITTED, passed=true（未变） |

未修改：`signal_miner/evaluation/p13_2_gate_contract.py`、两个 mutation gate 脚本、committed-evidence verifier 的既有校验语义、pack trust / annotation 业务规则、pipeline / 数据库 / API / 前端。

## MarkerWriteResult 契约

```python
@dataclass(frozen=True)
class MarkerWriteResult:
    ok: bool
    status: str          # "RUNNING" or "FAILED"
    run_id: str
    errors: tuple[str, ...]
```

`ok=True` 的必要条件（缺一不可）：

1. `_publish_atomic` 返回空 errors 列表（temp → fsync → os.replace → readback SHA 全部成功）。
2. 发布后 `out_path` 真实存在。
3. 重新读取的字节 SHA == 源字节 SHA。
4. 重新解析的 JSON 是 dict。
5. dict 的 `run_id` 严格等于期望 `run_id`。
6. dict 的 `status` 严格等于期望 `status`（"RUNNING" 或 "FAILED"）。
7. dict 的 `passed` 严格等于 `False`（marker 永远不是绿色）。

任一不满足 → `ok=False` 且 `errors` 非空。**调用方必须显式检查 `.ok`，不能依赖异常**。

`_publish_marker_with_readback` 是统一的发布 + readback 实现，RUNNING 和 FAILED marker 都走它。永不抛异常（所有失败都转为结构化 errors），所以 `main()` 的 try/except 不会被绕过。

## RUNNING gate 前置条件

正式流程：

1. 生成 `run_id`。
2. 原子发布 RUNNING marker（`_publish_marker_with_readback` 内部已做 readback）。
3. **只有 `.ok=True` 才允许调用 gate runner**。

RUNNING 发布或 readback 任一失败（`_publish_atomic` 返回非空、文件缺失、SHA 不匹配、JSON 解析失败、run_id/status/passed 字段不符）：

- `exit_code = 1`
- `gate_calls = 0`（gate runner 从未被调用）
- stderr 含结构化 `RUNNING_MARKER_WRITE_FAILED`
- stderr 明确 `this run did not start; gate_calls=0`
- 不打印 PASS

若旧 COMMITTED 文件仍在磁盘，它只能表示"上一轮最后成功"，不能声称本次已进入 RUNNING。CLI 文本和退出码明确说明本次未启动。

## FAILED marker 诚实状态

业务/commit 失败后：

- 调用 `_write_failed_marker` → 返回 `MarkerWriteResult`。
- readback 成功才返回 `ok=True`（即 `failed_marker_written=True`）。
- 若写入或 readback 任一步失败，`ok=False` 且 `errors` 非空。

`_print_summary(final_passed=False, failed_marker_written=...)` 的文本规则：

| failed_marker_written | stdout 文本 |
| --- | --- |
| `True` | `status: FAILED (no green metrics left)` |
| `False` | `status: FAILED_MARKER_WRITE_FAILED` + `note: on-disk marker may be from a previous run` |
| `None` | `status: FAILED`（仅在 uncaught exception 路径，main() 直接写 FAILED marker 并自行判断） |

无论哪种情况均 `exit 1`。

`_fail_and_summarize` 是统一的失败 finalize + summary helper，所有 `_orchestrate` 内的失败路径都走它，保证 summary 文本与 on-disk 真实状态一致。

## 8 类真实主路径负例

全部通过真实 `main()` 路径，使用 `tmp_path` evidence_dir + monkeypatch `_publish_atomic` + 捕获 stdout/stderr。所有断言基于真实 exit_code、真实 gate_calls、真实 on-disk 状态、真实 stdout/stderr 文本，不复制 marker 判定逻辑。

### MN-M1 RUNNING _publish_atomic 返回 error → gate_calls=0

- **攻击**：monkeypatch `_publish_atomic` 第 1 次调用（RUNNING marker）返回 `["forced RUNNING marker publish failure"]`。
- **结果**：`exit_code=1`；`gate_calls=0`；stderr 含 `RUNNING_MARKER_WRITE_FAILED` 和 `this run did not start`；stdout 不含 PASS。
- **测试**：`test_m1_running_publish_failure_blocks_gates` PASS。

### MN-M2 RUNNING readback run_id 错误 → gate_calls=0

- **攻击**：让 `_publish_atomic` 第 1 次调用（RUNNING）正常返回，但 monkeypatch 在返回前把磁盘上的 marker `run_id` 改为 `tampered-different-run-id`。
- **结果**：`exit_code=1`；`gate_calls=0`（readback 验证发现 run_id 不符，`.ok=False`，main() 在进入 gate 前返回）。
- **测试**：`test_m2_running_readback_run_id_mismatch` PASS。

### MN-M3 RUNNING readback status 错误 → gate_calls=0

- **攻击**：让 `_publish_atomic` 第 1 次调用正常返回，但 monkeypatch 把磁盘 marker `status` 改为 `COMMITTED`（应为 `RUNNING`）。
- **结果**：`exit_code=1`；`gate_calls=0`。
- **测试**：`test_m3_running_readback_status_mismatch` PASS。

### MN-M4 预置旧 COMMITTED，RUNNING 写失败 → gate_calls=0

- **攻击**：先在 evidence_dir 写一份 `run_id=old-green-run, status=COMMITTED, passed=true`；再让 RUNNING `_publish_atomic` 失败。
- **结果**：`exit_code=1`；`gate_calls=0`；stderr 含 `this run did not start`。
- **测试**：`test_m4_stale_committed_running_fails` PASS。

### MN-M5 COMMITTED publish 失败、FAILED marker 成功 → FAILED/passed=false

- **攻击**：让第 4 次 `_publish_atomic`（COMMITTED metrics）失败，第 5 次（FAILED marker）正常。
- **结果**：`exit_code=1`；`gate_calls=2`；on-disk metrics 为本次 `status=FAILED, passed=false`；stdout 含 `FAILED (no green metrics left)`；不含 `FAILED_MARKER_WRITE_FAILED`。
- **测试**：`test_m5_committed_fails_failed_marker_succeeds` PASS。

### MN-M6 COMMITTED 失败、FAILED marker 也失败 → FAILED_MARKER_WRITE_FAILED

- **攻击**：让第 4、5 次 `_publish_atomic` 都失败。
- **结果**：`exit_code=1`；stderr 含 `FAILED_MARKER_WRITE_FAILED`；stdout **不含** `no green metrics left`。
- **测试**：`test_m6_committed_and_failed_marker_both_fail` PASS。

### MN-M7 FAILED marker 写入后 readback 显示旧 run_id/passed=true → 按 marker 失败处理

- **攻击**：让第 4 次失败；第 5 次（FAILED marker）`_publish_atomic` 正常返回，但 monkeypatch 在返回前把磁盘内容替换为 `{run_id: old-green-run, status: COMMITTED, passed: true}`。
- **结果**：`exit_code=1`；stderr 含 `FAILED_MARKER_WRITE_FAILED`；stdout 不含 `no green metrics left`。
- **测试**：`test_m7_failed_marker_readback_stale` PASS。

### MN-M8 正向：RUNNING 成功 → gate_calls=2，COMMITTED，verifier PASS

- **流程**：不 patch 任何 `_publish_atomic`；正常 runner。
- **结果**：`exit_code=0`；`gate_calls=2`；stdout 含 PASS；on-disk metrics `status=COMMITTED, passed=true`；`verifier_module.verify()` 返回空 errors。
- **测试**：`test_m8_positive_running_then_committed` PASS。

## stdout/stderr 与落盘一致性

| 场景 | stdout | stderr | on-disk metrics |
| --- | --- | --- | --- |
| RUNNING 失败 | (无 PASS) | `RUNNING_MARKER_WRITE_FAILED` + `this run did not start` | 上一轮 COMMITTED 或不存在（本次未启动） |
| 业务失败 + FAILED marker 成功 | `FAILED (no green metrics left)` | 业务 errors | 本次 `FAILED/passed=false` |
| 业务失败 + FAILED marker 失败 | `FAILED_MARKER_WRITE_FAILED` + `note: on-disk marker may be from a previous run` | `FAILED_MARKER_WRITE_FAILED` + publish errors | 上一轮 COMMITTED 或部分写入（本次 FAILED 未落盘） |
| 全部成功 | `PASS` | (无) | 本次 `COMMITTED/passed=true` |

控制台陈述和落盘状态一一对应，不再出现"声称无绿色但磁盘仍绿色"的矛盾。

## 测试隔离 SHA

模块级 `@pytest.fixture(scope="module", autouse=True)` 在测试前后读取真实 evidence 三文件的 SHA 并断言不变。独立 shell 验证（运行完整 39 项契约测试前后）：

```
delta = 0
```

三文件 SHA 测试前后完全一致。fake runner 测试通过 `evidence_dir=tmp_path` 注入，不触碰正式 evidence。

## 正式 orchestrator / verifier

```
$ .venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
Orchestrator: PASS
  run_id:        8a4e94ec-bc30-4a68-9171-4121b29a9480
  contract_sha:  45c134efc1e311cb...
  pack-trust:    23 mutations, exit=0, passed=True
  annotation:    34 mutations, exit=0, passed=True
  meta-neg:      True

$ .venv/bin/python scripts/p13_2_verify_committed_evidence.py
committed-evidence verifier: PASS
```

contract_sha256 = `45c134efc1e311cb...`（未变），schema = `contract-1.0.0`（未变），23/34/2/1/5 集合未变。

## 全量回归

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| Ruff | `.venv/bin/ruff check signal_miner tests scripts` | All checks passed |
| fix-6 聚焦测试 | `pytest tests/test_p13_2_pack_trust_metrics_contract.py` | **39 passed** in 0.10s |
| pack-trust 契约 | `pytest tests/test_p13_2_pack_trust_contract.py` | **22 passed** |
| annotation 契约 | `pytest tests/test_p13_2_human_annotation_contract.py` | **43 passed** |
| 全量回归 | `pytest -o addopts= -q` | **328 passed, 3 warnings** in 50.08s |
| 正式 orchestrator | `python scripts/p13_2_pack_trust_contract_metrics.py` | PASS, 23/34, exit 0 |
| committed-evidence verifier | `python scripts/p13_2_verify_committed_evidence.py` | PASS, exit 0 |
| behavior probe | `python scripts/p13_1_behavior_probe.py` | Overall: PASS |
| goldset validator | `python scripts/p13_2_validate_goldset.py` | `{"status": "READY", "passed": true}` |
| metrics JSON | `python3 -m json.tool ...metrics.json` | VALID |
| pack-trust JSON | `python3 -m json.tool ...gate.json` | VALID |
| annotation JSON | `python3 -m json.tool ...gate.json` | VALID |
| 测试 SHA 隔离 | 独立 shell 前后比对 | delta = 0 |
| git diff | `git diff --check` | clean |

3 warnings 均为先前已存在的（fastapi deprecation + async mock coroutine），与本次修改无关。

## 未覆盖风险

- fix-6 只关闭 marker 错误传播。真实授权候选仍为 0（fixture-only），P13-2-2-2 与校准继续冻结。
- contract_sha256 是 SHA-256（无发布者认证），下一阶段才考虑外部 pack manifest 签名/HMAC 信任根升级。
- `_fail_and_summarize` 的 `pt_count/an_count` 在 gate 空输出等极早失败路径为 0，仅反映已成功解析后的 gate 行数；这是诚实的，不是缺陷。
- 长期防复发阈值（连续 10 次交付零复发或 20 个 blocker 样本 ≤ 1 次）尚未达到，后续阶段继续保留 RUNNING/FAILED marker 契约、commit 前后验证、测试隔离三类门禁。

## 完成边界

fix-6 通过仍只证明 P13-2-2-1A evidence marker 错误闭环可信。真实授权候选为 0 时，P13-2-2-2 与校准继续冻结。
