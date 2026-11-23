# P13-2-1 fix-2 交付报告：独立验证器、来源平台与artifact隔离

## 结论

- fixture validator：**PASS**
- mutation gate：**PASS（32/32）**
- artifact SHA守恒：**PASS**
- 真实候选：**BLOCKED**（0 eligible, 1,257 rejected）
- 真实预标注：**BLOCKED**（BLOCKED_PREANNOTATION_UNAVAILABLE exit 2）
- 人工标签：**NOT_STARTED**
- 校准发布：**NOT_ALLOWED**

## 修改文件

| 文件 | 变更 |
| --- | --- |
| `sample_data/p13_2/positive/fixture_feedback.json` | 删除`source_type`，新增`source_platform`(4平台25各)和`capture_method`(4方式25各) |
| `scripts/p13_2_export_annotation_pack.py` | 分别读取`source_platform`和`capture_method`禁止互推；新增`--new-dataset-version`；manifest冻结语义；dev/cal pack导出；blind_pack_hash基于实际A/B包文件 |
| `scripts/p13_2_validate_goldset.py` | 完全重写：21个目标check独立重算；7类artifact强制存在；精确50/25/25 split校验；sensitive has_sensitive即失败；pack_contract验证A/B/dev/cal；blind_pack_hash独立重算；manifest_identity(dataset_id=sha256(ordered_hash)[:16]) |
| `scripts/p13_2_generate_preannotations.py` | 新增`--fixture-mode`；fixture模式标记`fixture_only=true`/`suggestion_model=fixture`；默认模式BLOCKED_PREANNOTATION_UNAVAILABLE exit 2；按profile signal type白名单生成 |
| `scripts/p13_2_mutation_gate.py` | 完全重写：32类mutation；每类传临时`--out`；读取`checks[target_check].passed`；目标check缺失/overall false/exit 2均不算detected |
| `tests/test_p13_2_goldset_contract.py` | 完全重写：所有`_export`/`_validate`强制`tmp_path`；新增A/B缺失、dataset_id篡改、sensitive+redaction_false、preannotation BLOCKED测试 |
| `signal_miner/evaluation/__init__.py` | `FrozenManifest`新增`capture_method_distribution`字段 |

## 显式来源平台与采集方式

| 维度 | 值 | 数量 |
| --- | --- | ---: |
| source_platform | internal_support | 25 |
| source_platform | authorized_forum | 25 |
| source_platform | licensed_corpus | 25 |
| source_platform | github | 25 |
| capture_method | manual | 25 |
| capture_method | api | 25 |
| capture_method | import | 25 |
| capture_method | crawl | 25 |

- 导出器分别读取`fb["source_platform"]`和`fb["capture_method"]`，禁止互推。
- 缺少任一字段分别生成`missing_source_platform`或`missing_capture_method`拒绝。
- source balance只按`source_platform`统计，capture method分布单独输出。
- 真实DB没有这两个字段，1,257条全部因`missing_or_invalid_authorization`+`missing_source_platform`拒绝。

## Manifest身份与逐字段重算

验证器独立重算以下字段并与manifest比较：

| 重算字段 | 方法 | 状态 |
| --- | --- | --- |
| `dataset_id` | `sha256(ordered_hash)[:16]` | PASS |
| `ordered_samples_hash` | `sha256("".join(sorted content_hash))` | PASS |
| `selection_query_fingerprint` | `sha256(json(ids+hashes+seed+schema+rules))` | PASS |
| `blind_pack_hash` | `sha256(json({A: a_pack, B: b_pack}))` | PASS |
| `content_hash_list` | `[s.content_hash for s in samples]` | PASS |
| `profile_distribution` | `Counter(s.profile)` | PASS |
| `source_distribution` | `Counter(s.source_platform)` | PASS |
| `splits` | `dev=50, cal=25, test=25` | PASS |
| `double_annotation_count` | `len(unique_ids)` | PASS |
| `double_annotation_ratio` | `count/n` | PASS |

Manifest冻结语义：
- 相同输入再次导出不更新`created_at`，不改变任何SHA。
- 已存在但dataset_id/ordered_hash不同：`FAIL_FROZEN_MANIFEST_MISMATCH` exit 1。
- 只有`--new-dataset-version`才允许覆盖。

## 七类artifact与A/B契约

验证器CLI显式要求且验证存在：

1. candidates.json
2. manifest.json
3. development assisted-review pack
4. calibration assisted-review pack
5. test A blind pack
6. test B blind pack
7. preannotations + annotation guideline

| 契约 | 验证内容 | 状态 |
| --- | --- | --- |
| A包 | header=annotator_slot=A, 25条=all test, 每条slot=A | PASS |
| B包 | header=annotator_slot=B, 恰好=double_ids∩test, 每条slot=B | PASS |
| A/B隔离 | A=25条, B=double_ids子集 | PASS |
| Dev包 | 成员=development split, mode=assisted_review, 无prediction字段 | PASS |
| Cal包 | 成员=calibration split, mode=assisted_review, 无prediction字段 | PASS |
| A/B leakage | model_self_score/prediction/suggestion零泄漏 | PASS |

## 真实预标注 / fixture隔离

| 路径 | 行为 |
| --- | --- |
| `--fixture-mode` | 确定性模板，`fixture_only=true`，`suggestion_model=fixture`，不使用deepseek名称 |
| 默认（无--fixture-mode） | `BLOCKED_PREANNOTATION_UNAVAILABLE` exit 2，不生成模板 |

Fixture模式suggestion按profile signal type白名单生成：
- product_feedback: feature_request, bug_report, ui_feedback
- aigc_video: content_strategy, editing_request, platform_compatibility

75条suggestion（50 dev + 25 cal），0条test。

## Mutation target-check结果

每个mutation子进程使用临时`--out`，从临时metrics JSON读取`checks[target_check].passed`。

| mutation | target check | child exit | check exists | target passed | detected |
| --- | --- | ---: | --- | --- | --- |
| missing_authorization | authorization | 1 | True | False | True |
| invalid_authorization | authorization | 1 | True | False | True |
| test_mock_record | no_test_records | 1 | True | False | True |
| sensitive_email | sensitive_content | 1 | True | False | True |
| evidence_offset_unicode | evidence_offsets | 1 | True | False | True |
| cross_split_leak | no_cross_split_leak | 1 | True | False | True |
| duplicate_double_id | double_annotation | 1 | True | False | True |
| blind_pack_model_score_leak | blind_pack_leakage | 1 | True | False | True |
| fake_human_verified_count | labels_not_complete | 1 | True | False | True |
| split_49_26_25 | splits_valid | 1 | True | False | True |
| content_hash_tampered | manifest_hash_valid | 1 | True | False | True |
| dataset_id_tampered | manifest_identity | 1 | True | False | True |
| calibration_without_labels | calibration_not_allowed | 1 | True | False | True |
| suggestion_leak_to_test | suggestion_contract | 1 | True | False | True |
| suggestion_offset_mismatch | evidence_offsets | 1 | True | False | True |
| unknown_schema_field | schema_validation | 1 | True | False | True |
| sensitive_redaction_false | sensitive_content | 1 | True | False | True |
| ab_packs_missing | files_exist | 1 | True | False | True |
| dataset_id_zero | manifest_identity | 1 | True | False | True |
| blind_pack_hash_tampered | manifest_hash_valid | 1 | True | False | True |
| double_ratio_tampered | double_annotation | 1 | True | False | True |
| annotation_modes_tampered | annotation_modes | 1 | True | False | True |
| schema_version_tampered | schema_validation | 1 | True | False | True |
| suggestion_unknown_sample | suggestion_contract | 1 | True | False | True |
| preannotations_missing | files_exist | 1 | True | False | True |
| b_pack_header_a_cleared | pack_contract | 1 | True | False | True |
| split_49_26_25_v2 | splits_valid | 1 | True | False | True |
| source_platform_missing | source_balance | 1 | True | False | True |
| dev_pack_missing | files_exist | 1 | True | False | True |
| ordered_hash_tampered | manifest_hash_valid | 1 | True | False | True |
| capture_method_invalid | capture_method_contract | 1 | True | False | True |
| profile_minimum_violation | profile_minimum | 1 | True | False | True |

**32/32 detected.** 每项target check明确存在且passed=false。无overall fallback。BLOCKED exit 2不算detected。

## Artifact SHA守恒

| 命令 | 变化的artifact | passed |
| --- | ---: | --- |
| 聚焦测试 (20项) | 0 | True |
| Mutation gate (32项) | 0 | True |

`artifact-sha-invariance.json`包含执行前后的SHA-256对比。除mutation gate自身输出`mutation-gate.json`外，所有交付artifact零变化。

## 真实数据库导出

| 项 | 值 |
| --- | --- |
| 状态 | BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES |
| exit code | 2 |
| eligible | 0 |
| rejected | 1,257 |
| 拒绝原因 | missing_or_invalid_authorization: 1,257; missing_source_platform: 1,257 |

真实DB无`authorization_basis`和`source_platform`字段，全部诚实拒绝。

## P13-1回归

- Ruff：PASS
- 聚焦测试：20 passed
- 全量回归：216 passed, 3 warnings
- P13-1行为探针：PASS
- git diff --check：PASS

## 未覆盖风险

- 浏览器/Playwright证据：P13-2-1无UI变更，不涉及。
- `content_hash`基于原文hash而非脱敏文本hash：当前敏感内容在资格阶段直接拒绝，redact_sensitive基本不进入正式路径。
- FrozenManifest已有`capture_method_distribution`但验证器尚未将其纳入manifest_hash_valid比较（已独立验证capture_method_contract check）。
- P13-2-2继续冻结。
