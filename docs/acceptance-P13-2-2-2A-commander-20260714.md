# P13-2-2-2A Commander 独立验收报告

验收日期：2026-07-14

结论：**不通过，需要返修；当前业务状态继续为 `BLOCKED_INPUT_REQUIRED`，不得进入 P13-2-2-2B。**

本次“没有真实授权输入，因此不能启动人工标注”的业务结论是诚实的；但 readiness 实现存在可确定复现的 `READY` 假绿，所以工具链本身未达到验收标准。

## 已通过项

- 正式 CLI 在当前零合格候选、无生产签名密钥、无人工角色条件下实际退出 2。
- 正式输出保持 `passed=false`、`human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。
- 未发现伪造真实任务包、人工标签或用 fixture/test key 补齐当前缺失输入。
- Ruff：通过。
- 新增聚焦测试：48 passed。
- 全量回归：通过，3 warnings。
- `git diff --check`：通过。

## 阻断问题

### P0-1：授权候选数量和逐行授权完整性未参与最终 passed，存在 READY 假绿

位置：`scripts/p13_2_real_annotation_launch_readiness.py:207-260, 615-620`。

实现直接信任导出文件自报的 `eligible_count`，不要求它等于实际候选行数或授权完整行数；发现 `authorization_incomplete_rows` 后也没有追加 error。Commander 直接调用生产 `main()` 的反例：

```json
{
  "probe": "claimed_100_actual_99_all_auth_incomplete_no_window",
  "exit_code": 0,
  "status": "READY_FOR_HUMAN_ANNOTATION",
  "passed": true,
  "eligible_count": 100,
  "authorization_complete_rows": 0,
  "authorization_incomplete_rows": 99,
  "errors": []
}
```

这正是任务书 N1 与 N3 要阻断的情况。实际 99 行、0 行授权完整，却被判定可以启动真实人工标注。

### P0-2：READY 路径没有消费真实治理配置、split/pack 文件或 1A 信任链

位置：`scripts/p13_2_real_annotation_launch_readiness.py:590-677, 819-853`。

角色、split、test packs 和 PII candidates 仅能通过标注为“for testing only”的内存 override 注入；正式 CLI 只有 candidate path 和 environment 参数。标注执行窗口、保留期限、允许访问角色完全没有实现。正式路径也没有读取 dataset manifest、pack manifest、四个已签名 pack，未验证 pack signature、dataset/task hash、精确文件集合或 A/B 访问边界。

影响有两面：真实输入到位后 CLI 仍无法安全进入 READY；而程序化调用只需注入几个未签名字典，就可绕过生产信任链得到 READY。

### P0-3：缺失输入与已提供但无效的输入统一返回 exit 2

位置：`scripts/p13_2_real_annotation_launch_readiness.py:679-700`。

任务书要求缺少外部输入为 `exit2/BLOCKED`，14 类已提供但无效的负例必须 `exit1` 且对应结构化 target=false。当前所有 errors 都返回 exit 2。Commander 注入 test blind prediction 泄漏后得到：

```json
{
  "exit_code": 2,
  "status": "BLOCKED_TEST_BLIND_LEAKAGE",
  "passed": false,
  "leakage_count": 1
}
```

这会让上层把安全违规误判为“等待用户输入”，而不是实现/数据契约失败。

### P0-4：声称覆盖的 14 类负例与实际测试不一致

位置：`tests/test_p13_2_real_annotation_launch_readiness.py:246-286, 362-405`。

- N1 名称声称“99 行但 count 写 100”，实际把 `eligible_count` 也传成 99，没有攻击计数伪报。
- N3 只断言记录了 incomplete row，没有断言 `passed=false`、`exit1` 和结构化 target=false；因此假绿仍让测试通过。
- N9 只再次测试 pseudonym 碰撞，没有测试 A 包读取 B 标签或反向访问。
- N11 被替换成“缺生产密钥”，没有执行 pack signature、dataset hash 或 task hash 篡改。
- 全部安全负例没有统一断言 `exit1`。

因此“48 passed”不能证明交付报告声称的 14 类门禁成立。

### P1-1：正式 readiness 证据字段和 SHA 不可核验

当前 JSON 缺少任务书要求的 `dataset_id`、`batch_id`、dataset manifest SHA 和 pack manifest SHA。无输入时可以为 null/NOT_PROVIDED，但字段与结构化 check 仍应存在。

SHA 出现三方不一致：

- 当前文件实际 SHA-256：`4a8603fd5347d9f7074c01bf20f8f488147860948d78f91d59a3a06d9a0e5879`
- JSON 内 `_artifact_sha256`：`8193aad9b0dfb6f9122c2b6c6f21472e817f03ed7ef41474ad53edc586f6c953`
- 交付报告记录：`c4358306305c09a8032f7bc312ebd34f444602fb5ed92ac480a35a49da8f7727`

根因是先发布、把第一次 SHA 填回 payload、再发布一次，嵌入值天然不是最终文件字节 SHA；交付报告又未与最终文件对齐。

### P1-2：当前无输入状态没有使用任务书规定的统一顶层状态

任务书“无真实输入时”的验收契约明确要求 `status=BLOCKED_INPUT_REQUIRED`。当前顶层为 `BLOCKED_INSUFFICIENT_REAL_CANDIDATES`。细分原因可以保留在 `blockers[]`，但顶层状态应保持稳定，避免上层编排需要枚举不断扩张的 BLOCKED 状态。

## 验收命令摘要

| 检查 | 结果 |
| --- | --- |
| 正式 readiness `--no-publish` | exit 2，当前业务诚实 BLOCKED |
| Ruff（新增脚本与测试） | PASS |
| 聚焦 pytest | 48 passed |
| 全量 pytest | PASS，3 warnings |
| Commander 计数/授权假绿反例 | **exit 0 / passed=true，阻断失败** |
| Commander test blind 泄漏反例 | passed=false，但错误返回 exit 2 |
| 最终 artifact SHA 对账 | **三方不一致** |
| `git diff --check` | PASS |

## 复验边界

只修 P13-2-2-2A readiness 的真实输入消费、判定、退出码、证据发布和对应契约测试。不得修改已验收的 P13-2-2-1A 业务信任链，不得生成真实人工答案，不得进入 P13-2-2-2B、P13-2-3、P13-2-4、P13-3或前端概率发布。

