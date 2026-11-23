# P13-2-2-1 最终验收报告：人工标注接入与一致性工具

验收日期：2026-07-13

结论：**通过。**

本结论只表示 fixture 隔离、人工标签导入、A/B 一致性、分歧状态和本地冻结 task 完整性工具达到阶段要求，不表示已有真实人工金标，也不解除 P13-2-2-2、校准或后续阶段的前置条件。

## 验收范围

- fixture 与真实人工标签来源隔离。
- 人工 annotation schema、task identity、导入幂等和冲突拒绝。
- Assisted-review 与 blind A/B 隔离。
- Cohen's κ、退化 κ、双标比例和分歧裁决状态。
- calibration stage policy。
- Importer 结构化 target checks 与 mutation gate 防假阳性。
- pack/task/annotation fixture 一致性及 task hash 消费端重算。

## 独立验证结果

| 项目 | Commander 结果 |
| --- | --- |
| Ruff | PASS，exit 0 |
| 聚焦测试 | PASS，43 passed |
| 全量回归 | PASS，267 passed，3 warnings |
| annotation mutation gate | PASS，34/34 mutations |
| readiness invariant | PASS，1/1；零真实候选 exit 2/BLOCKED |
| mutation meta-negative | PASS，5/5 |
| P13-1 behavior probe | PASS |
| P13-2 goldset validator | PASS / READY（fixture） |
| Evidence JSON | 两份均可解析 |
| `git diff --check` | PASS |

## Commander 独立反例

### 整包 fixture 翻转并保留旧 hash

构造：复制 fixture task packs；把目标 pack 顶层及全部 task 的 `fixture` 从 true 改为 false；保留旧 task hashes；annotation 使用普通 ID、`fixture=false` 和旧 hash。

结果：

```json
{
  "exit": 1,
  "status": "FAIL_VALIDATION",
  "passed": false,
  "dataset_identity": false,
  "error": "task_hash_recompute_mismatch",
  "store_exists": false
}
```

### task 与 annotation 同步伪造同一个 hash

构造：task 和 annotation 的 task hash 同时改为相同的 64 位假值。

结果：exit 1、`dataset_identity=false`，expected hash 独立重算发现不一致，store 未创建。

这证明 importer 不再使用两个同源字段相等作为完整性证据。

## 状态不变量

- `status=FIXTURE_PASS`
- `fixture_count=120`
- `real_count=0`
- `human_verified_count=0`
- `human_labels_complete=false`
- `calibration_allowed=false`
- 真实候选为0，继续 `BLOCKED_WAITING_AUTHORIZED_DATA/exit2`

## 回归确认

- 退化全 true / 全 false κ 不能进入 READY。
- calibration policy=true、缺失、类型错误均失败。
- annotation 普通 ID / UUID 不能绕过 fixture task 来源。
- Importer mutation 从同次结构化报告读取 target check。
- exit 1但target为true、缺失或仅无关check失败时不计 detected。
- P13-1置信度与Embedding熔断行为未回退。

## 最终结论

P13-2-2-1 自本报告起关闭，fix-4 验收通过。此前高频的“验证脚本假阳性”和“fixture来源伪装”在本次确定性反例中没有复发；但只形成一个成功样本，长期有效性仍未达到连续10次零复发或20个 blocker 样本不超过1次的证明阈值。

## 后续边界

当前不可启动真实 P13-2-2-2：没有真实授权候选和人工标签。下一步先建立独立于 task 内容的 pack 外部信任根，解决“能够同时改字段并重新计算普通 SHA 的改包者仍可绕过”这一已披露风险；完成后等待真实授权数据和人工标注资源。
