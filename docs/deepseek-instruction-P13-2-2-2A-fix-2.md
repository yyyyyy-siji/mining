# DeepSeek 返修指令：P13-2-2-2A fix-2 READY信任链闭环

## 任务目标

关闭 fix 后仍存在的 READY 假绿：没有dataset/pack manifest、没有签名pack、没有test task、split与候选无关时绝不能READY。本轮只把现有P13-2-2-1A信任根和真实任务分配接入readiness，不重写1A工具链。

当前仍无用户真实输入，因此正式默认运行必须继续为 `BLOCKED_INPUT_REQUIRED/exit2`；不得为追求READY生成伪真实数据。

## 允许修改范围

- `scripts/p13_2_real_annotation_launch_readiness.py`
- `tests/test_p13_2_real_annotation_launch_readiness.py`
- 必要时新增readiness专用的独立evidence sidecar verifier或小型schema helper。
- `docs/P13-2/` 的launch config schema/runbook示例。
- `docs/P13-2-evidence/real-annotation-launch-readiness.json`及sidecar。
- P13-2-2-2A fix-2交付报告。

## 禁止修改范围

- 不得修改或弱化 `signal_miner/evaluation/pack_trust.py`、`human_annotation.py`、1A importer、23/34 mutation gate、orchestrator或committed-evidence verifier。
- 不得复制一个简化版签名/hash verifier来替代1A单一真源。
- 不得由LLM、fixture或规则生成真实人工标签或授权依据。
- 不得进入P13-2-2-2B、P13-2-3、P13-2-4、P13-3或前端发布。

## 实现要求

### 1. Launch config必须引用完整信任链

生产launch config至少新增并强制消费：

```json
{
  "real_candidate_path": "...",
  "real_rejections_path": "...",
  "dataset_manifest_path": "...",
  "pack_manifest_path": "...",
  "task_dir": "...",
  "roles_config_path": "...",
  "splits_config_path": "...",
  "governance_config_path": "..."
}
```

- 所有相对路径（包括task_dir）必须相对launch config所在目录解析。
- 缺路径/文件属于 `missing/exit2`；路径已提供但JSON/schema/hash/signature无效属于 `invalid/exit1`。
- READY时从真实文件推导并写入非null的 `dataset_id`、`batch_id`（或明确版本化run/batch identity）、`dataset_manifest_sha256`、`pack_manifest_sha256`。

### 2. 必须复用P13-2-2-1A生产verifier

调用 `signal_miner.evaluation.pack_trust.verify_manifest_file()`，参数必须包含：

- `manifest_path=pack_manifest_path`
- `task_dir=task_dir`
- 生产 `ANNOTATION_PACK_SIGNING_KEY`
- `dataset_manifest_path=dataset_manifest_path`
- 需要时校验生产key id

`result["valid"] is True`必须成为顶层passed的REQUIRED check。它必须验证：

- 精确四pack文件集合；
- pack SHA/bytes/task_count；
- dataset manifest SHA与dataset_id绑定；
- HMAC签名；
- fixture=false且生产key边界；
- manifest、dataset和pack dataset_id一致。

另外逐task复用 `signal_miner.evaluation.human_annotation.compute_task_hash()` 重算 `dataset_id + sample_id + annotator_slot + content_hash`，任何task hash不一致为 `invalid/exit1`。不得只依赖manifest文件级SHA而不检查task identity。

### 3. 从任务包重算任务、盲标、双标和访问边界

不得再信任roles配置中的计划count或 `a_b_access_isolation=true` 作为最终事实。

- 从四个已签名pack读取task，重算每个pack/slot/unique sample数量。
- test盲标数按唯一test `sample_id` 计算，不按JSON文件数；25个空pack必须失败。
- test任务必须递归扫描禁用字段，并与冻结test split精确绑定。
- A/B双标数量从同一sample在两个不同annotator_slot的实际任务分配重算，要求≥`max(20, ceil(n×20%))`。
- A/B pack必须各自只含自己的slot，不得含对方label、annotation或可读取引用；裁决pack不得改写A/B原始记录。
- 角色配置中的pseudonym/role id必须与pack assignment、governance access list一致；自报布尔值只能作为声明，不能替代实际检查。

### 4. Split必须与候选及任务真实绑定

- development/calibration/test三组sample_id并集必须与合格候选集精确一致：无缺失、无多余、无重复。
- 每个split sample必须绑定候选的content SHA；同content不得跨split。
- 对已有的session/conversation/near-duplicate group字段执行group隔离；没有必要字段时不得假装近重复门禁已通过，应BLOCKED或INVALID。
- task pack中的sample_id、content hash和split必须与冻结split manifest一致。
- 50/25/25及test≥25基于唯一候选/任务重算。

本阶段只验证冻结group字段，不要求实现新的聚类或近重复算法。

### 5. 候选、rejections和治理严格校验

- 补齐source adapter/version字段，并解析 `captured_at` 为带时区ISO-8601；URL只允许批准的可审计scheme/host策略，不接受仅“含scheme”即有效。
- export声明的 `rejected_count` 必须等于 `real_rejections`实际行数；rejection reason分布必须从实际文件重算并与声明一致。
- 候选dataset_id必须唯一一致并与dataset manifest一致。
- governance开始、结束、retention必须解析为带时区datetime，不得使用字符串字典序。
- allowed_access_role_ids必须至少精确覆盖A/B/裁决受控role id；未知/缺失角色按明确schema处理，不能只要求非空。

### 6. 删除production override旁路

生产 `main()`不能通过 `_test_mode=True` 在 `environment="production"` 接受内存roles/splits/packs/governance。可选方案：

- production主路径完全只接受launch config；测试通过真实CLI和tmp_path文件运行；或
- 仅当 `APP_ENVIRONMENT=test` 且使用显式test key时允许override。

不得保留一个布尔参数即可绕过生产文件与信任链的路径。

### 7. 独立evidence SHA验证

提供独立、只读、不发布的验证入口，例如：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

要求：

- JSON与sidecar匹配时exit0；
- JSON或sidecar任一篡改、缺失、格式错误时exit1；
- 验证不能先覆盖/重新生成artifact；
- N16必须调用这个生产入口，而不是只在测试中比较两个hash字符串。

## 必须存在的生产主路径负例

以下负例必须通过正式CLI/与CLI共用的唯一生产主路径，全部断言exit、passed和结构化target：

1. 无dataset manifest → exit2；提供后篡改 → exit1。
2. 无pack manifest → exit2；签名篡改 → exit1。
3. pack文件SHA/bytes/count篡改 → exit1。
4. task hash单独篡改，以及task与annotation/hash同步伪造 → exit1。
5. 25个空JSON/0个test task → exit1，不得READY。
6. split 50/25/25但ID与候选零交集 → exit1。
7. content/session/near-duplicate group跨split → exit1。
8. roles配置声明双标20，但实际A/B共同样本为0 → exit1。
9. `a_b_access_isolation=true`但A pack含B slot/label引用 → exit1。
10. rejections声明999、实际0 → exit1。
11. `captured_at="not-a-timestamp"`、治理时间`a/b/c` → exit1。
12. allowed access不包含A/B/裁决角色 → exit1。
13. READY artifact四个identity/hash字段任一null → 测试失败。
14. 发布后篡改JSON或sidecar，独立`--verify-evidence` → exit1。

必须保留上一轮已关闭的count伪报、授权缺字段、test blind泄漏、当前零输入exit2等回归。

## 正向验收要求

正向测试必须生成受控tmp_path dataset manifest、四个任务pack和生产模式签名manifest，并通过真实CLI加载；不得用空JSON、内存override或未签名字典作为正例。

正向READY机器证据至少满足：

```text
status=READY_FOR_HUMAN_ANNOTATION
passed=true
exit_code=0
pack_trust=true
task_identity=true
split_binding=true
test_unique_task_count>=25
double_label_recomputed_count>=20
dataset_id!=null
batch_id!=null
dataset_manifest_sha256=<actual 64 hex>
pack_manifest_sha256=<actual 64 hex>
human_verified_count=0
calibration_allowed=false
```

## 验收命令

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
git diff --check
```

## 交付前证据门禁

- readiness JSON、sidecar、交付报告中所有SHA必须扫描并逐一等于当前实际文件；不得保留旧代码块值。
- 交付报告不得把“缺生产密钥”列作N11签名/hash篡改证据。
- 报告逐项列出上述14个生产主路径负例的测试名/命令、退出码和target。
- 聚焦/全量测试前后正式JSON及sidecar SHA必须不变。

## 完成边界

fix-2通过只表示readiness工具能正确判定启动条件。当前真实输入仍为0，正式结果必须继续BLOCKED；不得进入P13-2-2-2B或生成任何真实人工标签。

