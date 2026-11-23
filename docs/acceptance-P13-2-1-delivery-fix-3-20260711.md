# P13-2-1 fix-3 交付报告：白名单、pack一致性与冻结保护

## 结论

- fixture validator：**PASS**（23 checks）
- mutation gate：**PASS（40/40）**
- artifact SHA守恒：**PASS**
- 真实候选：**BLOCKED**（0 eligible, 1,257 rejected）
- 真实预标注adapter：**可注入**（fake adapter成功验证，无key时BLOCKED exit2）
- 人工标签：**NOT_STARTED**
- 校准发布：**NOT_ALLOWED**

## 修改文件

| 文件 | 变更 |
| --- | --- |
| `scripts/p13_2_generate_preannotations.py` | 删除自定义PROFILE_SIGNAL_TYPES；使用`get_profile(profile).signal_types`生产白名单；新增可注入`generate_with_adapter()`；真实adapter使用`default_llm_provider`+`{provider}_api_key` |
| `scripts/p13_2_export_annotation_pack.py` | A/B包annotator_slot逐条设A/B；content_hash=sha256(redacted_text)；manifest冻结保护(失败不写回)；`--new-dataset-version`需新路径；source/capture trim检查 |
| `scripts/p13_2_validate_goldset.py` | 新增`suggestion_signal_types`/`source_platform_contract`；pack_contract逐字段canonical比对；suggestion_contract检查fixture标志+模型名+版本；manifest_hash_valid比较capture_method_distribution |
| `scripts/p13_2_mutation_gate.py` | 新增8类mutation(33-40)：invalid signal type、AB slot none、dev content drift、single source empty、capture dist tampered、fixture disguised、blind generic model、frozen manifest conflict |
| `tests/test_p13_2_goldset_contract.py` | 新增8项测试覆盖fix-3全部行为 |
| `signal_miner/evaluation/__init__.py` | `check_blind_pack_leakage`增强：覆盖model/provider/prompt/score精确键 |

## 生产profile白名单复用

fixture预标注使用`signal_miner.pipeline.pipeline_profile.get_profile()`取得生产白名单：

| Profile | 允许的signal types | fixture实际生成 |
| --- | --- | --- |
| product_feedback | feature_request, bug_report, usability_issue, question, praise, complaint, churn_risk | feature_request(31), bug_report(2), usability_issue(5), churn_risk(1) |
| aigc_video | viral_hook, content_pattern, visual_technique, audio_strategy, engagement_trigger, platform_algorithm, topic_trend, monetization_pattern | viral_hook(33), content_pattern(1), visual_technique(2) |

**不再存在** `ui_feedback`、`content_strategy`、`editing_request`、`platform_compatibility`等非生产类型。

验证器新增`suggestion_signal_types` check：逐条检查suggestion引用sample的profile及类型，`totally_invalid`必失败。

## A/B与pack逐字段一致性

| 契约 | 状态 |
| --- | --- |
| A包 header=annotator_slot=A, 每条slot=A | PASS |
| B包 header=annotator_slot=B, 每条slot=B | PASS |
| Dev包 逐字段与candidate canonical map一致 | PASS |
| Cal包 逐字段与candidate canonical map一致 | PASS |

CANONICAL_FIELDS包含16个字段：schema_version/sample_id/raw_feedback_id/profile/source_platform/capture_method/authorization_basis/content_hash/redacted_text/redaction_applied/language/hard_case_tags/split/split_seed/annotation_mode/annotation_status。除annotator_slot按包允许受控差异外，任意字段漂移→pack_contract=false。

## source/capture完整性

| Check | 内容 | 状态 |
| --- | --- | --- |
| source_platform_contract | 每条source_platform非空、trim后非空 | PASS |
| capture_method_contract | 允许值api/manual/import/crawl | PASS |
| manifest_hash_valid | 比较capture_method_distribution | PASS |
| source_balance | max_pct <= 0.60 | PASS |

source_distribution: {internal_support:25, authorized_forum:25, licensed_corpus:25, github:25}
capture_method_distribution: {manual:25, api:25, import:25, crawl:25}

## fixture/live预标注隔离与fake adapter证据

| 检查 | 内容 |
| --- | --- |
| fixture顶层fixture_only=true | PASS |
| 每条fixture suggestion fixture_only=true, model=fixture | PASS |
| fixture_version/prompt_version含fixture但model非fixture | FAIL |
| label_status=suggestion_only, counts_as_human_verified=false | PASS |

### 可注入adapter入口

```python
async def generate_with_adapter(adapter, sample) -> dict
```

- 使用`_build_llm_adapter(settings)`复用runtime工厂
- 读取`default_llm_provider`和`{provider}_api_key`
- 无key时BLOCKED_PREANNOTATION_UNAVAILABLE exit2
- fake adapter测试：合法结构成功、signal type经白名单验证

fixture伪装为DeepSeek（model=deepseek, fixture_only=false）→ suggestion_contract=false（fixture版本号暴露）。

## 通用泄漏扫描

`check_blind_pack_leakage`覆盖精确键和规范化变体：

- model, model_name, model_version, model_id
- provider, llm_provider
- prompt, prompt_version, prompt_template
- prediction, suggestion, suggested_signals
- confidence, score, self_score, calibrated_confidence, model_self_score

通用`model`字段（非`model_`前缀）注入blind pack → blind_pack_leakage=false。

## manifest冻结冲突前后SHA

| 场景 | 行为 | SHA变化 |
| --- | --- | --- |
| 同内容再次导出 | 复用，不更新created_at | 0 |
| 不同内容同路径 | FAIL_FROZEN_MANIFEST_MISMATCH exit1 | **0（字节不变）** |
| 损坏manifest | FAIL_FROZEN_MANIFEST_CORRUPT exit1 | **0** |
| --new-dataset-version同路径 | FAIL_NEW_VERSION_REQUIRES_NEW_PATH exit1 | **0** |

错误JSON只写stdout或--error-out，绝不写回manifest路径。

## 40类mutation target-check结果

| mutation | target check | detected |
| --- | --- | --- |
| 1-32 (fix-2原有) | 各自target | 32/32 True |
| 33. invalid_signal_type | suggestion_signal_types | True |
| 34. ab_slot_none | pack_contract | True |
| 35. dev_pack_content_drift | pack_contract | True |
| 36. single_source_empty_synced | source_platform_contract | True |
| 37. capture_dist_tampered | manifest_hash_valid | True |
| 38. fixture_disguised_as_deepseek | suggestion_contract | True |
| 39. blind_generic_model_field | blind_pack_leakage | True |
| 40. frozen_manifest_sha_invariant | manifest_identity | True |

**40/40 detected.** 每项target check明确存在且passed=false。

## Artifact SHA守恒

| 命令 | 变化artifact数 | passed |
| --- | ---: | --- |
| 聚焦测试 (28项) | 0 | True |
| Mutation gate (40项) | 0 | True |

## 真实DB导出与P13-1回归

| 项 | 值 |
| --- | --- |
| 真实DB状态 | BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES |
| eligible | 0 |
| rejected | 1,257 |
| 拒绝原因 | missing_or_invalid_authorization: 1,257; missing_source_platform: 1,257 |
| P13-1行为探针 | PASS |
| Ruff | PASS |
| 聚焦测试 | 28 passed |
| 全量回归 | 224 passed, 3 warnings |
| git diff --check | PASS |

## content_hash契约

`content_hash = sha256(redacted_text)`，manifest的content hash list确实对应标注员看到的脱敏文本。

## 未覆盖风险

- 真实预标注需要联网调用真实LLM adapter，Commander验收不要求联网，fake adapter路径已覆盖。
- P13-2-2继续冻结。
