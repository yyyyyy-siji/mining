# P13-2-2-1A Commander 独立验收报告：人工任务包外部信任根

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- HMAC-SHA256 manifest 的基础生成、签名和文件篡改检测路径存在。
- 生产模式不带 `--fixture` 且缺少 `ANNOTATION_PACK_SIGNING_KEY` 时 exit 2/BLOCKED。
- Ruff：PASS。
- Pack trust 聚焦测试：28 passed。
- Pack mutation gate：脚本报告 21/21、1/1 invariant。
- Annotation mutation gate：34/34、1/1、5/5。
- 全量回归：295 passed，3 warnings。
- `git diff --check`：PASS。

## 阻断问题

### P0-1：公开 fixture 测试密钥可在 production 环境启用

位置：

- `scripts/p13_2_sign_human_task_pack.py`
- `scripts/p13_2_import_human_annotations.py`
- `signal_miner/evaluation/pack_trust.py::resolve_signing_key()`

问题：测试密钥路径只由命令行 `--fixture` 决定，没有检查运行环境是否为 test。任意 production/development 进程都能自行添加该 flag 并启用仓库内公开密钥。

Commander 独立反例在 `APP_ENVIRONMENT=production`、无生产签名密钥下运行：

```json
{
  "fixture_sign_exit": 0,
  "fixture_sign_status": "SIGNED",
  "fixture_only": true,
  "signer_key_id": "fixture-test-key-v1"
}
```

任务书要求 test-only 路径必须同时满足 `environment=test` 和 `fixture=true`。当前实现违反该硬边界。

影响：公开测试密钥可被非测试环境调用，签名不再证明来自受控发布者。

### P0-2：fixture 模式无 manifest 仍把 pack trust 标为通过

位置：`scripts/p13_2_import_human_annotations.py::_verify_pack_trust()`。

问题：`is_fixture=true` 且未传 `--manifest` 时直接返回空错误列表，随后 `pack_trust.passed=true`。这不是“验证通过”，而是完全未验证。

Commander 在 `APP_ENVIRONMENT=production` 下使用 `--fixture` 且不提供 manifest：

```json
{
  "exit": 0,
  "status": "IMPORTED",
  "passed": true,
  "pack_trust": {"passed": true},
  "added": 120,
  "store_created": true
}
```

影响：本阶段声称建立的外部信任根在现有 fixture 主链路中是可选项。测试和 annotation mutation gate 继续走无 manifest 路径，无法证明信任根与既有导入链真正集成。

### P0-3：`dev_mode_test_key_flag` mutation 没有测试环境边界

该 mutation 只在已签名 manifest 中追加 `environment=development` 和 `allow_test_key=true`，却不重新签名。任何字段变化都会因旧签名失效而 exit 1，因此它只能证明“修改签名载荷会失败”，不能证明 development 环境无法启用测试密钥。

实际 production 环境正式 CLI 反例已经证明测试密钥可启用，所以 evidence 中对应 detected=true 是错误目标下的假绿。

验收要求：mutation 必须使用未篡改、签名有效的 fixture manifest，在真实子进程环境 `APP_ENVIRONMENT=development` 和 `production` 下调用 signer/importer `--fixture`，由明确的 `test_key_environment_boundary=false` 命中。

### P1-1：Manifest 未绑定 dataset manifest hash

原任务要求 pack manifest 包含并验证 `dataset manifest hash`。实际代码、测试和交付报告均没有 `dataset_manifest_hash` 字段或验证逻辑。

影响：task packs 虽能绑定自身文件，却没有绑定产生这些任务的冻结授权 dataset manifest，数据来源链仍缺一环。

## 问题统计归类

- test-only能力在production可启用：P0。
- 验证缺失却写成passed：P0，高频假阳性再次复发。
- mutation没有运行声称的环境行为：P0，负例空壳再次复发。
- dataset来源hash缺失：P1，来源完整性链不完整。

## 复验要求

强制 signed manifest 覆盖 fixture 和 production 全部导入；测试密钥必须由 test 环境显式注入；mutation 必须改变真实子进程环境。补齐 dataset manifest hash 绑定。不得通过扩大文档说明保留可选绕过。
