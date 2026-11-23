# P13-2-2-1A 最终验收报告：外部 Pack 信任根与 Evidence 事务

验收日期：2026-07-14

结论：**通过。P13-2-2-1A 自本报告起关闭。**

## 验收范围

- 人工任务包 HMAC/manifest 外部信任根。
- Dataset manifest 强制消费与 pack/task/annotation 完整性链。
- 23/34/2/1/5 版本化精确门禁集合。
- Evidence run_id、artifact SHA、原子发布、commit前后验证与独立 verifier。
- RUNNING / FAILED / COMMITTED marker 错误传播。
- Fake runner 测试与正式 evidence 隔离。

## Commander 独立复验结果

### fix-6 两个核心反例

1. **RUNNING marker发布失败**
   - exit：1
   - gate calls：0
   - stderr：`RUNNING_MARKER_WRITE_FAILED`、`this run did not start`
   - 未打印PASS。

2. **COMMITTED与FAILED marker均发布失败**
   - exit：1
   - gate calls：2
   - 磁盘保留本次 `RUNNING/passed=false`，不是绿色结果。
   - stdout：`FAILED_MARKER_WRITE_FAILED`。
   - 不再出现 `no green metrics left` 的错误声明。

上述反例均通过Commander独立脚本调用生产 `main()`，不是仅引用执行方测试。

### 静态、测试与正式运行

| 检查 | Commander结果 |
| --- | --- |
| Ruff | PASS |
| Metrics + pack trust + annotation聚焦测试 | 104 passed（39 + 22 + 43） |
| 全量回归 | 328 passed，3 warnings |
| 正式 orchestrator | PASS / exit 0 |
| Pack mutation | 23/23 |
| Annotation mutation | 34/34 |
| Pack readiness invariant | 2/2 |
| Annotation readiness invariant | 1/1 |
| Annotation meta-negative | 5/5 |
| committed-evidence verifier | PASS / exit 0 |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | READY / passed=true |
| 三份JSON解析 | PASS |
| `git diff --check` | PASS |

正式 orchestrator 本次 run_id：`1b029804-4fa2-42c8-8c8c-ffed107da303`。

### 测试隔离

Commander在三组聚焦测试前后独立计算正式三份 evidence SHA-256，结果完全相同：`UNCHANGED=true`。Fake runner 测试不会再覆盖正式机器证据。

## 回归确认

- Dataset manifest省略/缺失继续exit1并阻止store创建。
- Fixture缺pack manifest继续exit1。
- Production/development/空/staging测试密钥边界不回退。
- Consumer独立重算task hash、fixture provenance、pack签名和dataset hash链不回退。
- 关键false字段、集合缩减、SHA竞态、stale run和marker错误均不能产生本次绿色PASS。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`继续保持。

## 最终结论

P13-2-2-1A 的工具、外部pack信任根与Evidence事务链达到本阶段验收标准。fix-6 对上一轮 marker 错误传播门禁 **本次有效**。

长期防复发仍未达到连续10次交付零复发或20个blocker样本不超过1次的统计阈值，因此后续阶段继续保留：

- 关键字段必须参与顶层passed。
- 正式子命令退出码必须参与最终决策。
- Evidence exact-set、run_id、SHA与marker readback。
- Fake/fixture不得写入真实计数或正式evidence。

## 后续阶段边界

真实授权候选当前仍为0，P13-2-2-2不能直接宣告开始或完成。下一阶段为 **P13-2-2-2A：真实授权候选批次与人工标注启动准备**。

若没有用户提供的真实授权数据、生产pack签名密钥和独立人工标注角色，P13-2-2-2A必须 `BLOCKED_INPUT_REQUIRED/exit2`；禁止用fixture、LLM标签、规则标签或测试密钥替代。

