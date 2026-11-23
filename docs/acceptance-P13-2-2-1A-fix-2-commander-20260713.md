# P13-2-2-1A fix-2 Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- 省略实际dataset manifest：exit1、`pack_trust=false`、store不创建。
- Fixture test环境缺pack manifest：exit1，不再使用exit2特殊放行。
- Pack trust的23条计数mutation均满足exit1、target存在、target=false。
- production/development/空/staging环境继续拒绝fixture测试密钥。
- Contract metrics数值已与当前gate同步为23/23、2项pack invariants、34/34 annotation。
- Ruff：PASS。
- Pack trust聚焦测试：22 passed。
- Human annotation聚焦测试：43 passed。
- 全量回归：289 passed，3 warnings。
- Pack gate、annotation gate、P13-1 behavior probe、goldset和`git diff --check`通过。

## 阻断问题

### P0-1：聚合器忽略输入gate顶层失败，仍硬编码输出passed=true

位置：`scripts/p13_2_pack_trust_contract_metrics.py`。

问题：聚合器读取了以下关键字段，却没有把它们作为失败条件：

- `pack-trust-mutation-gate.json.passed`
- `human-annotation-mutation-gate.json.passed`
- annotation `meta_negatives_passed`
- annotation `readiness_invariants_passed`

最终输出中的 `passed` 直接硬编码为 `True`。

Commander 使用临时证据文件，把annotation gate改为：

```json
{
  "passed": false,
  "meta_negatives_passed": false,
  "readiness_invariants_passed": false
}
```

其余mutation行和计数保持不变。聚合器实际结果：

```json
{
  "aggregator_exit": 0,
  "aggregator_passed": true,
  "output_annotation_gate": {
    "passed": false,
    "readiness_invariants_passed": false,
    "meta_negatives_passed": false
  }
}
```

影响：输入和输出在同一JSON内自相矛盾仍可绿灯，是本项目高频“关键字段未参与顶层passed”的确定性复发。

验收要求：任一输入gate top-level passed、invariant、meta-negative为false/缺失/非bool时，聚合器exit1且输出passed=false；不得写硬编码True。

### P1-1：所谓同次run_id没有绑定两个输入gate

交付报告称“统一run_id + generated_at绑定两个evidence文件”。实际两个gate JSON均没有 `run_id` 或 `generated_at`；聚合器读取它们以后才新建一个UUID，只写入最终contract metrics。

因此该run_id无法证明两个输入来自同次运行，也无法识别一新一旧但结构和数量恰好一致的证据。

验收要求：由单一orchestrator先生成run_id，再把同一个run_id传给并写入两个gate evidence；聚合器必须要求三者run_id精确相等，并检查生成时间、子命令退出码和输入artifact hash。

## 问题统计归类

- 关键false字段未参与顶层passed：P0，验证假阳性再次复发。
- 报告声明同次绑定但artifact无run_id：P1，报告/证据漂移再次复发。

## 复验要求

行为安全修复已通过，本轮只返修证据orchestrator及聚合器。不得改动pack trust、dataset hash或annotation业务实现。
