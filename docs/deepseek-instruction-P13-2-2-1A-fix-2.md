# DeepSeek 返工指令：P13-2-2-1A fix-2 Dataset Manifest强制消费与证据同次聚合

## 任务目标

关闭省略实际dataset manifest仍能导入的P0绕过；删除fixture无manifest mutation的exit2特殊放行；让contract metrics严格来自同次真实gate。

## 允许修改范围

- `signal_miner/evaluation/pack_trust.py`
- `scripts/p13_2_import_human_annotations.py`
- `scripts/p13_2_pack_trust_mutation_gate.py`
- pack trust及human annotation聚焦测试/辅助脚本
- pack trust evidence、操作说明和fix-2交付报告

## 禁止修改范围

- 回退production/development/空环境测试密钥拒绝
- 让dataset manifest参数保持可选并仅靠manifest内SHA自证
- 为任何计数mutation覆写detected或接受exit2
- 手工维护contract metrics旧数字
- 生产pipeline、数据库、API、前端、LLM、Embedding、真实数据和后续阶段

## 实现要求

### 1. Dataset manifest必须强制提供并实际验证

- Signer和Importer的 `--dataset-manifest` 对fixture/production均为required。
- Importer在读取annotation、建立task index或创建store前检查文件存在。
- Verifier禁止 `dataset_manifest_path=None` 跳过；缺失必须 `FAIL_MISSING_DATASET_MANIFEST/exit1`，`pack_trust=false`。
- 必须重算实际文件SHA、解析dataset_id/schema/version，并与signed pack manifest字段核对。
- 声明路径与实际传入文件的受控身份规则必须明确；路径穿越、绝对路径、文件名/标识不匹配均失败。

新增正式CLI mutation：

1. signed pack manifest合法，但import省略`--dataset-manifest`。
2. 参数指向不存在文件。
3. 参数指向同dataset_id但不同内容文件。
4. 实际文件名/受控标识与signed声明不匹配。

每条exit1、同次pack_trust存在且false、store不变。

### 2. Fixture无pack manifest必须exit1

- `APP_ENVIRONMENT=test + --fixture` 但缺 `--manifest` 属于输入契约错误：`FAIL_MISSING_PACK_MANIFEST/exit1`。
- production缺manifest可以作为readiness/BLOCKED exit2，但不得计入mutation分母。
- `test_env_fixture_no_manifest_rejected` 必须走统一 `run_mutation/_evaluate_detection()` 或完全等价的统一函数。
- 禁止自定义 `detected = exit != 0`、禁止检查后覆写detected。

所有计数mutation必须严格满足：

```text
child_exit == 1
target check exists
target.passed == false
detected == true
```

### 3. Contract metrics同次聚合

新增正式聚合脚本或在pack trust gate中原子生成：

- 运行/读取本次pack trust gate、annotation gate和状态证据。
- `total_mutations/detected_count/invariant_count` 从实际JSON解析，不手写。
- 精确校验结果集合、数量、每行严格契约。
- contract metrics中的数字必须与mutation JSON完全一致。
- 任一文件缺失、旧时间戳/运行ID不一致、字段矛盾、20/21漂移时顶层passed=false并非0。

建议增加同次 `run_id` / `generated_at` 并在两个证据间交叉核对。

### 4. 元负例

至少证明：

- 任一计数mutation exit2时聚合器FAIL。
- mutation JSON为20但contract metrics写21时FAIL。
- readiness invariant数量漂移时FAIL。
- dataset manifest检查被monkeypatch/跳过时正式反例FAIL。
- 缺实际dataset manifest却pack_trust=true时聚合器FAIL。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_pack_trust_mutation_gate.py
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_2_pack_trust_contract_metrics.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
python3 -m json.tool docs/P13-2-evidence/pack-trust-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/pack-trust-mutation-gate.json >/dev/null
git diff --check
```

若聚合脚本采用其他明确名称，可替换命令，但必须作为独立正式CLI交付。

## Commander强制反例

使用合法signed fixture pack manifest，但导入命令省略 `--dataset-manifest`：

```text
expected exit=1
status=FAIL_MISSING_DATASET_MANIFEST
pack_trust.passed=false
store不存在或SHA不变
```

Fixture test环境省略pack manifest：同样exit1，不得exit2，不得特殊计作detected。

## 回归要求

- production/development/空/staging环境 `--fixture + test key`继续exit1。
- test环境缺测试密钥、production缺生产密钥继续exit2 readiness invariant。
- 合法test fixture必须同时提供两个manifest、签名和测试密钥后PASS。
- P13-2-2-1的34类annotation mutation、task hash重算、退化κ、stage policy不回退。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`。

## 交付报告模板

```markdown
# P13-2-2-1A fix-2交付报告

## 结论
## 修改文件
## Dataset manifest强制消费
## Fixture缺manifest统一exit1
## Mutation统一判定证据
## Contract metrics同次聚合
## Commander反例
## 环境边界与annotation回归
## 状态不变量
```

交付文件：`docs/acceptance-P13-2-2-1A-delivery-fix-2-20260713.md`。

## 完成边界

本fix通过仍只表示pack信任根工具可信。真实授权候选为0时，P13-2-2-2与校准继续冻结。
