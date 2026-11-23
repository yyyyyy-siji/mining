# DeepSeek 返工指令：P13-2-2-1A fix-6 Marker 发布错误闭环

## 任务目标

只修复fix-5剩余的marker错误传播：RUNNING marker发布失败必须在任何gate启动前阻断；FAILED marker写入结果必须被真实验证，控制台不得谎称旧绿已清除。

## 背景 / 当前问题

- `_write_running_marker()` 丢弃 `_publish_atomic()` errors；首次marker写失败后仍调用两个gate并最终exit0/COMMITTED。
- `_write_failed_marker()` 丢弃发布错误；旧COMMITTED绿色文件仍存在时，summary仍打印 `no green metrics left`。

## 允许修改范围

- `scripts/p13_2_pack_trust_contract_metrics.py` 中marker helper、main入口、失败finalize和summary
- `tests/test_p13_2_pack_trust_metrics_contract.py` 对应聚焦测试
- fix-6交付报告和机器反例证据

## 禁止修改范围

- 23/34/2/1/5版本化契约和mutation名称
- 两个mutation gate及pack trust/annotation业务规则
- committed-evidence verifier的既有校验语义
- pipeline、数据库、API、前端和后续阶段
- 用抛弃errors、`contextlib.suppress`或只检查异常代替返回值检查
- 把旧COMMITTED说成本次FAILED

## 实现要求

### 1. Marker API必须返回可判定结果

统一marker发布接口，例如：

```python
@dataclass(frozen=True)
class MarkerWriteResult:
    ok: bool
    status: str
    run_id: str
    errors: tuple[str, ...]
```

也可使用严格tuple/result对象，但必须满足：

- 不丢弃 `_publish_atomic` 返回的任何error。
- 发布后重新读取marker并验证run_id、status、passed。
- `ok=true` 只能来自实际落盘readback成功。
- 调用方必须显式检查结果。

### 2. RUNNING是启动gate的硬前置条件

正式流程：

1. 生成run_id。
2. 原子发布RUNNING marker。
3. readback验证本次run_id、status=RUNNING、passed=false。
4. 只有以上成功才允许调用gate runner。

RUNNING发布或readback任一失败：

- exit 1
- gate runner调用次数严格为0
- stderr包含结构化 `RUNNING_MARKER_WRITE_FAILED`
- 不得打印PASS

如果旧COMMITTED文件仍存在，它只能表示“上一轮最后成功”，不能声称本次已进入RUNNING。CLI退出码和错误文本必须明确本次未启动。

### 3. FAILED marker结果必须诚实

业务/commit失败后：

- 尝试原子写本次run_id的FAILED/passed=false。
- readback成功才返回 `failed_marker_written=true`。
- 若写入或readback失败，返回 `failed_marker_written=false`并附带完整errors。
- `_finalize_failed`和summary必须接收该结果。

只有 `failed_marker_written=true` 时允许输出：

```text
status: FAILED (no green metrics left)
```

否则必须输出：

```text
status: FAILED_MARKER_WRITE_FAILED
```

并明确当前磁盘marker可能仍是上一轮状态。无论哪种情况均exit1。

### 4. 必须新增的真实主路径负例

所有测试使用 `tmp_path`，不得污染正式evidence：

1. RUNNING `_publish_atomic`返回error：exit1、gate_calls=0、无PASS。
2. RUNNING写入后readback run_id错误：exit1、gate_calls=0。
3. RUNNING写入后readback status错误：exit1、gate_calls=0。
4. 预置旧COMMITTED，RUNNING写失败：exit1、gate_calls=0；错误明确本次未启动。
5. Final COMMITTED publish失败、FAILED marker成功：exit1，最终为本次run_id FAILED/passed=false。
6. Final COMMITTED publish失败、FAILED marker也失败：exit1，summary包含 `FAILED_MARKER_WRITE_FAILED`，禁止包含 `no green metrics left`。
7. FAILED marker写入后readback为旧run_id或passed=true：按marker失败处理。
8. 正向：RUNNING成功后才有gate_calls=2，最终COMMITTED/verifier PASS。

### 5. 防止测试自证

- 测试必须断言真实gate runner调用次数，而不只看最终JSON。
- 必须捕获stdout/stderr，断言PASS/FAILED文案与落盘状态一致。
- 必须调用生产 `main()`，不复制marker判定逻辑。
- 正式evidence三文件测试前后SHA保持不变。

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

### 回归验证

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
```

正式运行继续保持23/23、34/34、2/2、1/1、5/5和verifier exit0。

### 交付前质量门禁

- 交付报告必须给出8类marker负例的exit、gate_calls、marker status/run_id/passed、stdout/stderr关键行。
- 全量测试数从真实命令采集。
- 给出测试前后正式evidence SHA，delta必须为0。
- 报告必须分别声明 `failed_marker_written=true/false`，不得笼统写“无绿色metrics”。

## 交付报告模板

```markdown
# P13-2-2-1A fix-6 交付报告

## 结论
## 修改文件
## MarkerWriteResult契约
## RUNNING gate前置条件
## FAILED marker诚实状态
## 8类真实主路径负例
## stdout/stderr与落盘一致性
## 测试隔离SHA
## 正式orchestrator/verifier
## 全量回归
## 未覆盖风险
```

## 完成边界

fix-6通过仍只证明P13-2-2-1A evidence marker错误闭环可信。真实授权候选为0时，P13-2-2-2与校准继续冻结。

