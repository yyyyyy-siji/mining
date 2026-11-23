# P13-2-2-2A 最终验收报告：真实人工标注启动准备

验收日期：2026-07-15

结论：**通过。** fix-5 已关闭源 `near_duplicate_group_id` 缺失与非空near-duplicate group跨split两类READY假绿；P13-2-2-2A readiness工具阶段结束。

## 验收范围

- fix-5冻结契约P1、N1、N2、R1、R2、R3、D1；
- fix-4已通过的7组件batch identity、session/conversation逐行元数据和naive governance结构化失败；
- 正式无真实输入时的安全阻塞状态；
- 交付报告、正式evidence及sidecar对账；
- 聚焦与全量回归。

本次通过只评价readiness是否能安全判断启动条件，不表示真实授权候选、人工标注或校准已经完成。

## 交付物对账

| 文件 | Commander复验SHA-256 |
| --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | `b036663c4fde458c0fcbf0fdaaa7cdaa80f0a0ab355017d84bf2ef60a945cd5f` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | `78262b8aa9eb742c0cab33b292a5a11f4554d60d5b067a8497d25341a63d178e` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | `153a294e13fdc0ade19051c5eaaf0747986dba6552c6f3e4066f0906480f6797` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256` | `4588d28622b5bfd67f2c2b6f9046913e51eabcf063314256036ed6023c5ba37c` |

交付报告中的脚本、测试和evidence JSON SHA与实际文件一致。报告漏列sidecar SHA，但sidecar内容实际指向当前JSON，Commander执行`shasum -a 256 -c`得到`OK`，不存在旧hash或错误hash。

## 标准门禁

| 检查 | Commander结果 |
| --- | --- |
| 三个冻结核心用例 | 3 passed，41 deselected，exit0 |
| focused Ruff | All checks passed，exit0 |
| readiness聚焦测试 | 44 passed，exit0 |
| 全量回归 | 372 passed，3 warnings，exit0 |
| `git diff --check` | exit0 |
| 正式默认行为（`--no-publish`独立复验） | `BLOCKED_INPUT_REQUIRED / exit2 / passed=false` |
| 正式evidence verifier | `verify-evidence: PASS / exit0` |
| sidecar校验 | `real-annotation-launch-readiness.json: OK` |

全量回归的3个既有warning为Starlette弃用提示和两个AsyncMock未await提示，本阶段未新增失败。

## Commander独立行为探针

独立探针复用受控签名输入生成器，但直接调用生产 `main()`；mutation和最终断言由Commander独立定义。

| 编号 | 独立mutation | 实际结果 | 结论 |
| --- | --- | --- | --- |
| P1 | 完整受控签名输入 | `READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true`，7个batch组件齐全 | 通过 |
| N1 | 删除源candidate `smp_development_0000.near_duplicate_group_id`键 | `FAILED_INVALID_INPUT / exit1`，`group_isolation=false`，准确sample进入`missing_group_rows` | 通过 |
| N2 | development/test共享`near_duplicate_group_id=commander_ndg_cross` | `FAILED_INVALID_INPUT / exit1`，`cross_split_groups`准确列出字段、group和两个split | 通过 |
| R1 | 单条candidate缺conversation | `FAILED_INVALID_INPUT / exit1`，`group_isolation=false` | 通过 |
| R2 | governance开始时间无时区 | `FAILED_INVALID_INPUT / exit1`，`annotation_governance=false`，无unexpected | 通过 |
| R3a | 合法governance字节变化 | 保持READY，governance component SHA与batch_id均变化 | 通过 |
| R3b | 合法roles字节变化 | 保持READY，roles component SHA与batch_id均变化 | 通过 |
| R3c | `real_rejections`语义相同但字节变化 | 保持READY，rejections component SHA与batch_id均变化 | 通过 |

Commander探针顶层`all_passed=true / exit0`。

## 正式环境边界

当前正式evidence仍为：

```text
status = BLOCKED_INPUT_REQUIRED
passed = false
exit_code = 2
human_verified_count = 0
human_labels_complete = false
calibration_allowed = false
```

因此本次不能解释为“已具备真实人工标注数据”，更不能进入模型准确率评测或置信度校准。

## 非阻断交付文档观察

执行方交付报告有两项完整性遗漏：

1. 修改文件SHA表未列sidecar；
2. 冻结契约表列了governance和roles的batch变化，但漏列rejections变化。

两项均由Commander实际SHA和独立R3c探针闭环，没有错误值、假绿或行为缺陷。本次按新的返工分类规则记为“交付文档不完整”，不升级为代码返工，也不阻断阶段通过。

## 质量门禁效果

- 精确sample/group反例门禁：**本次有效**；
- 生产主路径与顶层状态一致性门禁：**本次有效**；
- 交付报告完整性门禁：**部分有效**，无错误SHA但存在漏项；
- 长期防复发效果：**尚未充分证明**，仍需满足后续10次交付零复发或20个blocker样本不超过1次。

## 最终结论

P13-2-2-2A最终通过，不再下发fix-6。下一阶段是P13-2-2-2B真实人工标注执行，但它是外部输入门禁阶段：真实授权候选、生产签名包、独立A/B标注员及裁决员未到位时，只能保持BLOCKED，不得用fixture、LLM或规则标签替代。
