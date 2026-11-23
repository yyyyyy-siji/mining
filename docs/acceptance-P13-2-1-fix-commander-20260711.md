# P13-2-1 fix 复验报告：授权真实性与机器门禁收口

验收日期：2026-07-11

结论：**不通过，需要第二次返修。P13-2-2继续冻结。**

## 已通过项

- 已删除`_derive_authorization`，真实数据库1,257条记录因缺少显式授权全部拒绝，未再把采集方式伪装成授权依据。
- 必需的`real-candidate-export.json`与`real-rejections.json`已经提交；真实导出诚实返回`BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES`、退出码2、eligible=0。
- Pydantic主要模型启用了`extra="forbid"`，`GoldRecord`增加`schema_version`。
- Ruff独立执行通过。
- 聚焦测试`14 passed`，全量回归`210 passed, 3 warnings`。
- P13-1行为探针独立复跑通过。
- 基础fixture仍能生成100条、50/25/25候选，以及test A/B文件。

## 阻断问题

### P0-1：mutation gate仍是假阳性，未证明目标检查捕获了错误

位置：`scripts/p13_2_mutation_gate.py`

问题：子验证器stdout只输出`{"status":..., "passed":...}`，不包含`checks`。mutation gate读取stdout后找不到目标check，就回退到`overall_passed`：

```python
check_passed = result.get("checks", {}).get(target_check, {}).get("passed", overall_passed)
detected = r.returncode != 0 and (not check_passed or not overall_passed)
```

因此任何无关检查失败，都可以被记成目标检查已捕获。mutation 5名为Unicode evidence offset，实际只篡改manifest hash；mutation 12名为dataset冻结变化，实际也只篡改content hash list。

独立证据：mutation gate运行后报告`16/16 PASS`，但它同时把项目`goldset-contract-metrics.json`改写成`status=FAIL/passed=false`。其JSON中的`check_passed=false`并非来自目标check，而是来自overall fallback。

影响：16/16并不等于16个契约分别受到保护，复发“验证脚本假阳性”。

验收要求：每个子进程必须使用临时`--out`，mutation gate读取该机器JSON中的**指定目标check**；目标check缺失即mutation失败，不得退回overall结果。

### P0-2：验证器仍放过多项关键篡改

位置：`scripts/p13_2_validate_goldset.py`

Commander基于正例artifact独立篡改，得到：

| 篡改 | 实际结果 |
| --- | --- |
| test候选含`leak@example.com`且`redaction_applied=false` | exit 0 / passed=true |
| A/B包均不存在 | exit 0 / passed=true |
| `dataset_id`篡改 | exit 0 / passed=true |
| `blind_pack_hash`篡改 | exit 0 / passed=true |
| manifest双标ratio、annotation modes、schema version同时篡改 | exit 0 / passed=true |
| suggestion引用不存在sample | exit 0 / passed=true |
| preannotations文件不存在 | exit 0 / passed=true |
| B包改为slot A并清空samples | exit 0 / passed=true |

原因包括：

- sensitive检查错误地要求`has_sensitive(...) and redaction_applied`，flag为false时残留敏感数据反而放行。
- A/B包不存在时直接跳过，没有`files_exist/pack_contract`失败。
- 没有重算dataset ID、blind pack hash、double ratio、annotation mode mapping或manifest schema version。
- 没有验证suggestion sample引用完整性、dev/cal suggestion数量和preannotations必需存在。
- 没有验证A/B header、样本集合、slot或相互隔离。
- 只读取A/B test包，没有读取/验证development与calibration assisted-review包。

影响：金标冻结、隐私和盲标隔离仍不能由机器证据证明。

### P1-1：`source_platform`仍由`source_type`冒充

位置：`scripts/p13_2_export_annotation_pack.py:105,188-189`

问题：

- 导出资格读取`src_platform = fb.get("source_type", "")`。
- `source_platform`和`capture_method`都写入同一个`source_type`。
- fixture没有`source_platform`或`capture_method`字段，所谓四来源平衡实际是`manual/api/import/crawl`四种采集方式平衡。

影响：任务重点是数据来源真实性；当前`source_distribution`不是来源平台分布，报告“4×25来源”具有误导性。

验收要求：fixture与真实输入必须显式提供`source_platform`和`capture_method`，二者分别验证；缺少任何一个均拒绝，禁止互相推导。

### P1-2：预标注路径没有按fix指令实现，交付报告与代码不一致

位置：`scripts/p13_2_generate_preannotations.py`

问题：

- 没有`--fixture-mode`。
- 没有真实adapter调用或`BLOCKED_PREANNOTATION_UNAVAILABLE/exit 2`路径。
- 仍对所有dev/cal样本固定生成`feature_request`和“需要人工确认”模板，包括AIGC profile。
- 输出仍使用`--model deepseek`默认值，模板可能被误认为DeepSeek结果。
- 输出项没有`fixture_only=true`。

影响：该工具不能降低人工标注成本，也违反“默认路径不得伪造真实预标注”的要求。

### P1-3：测试仍会修改交付artifact，SHA守恒未实现

位置：`tests/test_p13_2_goldset_contract.py`

问题：

- `test_export_creates_candidates()`仍调用默认项目输出路径。
- `test_validate_passes()`、`test_splits()`等仍写默认`docs/P13-2-evidence/goldset-contract-metrics.json`。
- mutation gate的每个子验证器也未传临时`--out`，持续覆盖项目metrics。

独立证据：执行聚焦测试前后，以下SHA发生变化：

- `sample_data/p13_2/manifest.json`
- `docs/P13-2-evidence/goldset-contract-metrics.json`

mutation gate单独运行也改变metrics SHA，并将其留为FAIL状态。

影响：交付报告缺少要求的artifact SHA守恒表；测试全绿后机器证据可能不是交付时那一份。

### P1-4：冻结manifest没有真正防止静默覆盖

当前export每次都会用相同dataset ID和新的`created_at`覆盖manifest，没有检查已存在manifest的不可变字段，也没有显式新dataset版本机制。验证器同样不验证dataset ID是否由当前有序内容hash推导。

## 非阻断观察项

- `content_hash`仍基于原文，而任务契约要求manifest保存脱敏文本hash；当前敏感内容在资格阶段直接拒绝，因此`redact_sensitive()`基本不会进入正式候选路径。
- 验证器输出仍硬编码`human_labels_complete=false`、`human_verified_count=0`、`calibration_allowed=false`，而不是回显已验证的manifest实际值。
- 报告提到浏览器/Playwright，但P13-2-1没有UI变更，该项不属于本阶段验收。

## 复验要求

1. 只执行`docs/deepseek-instruction-P13-2-1-fix-2.md`。
2. P13-2-2、人工标注、主动学习和校准继续冻结。
3. 提交至少25类mutation的真实目标check证据、测试SHA守恒、显式source platform分布和真实预标注BLOCKED/fixture隔离证据。
4. Commander将重新运行本报告表格中的全部独立篡改，不接受mutation脚本自报替代独立复算。

## 问题统计归类

- 验证脚本假阳性 / 目标check未被真实证明：再次复发。
- 交付报告与代码事实漂移：再次复发。
- 测试污染机器证据artifact：再次复发。
- 来源平台与采集方式混淆：上一轮问题未修复。
