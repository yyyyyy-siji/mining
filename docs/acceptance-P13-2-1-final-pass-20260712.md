# P13-2-1 最终验收报告：混合金标基础设施

验收日期：2026-07-12

结论：**通过。P13-2-1关闭，允许进入P13-2-2-1。**

## 验收范围

- 显式授权、来源平台与采集方式契约
- 脱敏候选、50/25/25冻结split和manifest身份
- development/calibration assisted-review包与test A/B blind包
- fixture/live预标注隔离、生产signal type白名单和可注入adapter入口
- 40类mutation target-check门禁
- 测试与机器证据artifact隔离
- P13-1安全能力回归

## 独立验证结果

| 验收项 | 结果 | Commander证据 |
| --- | --- | --- |
| 正例fixture validator | PASS | exit0，23个check全部true |
| 生产signal type单一真源 | PASS | 使用`get_profile(profile).signal_types`；非法类型独立负例exit1 |
| A/B内部slot | PASS | A包每条A、B包每条B；none负例`pack_contract=false` |
| Pack逐字段一致 | PASS | dev正文漂移独立负例`pack_contract=false` |
| Source/capture分离 | PASS | source平台四类、采集方式四类分别统计；空source负例失败 |
| Fixture/live隔离 | PASS | fixture伪装DeepSeek负例`suggestion_contract=false` |
| 通用模型字段泄漏 | PASS | blind包`model=deepseek`即使同步blind hash仍失败 |
| Manifest身份与冻结保护 | PASS | 内容冲突exit1，冲突前后完整SHA-256相同 |
| Fake adapter成功路径 | PASS | 合法结构成功；非法signal type抛`ValueError` |
| Mutation gate | PASS | Commander复跑40/40；每项exit1、target存在且false |
| 聚焦测试 | PASS | `28 passed`，artifact SHA变化0 |
| 全量回归 | PASS | `224 passed, 3 warnings` |
| Ruff / diff | PASS | exit0 |
| P13-1行为探针 | PASS | 低分入库、Embedding熔断、SSE终态和DB delta保持通过 |

## 真实数据状态

真实数据库导出独立复跑结果：

```json
{
  "status": "BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES",
  "passed": false,
  "eligible_count": 0,
  "rejected_count": 1257,
  "rejected_by_reason": {
    "missing_or_invalid_authorization": 1257,
    "missing_source_platform": 1257
  }
}
```

该BLOCKED是正确安全行为，不构成P13-2-1代码验收失败。它意味着后续只能建设人工标注接入工具；在用户提供可追溯授权数据前，不能声称真实金标集已开始或完成。

## 回归确认

- `human_labels_complete=false`
- `human_verified_count=0`
- `calibration_allowed=false`
- test包不含模型预测、suggestion、provider、prompt或confidence字段。
- fixture suggestion不计入人工验证数量。
- 未修改生产pipeline、去重、聚类或`calibrated_confidence`。
- 真实LLM预标注未联网执行，不被描述为READY。

## 非阻断观察

- 真实授权样本当前为0，P13-2业务评测尚未开始。
- 实际人工标注仍需用户或受授权标注人员参与；DeepSeek不能代替A/B人工标签。
- 100条是初始最低人工验证规模，不代表最终概率校准样本量充分。

## 最终结论

P13-2-1已建立可审计、可冻结、可防泄漏的混合金标基础设施，上一轮高频假阳性和artifact漂移问题在fix-3未复发。本阶段通过。

下一阶段只开放**P13-2-2-1：授权样本接入、人工标注导入与一致性工具**。在真实授权候选和人工A/B标签到位前，该阶段的业务状态必须保持BLOCKED。
