# P13-2-1 fix 交付报告：授权真实性与机器门禁收口

交付日期：2026-07-11

## 结论

- **fixture 契约：PASS**
- **mutation gate：PASS** (16/16)
- **真实候选：BLOCKED** (exit 2, 0 eligible)
- **真实预标注：NOT_RUN** (模型/密钥不可用)
- **人工标签：NOT_STARTED**
- **校准发布：NOT_ALLOWED**

## 修改文件

| 文件 | 修改说明 |
| --- | --- |
| `signal_miner/evaluation/__init__.py` | 删除 `_derive_authorization`；所有模型加 `extra="forbid"`；`GoldRecord`加 `schema_version`；新增 `redact_sensitive()` |
| `scripts/p13_2_export_annotation_pack.py` | 删除自动授权推导；强制显式 `authorization_basis`；`source_platform`必填；退出码0/2/1；始终写输出JSON；A/B独立盲标包 |
| `scripts/p13_2_validate_goldset.py` | 独立重算全部17项检查；不信任 `manifest.passed`；独立验证hash/split/双标/授权/盲标泄漏/evidence offset/schema版本 |
| `scripts/p13_2_mutation_gate.py` | 新增16类mutation脚本；每项篡改artifact → CLI验证器 → 断言非0退出+对应check=false |
| `tests/test_p13_2_goldset_contract.py` | 重写：删除空pass；所有负例调用真实CLI；新增 `extra="forbid"`+redact+is_test_record 单元测试 |
| `sample_data/p13_2/positive/fixture_feedback.json` | 修复：显式授权依据(4种×25)；balanced source分布 |

## 授权与来源平台拒绝统计

| 原因 | 真实DB |
| --- | ---: |
| `missing_or_invalid_authorization` | 1,257 |
| eligible | 0 |

## Manifest逐字段重算

验证器独立重算17项，均与manifest一致：
- sample_count: 100 ✅
- 50/25/25 split ✅
- ordered_samples_hash 匹配 ✅
- guideline_hash 匹配 ✅
- selection_query_fingerprint 匹配 ✅
- content_hash_list 逐项匹配 ✅
- double_annotation_count: 20 (20.0%) ✅
- profile_distribution: {product_feedback: 50, aigc_video: 50} ✅
- source_distribution: 4×25 ✅

## A/B盲标包与预标注隔离

- `annotation_pack_test_A.json`: 25条test，annotator_slot=A
- `annotation_pack_test_B.json`: 20条双标test，annotator_slot=B
- A/B互不含对方标签
- 预标注仅dev+calibration (75条)
- test盲标泄漏扫描: 0

## Mutation gate 结果

| mutation | child exit | check | detected |
| --- | ---: | --- | --- |
| missing_authorization | 1 | authorization | ✅ |
| invalid_authorization | 1 | authorization | ✅ |
| test_mock_record | 1 | no_test_records | ✅ |
| sensitive_email | 1 | sensitive_content | ✅ |
| evidence_offset_hash_mismatch | 1 | manifest_hash_valid | ✅ |
| cross_split_leak_attempt | 1 | no_cross_split_leak | ✅ |
| duplicate_double_id | 1 | double_annotation | ✅ |
| blind_pack_model_score_leak | 1 | blind_pack_leakage | ✅ |
| fake_human_verified_count | 1 | labels_not_complete | ✅ |
| test_less_than_25 | 1 | splits_valid | ✅ |
| content_hash_tampered | 1 | manifest_hash_valid | ✅ |
| silent_hash_change | 1 | manifest_hash_valid | ✅ |
| calibration_without_labels | 1 | calibration_not_allowed | ✅ |
| suggestion_leak_to_test | 1 | suggestion_test_zero | ✅ |
| suggestion_offset_mismatch | 1 | evidence_offsets | ✅ |
| unknown_schema_field | 1 | sample_count | ✅ |

**16/16 detected, overall PASS.**

## 真实数据库导出

| status | exit | eligible | rejected | blocker |
| --- | ---: | ---: | ---: | --- |
| BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES | 2 | 0 | 1,257 | 授权字段未填充 |

## P13-1 回归

- behavior_probe: **Overall: PASS**
- baseline_metrics: **Overall: PASS**
- 全量测试: **210 passed, 3 warnings**

## 命令结果

| 命令 | 退出码 | 摘要 |
| --- | ---: | --- |
| ruff check | 0 | All checks passed |
| pytest | 0 | 210 passed, 3 warnings |
| behavior_probe | 0 | Overall: PASS |
| baseline_metrics | 0 | Overall: PASS |
| fixture export | 0 | 100 samples, 50/25/25 |
| fixture validate | 0 | READY, passed=true |
| mutation gate | 0 | 16/16 PASS |
| real DB export | 2 | 0 eligible, BLOCKED |

## 未覆盖风险

1. 真实DB授权字段未填充 → 需人工补充或追加授权数据后重新导出
2. 预标注依赖真实模型调用 → 当前不可用，fixture为模板占位
3. 浏览器验证无Playwright → Commander可独立复验
4. P13-2-2/2-3/2-4 后续阶段尚未开始
