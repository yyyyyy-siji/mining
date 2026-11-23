# P13-2-2-1A fix-5 交付报告

## 结论

fix-5 已完成，关闭 fix-4 验收报告中的四个 P0 拦截点和两个 P1 拦截点：

- **P0-1 关闭**：commit 前 gate 再验证 (`_reverify_gate_on_disk`) — gate publish 后、metrics commit 前被篡改 → exit 1，无绿色 metrics。
- **P0-2 关闭**：metrics publish 错误参与最终返回码 — 任何 `_publish_atomic` 错误 → exit 1，控制台不打印 PASS。
- **P0-3 关闭**：畸形输入失败闭环 — RUNNING marker 先写，所有 KeyError/TypeError 被严格类型校验拦截；未捕获异常由 `main()` 的 try/except 转为 FAILED marker + exit 1，旧绿色 metrics 不会保留。
- **P0-4 关闭**：测试隔离 — 所有 fake runner 测试通过 `evidence_dir=tmp_path` 注入；删除 `TestEvidenceRestore`；模块级 fixture 自动断言真实 evidence 三文件 SHA 前后不变（实测 delta=0）。
- **P1-1 关闭**：strict metadata 校验 — `phase`、`command`、`contract_schema_version`、`exit_code` 均严格值匹配。
- **P1-2 关闭**：交付报告测试数自动采集，不手写旧数字（见下文机器结果）。

fix-4 的 23/34/2/1/5 版本化精确集合与不可变 bytes snapshot 完全保留，未做任何缩减。

## 修改文件

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `scripts/p13_2_pack_trust_contract_metrics.py` | 重写 | Evidence 事务状态机、commit 前再验证、发布错误返回码、畸形输入闭环、`evidence_dir` 参数 |
| `scripts/p13_2_verify_committed_evidence.py` | 新增 | 独立 committed-evidence verifier，post-commit tamper → exit 1 |
| `tests/test_p13_2_pack_trust_metrics_contract.py` | 重写 | 31 项契约测试，全部通过 `evidence_dir=tmp_path` 注入；模块级 fixture 守护真实 evidence SHA |
| `docs/P13-2-evidence/pack-trust-contract-metrics.json` | 重新生成 | status=COMMITTED, passed=true, run_id 一致 |
| `docs/P13-2-evidence/pack-trust-mutation-gate.json` | 重新生成 | 23/23 + 2/2 invariants |
| `docs/P13-2-evidence/human-annotation-mutation-gate.json` | 重新生成 | 34/34 + 1/1 invariant + 5/5 meta-negatives |

未修改：`signal_miner/evaluation/p13_2_gate_contract.py`、两个 mutation gate 脚本的业务规则、pack trust / annotation importer/validator 业务规则、生产 pipeline、数据库、API、前端。

## Evidence 事务状态机

正式运行的生命周期：

```
RUNNING  ──[all gates + commit + verify OK]──►  COMMITTED (passed=true)
   │
   └─[any failure / exception]──►  FAILED (passed=false, exit 1)
```

状态转换点：

1. **启动**：`_write_running_marker` 在任何 gate 运行前原子发布 `status=RUNNING, passed=false`。
2. **成功路径**：所有 gate 通过 + gate 发布 + commit 前再验证 + metrics 原子发布 + committed-evidence verifier 通过 → `status=COMMITTED, passed=true`。
3. **失败路径**：任一 gate 失败、契约违反、发布错误、异常或 verifier 失败 → `_write_failed_marker` 原子写 `status=FAILED, passed=false, errors=[...]`，exit 1。

**旧绿色 metrics 不会保留**：每次正式运行的第一步就是把当前 metrics 文件原子替换为本次 run_id 的 RUNNING marker。即使本次最终 FAILED，磁盘上也是本次的 FAILED marker，不会是上一轮的 COMMITTED 绿色。

## Commit 前后验证流程

```
┌─ Step 1-9: gates 运行 + 契约校验（exact-set、per-row、metadata、counts）
│
├─ Step 10: 原子发布两个 gate artifact（_publish_atomic: temp → fsync → os.replace → readback → SHA verify）
│
├─ Step 11: ★ commit 前再验证 ★ (_reverify_gate_on_disk)
│           重新从磁盘读取每个 gate 文件，验证：
│             - bytes SHA == snapshot SHA（捕获 P0-1 tamper）
│             - bytes 内容 == snapshot（即使 SHA 碰撞）
│             - JSON 可解析
│             - run_id / contract_sha256 / passed / phase / command / schema 严格匹配
│           任一不符 → _write_failed_marker + exit 1
│
├─ Step 12: 构建 metrics payload（status=COMMITTED, passed=true 为暂定）
│
├─ Step 13: 原子发布 metrics（_publish_atomic）
│           任一 publish/fsync/replace/readback 错误 → _write_failed_marker + exit 1（P0-2）
│
├─ Step 14: ★ committed-evidence verifier ★ (_verify_committed_evidence)
│           独立读取三份 artifact，复核：
│             - metrics 引用的 artifact SHA == 磁盘实际 SHA
│             - run_id 三处一致
│             - contract_sha256 三处一致
│             - metrics status == COMMITTED, passed == True
│           任一不符 → _write_failed_marker + exit 1
│
└─ Step 15: final_passed 在全部成功后计算；PASS 文本仅在此时打印
```

对 main 返回后才发生的外部篡改，orchestrator 自身不能追溯改返回码，因此提供独立 verifier 脚本（见下文）。

## RUNNING/FAILED/COMMITTED marker

### RUNNING marker（启动时原子写）

```json
{
  "run_id": "...",
  "status": "RUNNING",
  "passed": false,
  "started_at": "...",
  "generated_at": "...",
  "phase": "orchestrator",
  "contract_sha256": "..."
}
```

### FAILED marker（任何失败时原子写）

```json
{
  "run_id": "...",
  "status": "FAILED",
  "passed": false,
  "started_at": "...",
  "finished_at": "...",
  "generated_at": "...",
  "phase": "orchestrator",
  "contract_sha256": "...",
  "contract_schema_version": "contract-1.0.0",
  "errors": ["..."],
  "production_blocked": true,
  "calibration_allowed": false,
  "human_labels_complete": false
}
```

### COMMITTED marker（全部成功后）

见 `docs/P13-2-evidence/pack-trust-contract-metrics.json` — 包含 `status=COMMITTED, passed=true`、两个 gate 的完整引用、artifact SHA 等。

## 六个 Commander 真实负例

全部通过真实 orchestrator `main()` 路径或真实 verifier，不复制校验逻辑。

### MN16 Pre-commit tamper（orchestrator 阻断）

**攻击**：pack gate 发布后、metrics commit 前，monkeypatch `_reverify_gate_on_disk` 在第一次调用时把已发布的 gate 文件 `passed` 改 false 并写回。

**结果**：`exit_code == 1`；metrics 文件为 `status=FAILED, passed=false`。`tests/test_p13_2_pack_trust_metrics_contract.py::TestFix5CommanderNegatives::test_pre_commit_tamper` 通过。

### MN17 Metrics publish failure（orchestrator 阻断）

**攻击**：monkeypatch `_publish_atomic` 让 metrics 发布（第 3 次调用）返回 `["forced metrics publish failure"]`。

**结果**：`exit_code == 1`；控制台不打印 PASS；若 metrics 文件存在则 `passed != true`。`tests/.../test_metrics_publish_failure` 通过。

### MN18 Stale-green crash（orchestrator 阻断）

**攻击变体 MN18a**：fake runner 返回缺 `mutation` 字段的行。`_check_exact_set` 与 `_check_row_contract` 的逐层类型校验拦截（不再 `[r["mutation"] for r in ...]` 裸索引）。

**攻击变体 MN18b**：top-level 是 list 而非 dict。`_require_dict` 拦截。

**攻击变体 MN18c**：`results` 是 dict 而非 list。`_require_list` 拦截。

**攻击变体 MN18d**：row 是字符串而非 dict。`_check_row_contract` 内 `isinstance(r, dict)` 拦截。

**攻击变体 MN18e**：`detected` 为 `1`（truthy 但非 True）。`_bool_strictly_true` 拒绝。

**结果**：全部 `exit_code == 1`，无未捕获异常 traceback，metrics 为 `status=FAILED`。五项测试通过。

### MN19 Metadata mismatch（orchestrator 阻断）

**攻击变体 MN19**：phase / command / contract_schema_version 同时错误。`_validate_gate_payload` 的 strict metadata 校验拦截。

**攻击变体 MN19b**：phase 跨污染（pack-trust 的 phase 写成 annotation 的）。

**攻击变体 MN19c**：command 缺失。

**结果**：全部 `exit_code == 1`。三项测试通过。

### MN20 Post-commit tamper（verifier 阻断）

**攻击**：成功运行 orchestrator 后，直接写改 `pack-trust-mutation-gate.json` 的 `passed=false`。orchestrator 自身不能追溯改返回码，但独立 `scripts/p13_2_verify_committed_evidence.py` 必须能发现。

**结果**：`verifier_module.verify(tmp_path)` 返回非空 errors 列表，且至少一条含 "sha"（artifacts SHA 不匹配）。正式 CLI 同样行为：`python scripts/p13_2_verify_committed_evidence.py` 在 tamper 后 exit 1。

### MN21 Test isolation（evidence SHA 零变化）

**机制**：`@pytest.fixture(scope="module", autouse=True)` 在测试前后读取真实 evidence 三文件的 SHA，yield 后断言 `before == after`。

**实测结果**（独立 shell 验证，非测试内部）：

```
BEFORE:
  pack-trust-contract-metrics.json: 410d73b7d28f4adf...
  pack-trust-mutation-gate.json:     9111c46bc657bb8d...
  human-annotation-mutation-gate.json: acee6064c61b3c6b...
AFTER (运行完整 31 项契约测试后):
  pack-trust-contract-metrics.json: 410d73b7d28f4adf...
  pack-trust-mutation-gate.json:     9111c46bc657bb8d...
  human-annotation-mutation-gate.json: acee6064c61b3c6b...
```

**delta = 0**：运行 pytest 不再污染正式 evidence，也不再用 fake runner "恢复"绿色证据。`TestEvidenceRestore` 类已删除。

## 测试隔离与正式 evidence SHA 零变化

`main(gate_runner=..., evidence_dir=tmp_path)` 的注入点：

- `_write_running_marker(evidence_dir=tmp_path, ...)`
- `_publish_atomic(..., tmp_path / PT_NAME)` / `(tmp_path / AN_NAME)`
- `_reverify_gate_on_disk(tmp_path / PT_NAME, ...)` / `(tmp_path / AN_NAME, ...)`
- `_publish_atomic(..., tmp_path / METRICS_NAME)`
- `_verify_committed_evidence(tmp_path)`

正式 CLI 入口 `main()` 不传 `evidence_dir`，使用 `EVIDENCE_DIR_DEFAULT`；只有真实 orchestrator 运行才写 `docs/P13-2-evidence`。

## 23/34/2/1/5 回归

正式 orchestrator 输出：

| 集合 | contract | 实际 | exit |
| --- | --- | --- | --- |
| pack-trust mutations | 23 | 23/23 detected | 0 |
| pack-trust readiness invariants | 2 | 2/2 passed | 0 |
| annotation mutations | 34 | 34/34 detected | 0 |
| annotation readiness invariants | 1 | 1/1 passed | 0 |
| annotation meta-negatives | 5 | 5/5 passed | 0 |

contract_sha256 = `45c134efc1e311cb...`（未变），schema_version = `contract-1.0.0`（未变）。

## 正式 committed-evidence verifier

```bash
$ .venv/bin/python scripts/p13_2_verify_committed_evidence.py
committed-evidence verifier: PASS
  evidence_dir: .../docs/P13-2-evidence
  checked_at:   2026-07-14T03:08:08.399307+00:00
```

Verifier 独立检查：

- 三份 artifact 文件存在且 JSON 可解析
- metrics status == COMMITTED, passed == True
- contract_sha256 三处一致（metrics + pack-trust + annotation）
- contract_schema_version 匹配
- run_id 三处一致
- metrics 引用的 artifact SHA == 磁盘实际 SHA
- 每个 gate 的 phase / command / exit_code / passed 严格匹配
- 各集合基数（23/34/2/1/5）匹配 contract

任何 post-commit tamper（如改 gate 的 passed、改 SHA 引用、改 run_id）都会使 verifier exit 1。

## 全量回归

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| Ruff | `.venv/bin/ruff check signal_miner tests scripts` | All checks passed |
| fix-5 聚焦测试 | `pytest tests/test_p13_2_pack_trust_metrics_contract.py` | **31 passed** in 0.13s |
| pack-trust 契约 | `pytest tests/test_p13_2_pack_trust_contract.py` | **22 passed** |
| annotation 契约 | `pytest tests/test_p13_2_human_annotation_contract.py` | **43 passed** |
| 全量回归 | `pytest -o addopts= -q` | **320 passed, 3 warnings** in 49.17s |
| 正式 orchestrator | `python scripts/p13_2_pack_trust_contract_metrics.py` | PASS, 23/34, exit 0 |
| committed-evidence verifier | `python scripts/p13_2_verify_committed_evidence.py` | PASS, exit 0 |
| behavior probe | `python scripts/p13_1_behavior_probe.py` | Overall: PASS |
| goldset validator | `python scripts/p13_2_validate_goldset.py` | `{"status": "READY", "passed": true}` |
| metrics JSON | `python3 -m json.tool ...metrics.json` | VALID |
| pack-trust JSON | `python3 -m json.tool ...gate.json` | VALID |
| annotation JSON | `python3 -m json.tool ...gate.json` | VALID |
| git diff | `git diff --check` | clean |

3 warnings 均为先前已存在的（fastapi deprecation + async mock coroutine），与本次修改无关。

## 正式 current commit / run_id / artifact SHA

```
run_id:           7648f91f-1876-4beb-ad71-3847ff1e936a
status:           COMMITTED
passed:           true
contract_sha256:  45c134efc1e311cb53413a7fe094e323716aab954b95b55882c64b978d798d5e
schema_version:   contract-1.0.0

pack-trust artifact_sha256:    9111c46bc657bb8d... (matches disk)
annotation artifact_sha256:    acee6064c61b3c6b... (matches disk)
metrics file sha256:           410d73b7d28f4adf...

committed-evidence verifier exit code: 0
```

## "orchestrator 应当阻断" vs "提交后由 verifier 发现"

按 DeepSeek fix-5 指令要求，本报告明确区分两类阻断：

| 场景 | 阻断方 | 实现 |
| --- | --- | --- |
| Pre-commit gate tamper（publish 后、metrics commit 前） | orchestrator | `_reverify_gate_on_disk` → exit 1 |
| Metrics publish failure | orchestrator | `_publish_atomic` 错误参与 exit code → exit 1 |
| 畸形 evidence / 异常 | orchestrator | RUNNING marker + strict type checks + try/except → exit 1 |
| Metadata mismatch | orchestrator | `_validate_gate_payload` strict metadata → exit 1 |
| Post-commit tamper（main 返回后） | 独立 verifier | `scripts/p13_2_verify_committed_evidence.py` exit 1 |
| Test pollution | （预防）| `evidence_dir=tmp_path` + fixture SHA guard |

orchestrator 自身不能追溯改 main 返回后的外部篡改，因此 post-commit tamper 由独立 verifier 阻断；两类不混称。

## 未覆盖风险

- fix-5 只关闭 evidence 事务与外部 pack 信任根工具的可信度。**真实授权候选仍为 0**（fixture-only），P13-2-2-2 与校准继续冻结。
- contract_sha256 是 SHA-256（无发布者认证），下一阶段才考虑外部 pack manifest 签名/HMAC 信任根升级。
- committed-evidence verifier 是确定性机器门禁，不替代人工审计；持续监控仍需对接 SIEM/审计日志。
- 长期防复发阈值（连续 10 次交付零复发或 20 个 blocker 样本 ≤ 1 次）尚未达到，后续阶段继续保留 evidence 事务状态机、commit 前后验证、测试隔离三类门禁。

## 完成边界

fix-5 通过仍只证明 P13-2-2-1A evidence 事务与外部 pack 信任根工具可信。真实授权候选为 0 时，P13-2-2-2 与校准继续冻结。
