# DeepSeek 返工指令：P13-2-2-1A fix-5 Evidence 事务提交与测试隔离

## 任务目标

保留 fix-4 已有效的 23/34/2/1/5 exact-set 和 immutable bytes snapshot；只关闭四个剩余缺口：commit 前 gate 再验证、metrics 发布失败返回码、异常/旧绿状态、fake 测试污染正式 evidence。

## 背景 / 当前问题

- gate 在自身 publish 返回后、metrics commit 前被篡改，orchestrator仍 exit0/passed=true。
- final metrics `_publish_atomic` 失败时仍打印 PASS并exit0。
- 畸形行触发KeyError后旧passed=true metrics保留。
- pytest fake runner直接覆盖正式 evidence，最后仍用fake数据“恢复”。

## 允许修改范围

- `scripts/p13_2_pack_trust_contract_metrics.py`
- 新增一个 committed-evidence verifier脚本或同模块正式 CLI子命令
- 两个 mutation gate 的 evidence 元数据字段（仅在严格契约需要时）
- `tests/test_p13_2_pack_trust_metrics_contract.py`
- P13-2 evidence 提交目录/manifest结构
- 本次交付报告和机器证据

## 禁止修改范围

- 修改或减少 23/34/2/1/5 必需集合
- 修改 pack trust、dataset manifest、annotation importer/validator 业务规则
- 修改生产 pipeline、数据库、API、前端或进入后续阶段
- 测试写入 `docs/P13-2-evidence` 后再用 fake runner恢复
- 把发布错误只写日志但仍 exit0
- 用 `try/except: pass`、保留旧绿 metrics或手工改JSON掩盖失败

## 实现要求

### 1. 明确 Evidence 事务状态

正式运行开始时先原子发布本次 run_id 的非绿色状态：

```json
{
  "run_id": "...",
  "status": "RUNNING",
  "passed": false
}
```

随后才运行 gates。正常成功状态只能在两个 gate和最终 metrics全部提交、重新验证成功后成为 `COMMITTED/passed=true`。任何异常或发布失败必须留下本次 `FAILED/passed=false`，不得让旧 run 的绿色 marker代表本次结果。

如采用 run-specific evidence目录，推荐：

```text
docs/P13-2-evidence/runs/<run_id>/
  pack-trust-mutation-gate.json
  human-annotation-mutation-gate.json
  pack-trust-contract-metrics.json
docs/P13-2-evidence/current.json
```

先在同文件系统 staging目录写齐、fsync并验证，再原子rename为 committed run目录，最后原子更新 `current.json`。固定文件镜像如保留，只能作为非权威兼容视图；权威读取必须从 current commit解析。

### 2. Commit 前后完整验证

Final green commit至少满足：

1. 两个 gate目标文件重新读取后的 bytes SHA等于 snapshot SHA。
2. 重新解析后的 run_id、contract SHA、schema version、phase、command、exit_code、passed均与已验证值一致。
3. metrics写入成功，发布后重新读取并验证自身 run_id/status/passed与两个artifact引用。
4. committed-evidence verifier对当前提交 exit0。
5. 任一步出错，最终返回码必须1；不得打印PASS。

对“main返回后才发生的外部篡改”，orchestrator不能追溯改变旧返回码，因此必须提供独立 verifier；篡改后 verifier必须exit1。对 gate publish与metrics commit之间的篡改，orchestrator自身必须exit1。

### 3. 所有失败参与最终返回码

禁止在 metrics publish前冻结 `final_passed`。最终退出码只能在以下全部完成后计算：

- gate运行与契约验证
- gate发布与commit前重验
- metrics原子发布与post-verify
- current commit marker原子更新
- 最终 verifier

任何 `_publish_atomic` / fsync / replace / readback / verifier error 都必须 `status=FAILED, passed=false, exit1`。控制台 PASS 只能在最终 verifier成功以后输出。

### 4. 畸形输入与异常闭环

先逐层校验：顶层必须dict；results/invariants/meta必须list；每行必须dict；所有必需字段存在且严格类型正确。不得直接在未验证容器上使用 `r["mutation"]`、`r["name"]`或datetime aware/naive比较。

至少覆盖：

- 顶层JSON为list/null/string
- results缺失/null/dict
- 行不是dict
- mutation/name缺失或非string
- bool字段为1或`"true"`
- generated_at无timezone、无效字符串、null
- phase/schema/command缺失或错误

所有情况必须无traceback、exit1、本次FAILED/passed=false。

### 5. 测试与正式 Evidence 完全隔离

- `main()`/orchestrator接受显式 `evidence_dir`、`out/current marker`或 EvidenceStore依赖。
- 所有 fake runner测试只使用 pytest `tmp_path`。
- 删除 `TestEvidenceRestore`；测试不应需要恢复正式 evidence。
- 新增测试：运行整个 metrics契约测试文件前后，`docs/P13-2-evidence` 三份正式文件 SHA完全不变。
- 正式 evidence只能由显式正式 CLI命令更新。

### 6. 必须通过的 Commander 负例

1. **Pre-commit tamper**：pack gate发布后、metrics commit前把其passed改false；main必须exit1，本次无绿色commit。
2. **Metrics publish failure**：final metrics发布函数返回错误；main必须exit1且不得打印PASS。
3. **Stale-green crash**：预置旧passed=true，再输入缺mutation字段；无异常泄漏，本次marker为FAILED/passed=false且run_id已更新。
4. **Metadata mismatch**：phase/schema/command同时错误；exit1/passed=false。
5. **Post-commit tamper**：成功后修改任一gate；committed-evidence verifier必须exit1并列出SHA不匹配。
6. **Test isolation**：fake runner完整测试前后正式 evidence SHA零变化。

## 验收标准

### 语法 / 静态检查

```bash
.venv/bin/ruff check signal_miner tests scripts
git diff --check
```

### 功能验证

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_metrics_contract.py
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
```

若 verifier 使用同脚本子命令，可替换最后一条，但交付报告必须给出精确正式命令。

### 回归验证

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
git diff --check
```

正式结果继续保持23/23、34/34、2/2、1/1、5/5；不得通过更改集合让测试变绿。

### 交付前质量门禁

- 自动记录 Ruff、聚焦、全量实际测试数和退出码；报告不得手写旧数字。
- 六个 Commander负例必须来自真实生产主路径/正式 verifier，不得只比较两个SHA后宣称已阻断。
- 提供测试前后正式 evidence SHA对比JSON，全部delta为0。
- 提供正式CLI运行后current commit、run_id、artifact SHA和verifier exit code。
- 报告逐项区分“orchestrator应当阻断”和“提交后由verifier发现”，不得混称。

## 交付报告模板

```markdown
# P13-2-2-1A fix-5 交付报告

## 结论
## 修改文件
## Evidence事务状态机
## Commit前后验证流程
## RUNNING/FAILED/COMMITTED marker
## 六个Commander真实负例
## 测试隔离与正式evidence SHA零变化
## 23/34/2/1/5回归
## 正式committed-evidence verifier
## 全量回归
## 未覆盖风险
```

## 完成边界

fix-5通过仍只证明 P13-2-2-1A evidence事务与外部pack信任根工具可信。真实授权候选为0时，P13-2-2-2与校准继续冻结。

