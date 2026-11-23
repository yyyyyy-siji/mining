# P13-2-2-1A fix Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- `APP_ENVIRONMENT=production/development/空/staging + --fixture + test key` 均 exit 1，测试密钥环境边界已真实生效。
- Runtime 已删除内置默认测试密钥，test环境缺注入密钥时 exit 2/BLOCKED。
- Fixture 无 pack manifest 时不再导入，store 不创建，`pack_trust=false`。
- Pack manifest schema 已加入 `dataset_manifest_path` 和 `dataset_manifest_sha256`。
- Ruff：PASS。
- Pack trust聚焦测试：22 passed。
- Pack trust gate脚本报告20/20、2/2 invariants。
- `git diff --check`：PASS。

## 阻断问题

### P0-1：Dataset manifest 实际文件仍是可选参数，省略后 pack trust 通过

位置：

- `scripts/p13_2_import_human_annotations.py` 的 `--dataset-manifest` 默认空值。
- `signal_miner/evaluation/pack_trust.py::verify_manifest_file()` 仅在 `dataset_manifest_path is not None` 时重算。

问题：signed pack manifest 虽包含 dataset manifest SHA，但 importer 不要求传实际 dataset manifest。省略参数后 verifier 跳过文件读取和SHA/dataset_id独立核对。

Commander 独立正式 CLI 反例：先用合法 dataset manifest 签出 fixture pack manifest，再在导入时提供 signed pack manifest但省略 `--dataset-manifest`。

实际结果：

```json
{
  "sign_exit": 0,
  "import_without_dataset_manifest_exit": 0,
  "status": "IMPORTED",
  "passed": true,
  "pack_trust": {"passed": true},
  "store_created": true
}
```

影响：交付声称的 dataset 来源绑定只存在于签名载荷字段，没有在每次消费时强制验证实际冻结 dataset manifest。P1-1并未真正关闭。

验收要求：所有fixture/production导入必须提供实际dataset manifest；缺失时在读取annotation前exit1、`pack_trust=false`、store不变。Verifier不得在路径为None时跳过。

### P0-2：Fixture无manifest计数mutation仍用exit2特殊放行

任务书明确要求test fixture缺manifest属于契约FAIL/exit1，且所有计数mutation必须满足统一契约：exit1、target存在、target=false。

实际 gate：

- `_evaluate_detection()`正确要求exit1。
- 但 `test_env_fixture_no_manifest_rejected` 使用自定义runner，在真实结果exit2时覆盖规则，以“非exit0且store不存在”手工写`detected=true`。

机器证据实际行：`child_exit=2`、`detected=true`。

影响：mutation gate再次产生特殊放行，破坏了用于治理高频假阳性的统一判定契约。exit2应只出现在生产缺密钥、test缺注入密钥或等待真实数据的readiness invariant中。

### P1-1：Contract metrics 与本次 gate 证据漂移

实际 `pack-trust-mutation-gate.json` 为20/20、2/2；交付报告也写20/20。但 `pack-trust-contract-metrics.json` 仍保存上一次的21/21、1项invariant，同时顶层 `passed=true`。

影响：聚合证据没有从同次gate结果生成，无法作为最终通过依据。

## 问题统计归类

- 来源hash有声明但消费端可跳过：P0。
- mutation特殊放行exit2：P0，高频验证假阳性再次复发。
- 聚合metrics陈旧：P1，报告/机器证据漂移再次复发。

## 复验要求

修复范围只限：dataset manifest强制消费、fixture缺manifest exit1统一判定、contract metrics同次聚合。已经通过的真实环境边界不得回退。
