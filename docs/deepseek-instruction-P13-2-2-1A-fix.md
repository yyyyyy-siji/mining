# DeepSeek 返工指令：P13-2-2-1A 测试密钥环境边界与强制 Manifest

## 任务目标

关闭 production/development 启用公开测试密钥和 fixture 无 manifest 仍 PASS 的 P0 绕过，并补齐 dataset manifest hash 绑定。

## 允许修改范围

- `signal_miner/evaluation/pack_trust.py`
- `scripts/p13_2_sign_human_task_pack.py`
- `scripts/p13_2_import_human_annotations.py`
- 两个 P13-2 annotation/pack trust mutation gate
- P13-2 pack trust及human annotation聚焦测试
- fixture signed manifest生成辅助与P13-2 evidence/操作文档

## 禁止修改范围

- 在仓库中保留可被production直接使用的默认测试密钥
- 仅依赖 `--fixture`、manifest内environment字段或用户可编辑flag判断测试环境
- fixture无manifest时把pack_trust写为passed
- 用篡改签名后的manifest冒充环境边界测试
- 生产pipeline、数据库、API、前端、LLM、Embedding、去重聚类
- 真实数据、真实人工标签、P13-2-2-2和校准

## 实现要求

### 1. Test-only密钥必须双重约束

测试密钥只能在以下条件同时成立时解析：

- 可信运行环境单一真源严格为 `test`，例如 `APP_ENVIRONMENT=test`；
- CLI显式 `--fixture`；
- manifest/task pack结构化 fixture=true；
- 测试密钥由测试进程显式注入，例如 `ANNOTATION_PACK_TEST_SIGNING_KEY`，不得存在生产可调用的内置默认值。

development、production、空环境、未知环境即使传 `--fixture` 和测试密钥也必须 FAIL/exit1，target `test_key_environment_boundary=false`。真实模式缺生产密钥仍为BLOCKED/exit2。

### 2. Manifest对所有导入强制必需

- Fixture 和 production importer 都必须提供签名 manifest。
- 无 manifest：不得运行annotation校验，不得创建store，不得 `pack_trust=true`。
- fixture test环境无manifest属于契约FAIL/exit1；production无manifest可保持BLOCKED/exit2，但状态需区分“缺manifest”与“缺key”。
- 删除或禁用“fixture manifest optional”路径。
- 现有human annotation测试和34类mutation必须先在临时目录生成合法signed fixture manifest，再传给正式 importer；不得以跳过trust维持回归绿灯。

### 3. Dataset manifest hash绑定

Pack signer必须接收明确的冻结 dataset manifest 路径，signed pack manifest至少包含：

- `dataset_manifest_path`（受控相对标识或文件名，不允许路径穿越）
- `dataset_manifest_sha256`
- dataset_id/schema/version

Importer/verifier必须从独立传入或受控位置读取实际dataset manifest，重算SHA并核对dataset_id。缺失、路径不安全、SHA不符、dataset_id不符均exit1、对应target=false。

Fixture使用P13-2冻结fixture dataset manifest；真实模式未来使用授权数据新版本manifest。不得手写hash常量自证。

### 4. 修复Mutation真实性

新增或改造正式CLI mutation：

1. `APP_ENVIRONMENT=production + --fixture + test key`。
2. `APP_ENVIRONMENT=development + --fixture + test key`。
3. 环境缺失/未知 + `--fixture + test key`。
4. test环境fixture import无manifest。
5. test环境fixture使用合法manifest后篡改pack并重签普通SHA、但不持有正确HMAC。
6. dataset manifest内容变化。
7. dataset manifest SHA在pack manifest中被改但签名未更新。
8. dataset manifest路径穿越/绝对路径。
9. dataset_id与dataset manifest不一致。
10. annotation mutation gate如果漏传manifest必须整体失败。

环境边界mutation必须通过子进程真实env触发，使用签名有效、内容未篡改的manifest；禁止通过制造陈旧签名获得exit1。

每条计数mutation仍须：child exit1、同次target存在、target passed=false。exit2只用于真实缺生产密钥/授权数据的readiness invariant。

### 5. 机器证据顶层一致性

`pack-trust-contract-metrics.json` 必须包含：

- fixture test环境签名与导入结果
- production/development测试密钥拒绝结果
- fixture无manifest拒绝结果
- dataset manifest实际SHA与匹配结果
- pack trust mutation聚合
- annotation mutation回归
- 状态不变量

任一关键字段false/UNKNOWN/缺失时顶层passed=false。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_pack_trust_mutation_gate.py
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/pack-trust-mutation-gate.json >/dev/null
git diff --check
```

## 强制Commander反例

在 `APP_ENVIRONMENT=production` 且无生产密钥时：

```bash
... p13_2_sign_human_task_pack.py --fixture ...
... p13_2_import_human_annotations.py --fixture ...
```

两者均不得exit0；importer不得创建store，`pack_trust`不得为true。development、空环境也必须相同。

在 `APP_ENVIRONMENT=test`、fixture=true、显式测试密钥、合法manifest和dataset manifest全部存在时，fixture工具链才允许PASS。

## 回归与状态不变量

- P13-2-2-1的task hash重算、退化κ、stage policy、34类annotation mutation不得回退。
- 真实候选仍为0。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。
- 生产无密钥保持诚实exit2/BLOCKED。

## 交付报告模板

```markdown
# P13-2-2-1A fix交付报告

## 结论
## 修改文件
## Test-only环境与密钥边界
## Fixture强制Manifest链路
## Dataset manifest hash绑定
## Commander production/development反例
## Mutation真实env证据
## Annotation回归
## 状态不变量与未覆盖风险
```

交付物：

1. `docs/acceptance-P13-2-2-1A-delivery-fix-20260713.md`
2. `docs/P13-2-evidence/pack-trust-contract-metrics.json`
3. `docs/P13-2-evidence/pack-trust-mutation-gate.json`
4. 更新后的操作说明

## 完成边界

通过仍只表示pack信任根工具可信。真实授权候选为0时，P13-2-2-2和校准继续冻结。
