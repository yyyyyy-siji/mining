# Commander / Executor Quality Metrics

日期：2026-07-09

## 当前滚动样本

范围：P12-2 fix-4 至 fix-5 复验。

| 缺陷类别 | 次数 | 最近证据 | 状态 |
| --- | ---: | --- | --- |
| 验证脚本假阳性 / 缺少关键 `passed` 门禁 | 3 | `p12_2_api_evidence.json` 顶层 PASS，但 `browser_screenshot_without_evidence.passed` 缺失 | 未收敛 |
| 交付报告与代码事实不一致 | 2 | `acceptance-P12-2-delivery-20260708.md` 仍写 `source_captured_at: str \| None` | 未收敛 |
| 契约测试缺少负例 | 1 | 无 `not-a-date` / `invalid_source_captured_at` 测试命中 | 新增跟踪 |

## 当前判断

本轮优化门禁尚未证明有效。虽然 WorkBuddy 报告和现有测试显示通过，但更严格的机器断言发现证据 JSON 子门禁缺失，属于重复出现的“验证脚本假阳性 / 报告漂移”类别。

## 下一轮控制措施

P12-2 fix-6 指令已升级为确定性门禁：

- 要求每个关键 `route_checks` 子项都有 `passed: true`。
- 要求新增 `invalid_source_captured_at` 负例并写入 JSON。
- 要求交付报告用 `rg` 自查过期类型描述。
- 要求严格 JSON 断言命令作为验收标准。
