# DeepSeek 返修指令：P13-2-1 fix-3 白名单、pack一致性与冻结清单保护

## 任务目标

只修复fix-2剩余的8个精确缺口：生产signal type白名单、冻结manifest不破坏、A/B内部slot、pack逐字段一致性、source/capture完整性、fixture/live预标注隔离、通用模型字段泄漏和真实adapter入口。

## 允许修改范围

- `signal_miner/evaluation/`
- `scripts/p13_2_export_annotation_pack.py`
- `scripts/p13_2_generate_preannotations.py`
- `scripts/p13_2_validate_goldset.py`
- `scripts/p13_2_mutation_gate.py`
- `tests/test_p13_2_goldset_contract.py`
- `sample_data/p13_2/`
- `docs/P13-2/`、`docs/P13-2-evidence/`
- fix-3交付报告

## 禁止修改范围

- pipeline提取、runner、去重、聚类、资产生成
- LLM adapter实现、生产prompt、数据库、迁移、API、前端
- P13-1已通过逻辑
- P13-2-2及后续阶段

## 实现要求

### 1. signal type白名单必须使用生产单一真源

- 删除`PROFILE_SIGNAL_TYPES`自定义列表。
- 通过`signal_miner.pipeline.pipeline_profile.get_profile(profile).signal_types`取得允许类型。
- fixture关键词映射的结果必须属于该集合；无匹配时只能选择该profile集合内的确定性类型。
- 定义严格SuggestionSignal schema，`signal_type`必须经过profile白名单验证。
- validator新增`suggestion_signal_types`check，逐条检查suggestion引用sample的profile及类型。

必须证明以下类型失败：

- product：`ui_feedback`
- AIGC：`content_strategy`、`editing_request`、`platform_compatibility`
- 任意profile：`totally_invalid`

### 2. A/B与assisted pack逐字段一致

- 导出A包时，每条副本`annotator_slot="A"`；B包为`"B"`。
- 验证器A包只接受A、B包只接受B，不接受none。
- dev/cal pack的slot保持none。
- 建立candidate canonical map。每个pack样本除允许的slot差异外，`schema_version/sample_id/raw_feedback_id/profile/source_platform/capture_method/authorization_basis/content_hash/redacted_text/redaction_applied/language/hard_case_tags/split/split_seed/annotation_mode/annotation_status`必须逐字段一致。
- 任意正文、来源、profile、hash或mode漂移时`pack_contract=false`。

### 3. source/capture完整性

- 新增`source_platform_contract`：每条source platform必须为非空、去除空格后仍非空的字符串。
- `capture_method_contract`继续校验允许值。
- `manifest_hash_valid`必须同时比较`source_distribution`和`capture_method_distribution`。
- 两种分布均从candidate独立重算，不接受manifest自述。

### 4. fixture/live suggestion不可互相伪装

validator新增检查：

- fixture证据文件顶层`fixture_only=true`。
- 每条fixture suggestion必须`fixture_only=true`且`suggestion_model="fixture"`。
- 若顶层标记为live，则每条不得`fixture_only=true`，模型/provider/version必须非空，并有独立运行状态证据。
- `counts_as_human_verified`必须为false；`label_status`必须为`suggestion_only`。
- suggestion schema禁止未知字段并验证evidence结构。

将fixture改名为DeepSeek、删除fixture flag或把人工计数flag设true，必须`suggestion_contract=false`。

### 5. 通用泄漏字段扫描

`check_blind_pack_leakage`至少覆盖键名的精确或规范化变体：

- `model`、`model_name`、`model_version`
- `provider`、`llm_provider`
- `prompt`、`prompt_version`
- `prediction`、`suggestion`
- `confidence`、`score`、`self_score`、`calibrated_confidence`

同步更新blind/dev/cal检查。不得只依赖blind hash，因为攻击者可以同时更新hash。

### 6. 实现真实adapter入口

- 使用项目真实配置字段：`default_llm_provider`及对应`deepseek_api_key/openai_api_key/google_api_key/qwen_api_key/minimax_api_key`。
- 复用现有adapter类，不修改adapter本身。
- 把核心逻辑实现成可注入函数，例如`async generate_with_adapter(adapter, sample)`，测试使用fake adapter验证：
  - 合法结构成功；
  - 非法JSON失败；
  - 非法signal type失败；
  - adapter异常返回FAIL/BLOCKED且不生成部分伪结果。
- 无对应密钥时保持`BLOCKED_PREANNOTATION_UNAVAILABLE/exit2`。
- 有配置时不得无条件抛出“No adapter implemented”。
- Commander验收不要求真实联网成功，但代码路径必须可由fake adapter完整执行。

### 7. 冻结manifest绝不被失败路径修改

- manifest存在且JSON损坏：exit1，原文件字节不变。
- manifest存在且dataset/ordered hash不一致：exit1，原文件字节不变。
- 错误信息写stdout或独立`--error-out`，禁止写回manifest。
- 相同输入、相同路径再次导出：manifest完整SHA-256和字节完全不变。
- `--new-dataset-version`必须要求新的manifest路径；禁止覆盖已有冻结清单。
- 测试必须保存before bytes/SHA，执行冲突导出后断言after完全一致。

### 8. 脱敏hash契约收口

- `content_hash`定义为`sha256(redacted_text)`，保证manifest的content hash list确实对应标注员看到的文本。
- 如需保留原文去重指纹，新增不含正文的`source_content_hash`，不得把原文写入标注包。
- 脱敏成功后再次扫描；仍含敏感模式才拒绝。

## 精确mutation增量

在现有32类基础上新增以下8类，且指定target check必须false：

33. `ui_feedback/content_strategy/totally_invalid` → `suggestion_signal_types`
34. A/B内部slot为none或相反slot → `pack_contract`
35. dev pack正文与candidate不同 → `pack_contract`
36. 单条source platform为空并同步篡改manifest分布 → `source_platform_contract`
37. manifest capture method分布篡改 → `manifest_hash_valid`
38. fixture改名为DeepSeek/fixture_only=false → `suggestion_contract`
39. blind pack加入通用`model`并同步更新blind hash → `blind_pack_leakage`
40. 冻结manifest冲突导出后SHA变化 → `manifest_freeze`或独立export gate

mutation gate至少40/40。不得以其他check失败替代指定target。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_goldset_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_validate_goldset.py
.venv/bin/python scripts/p13_2_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
git diff --check
```

期望：

- 正例validator exit0；
- mutation gate≥40/40，所有target check存在且false；
- 聚焦/全量/mutation运行后，除命令声明输出外artifact SHA零变化；
- A/B内部slot分别精确A/B；
- fixture suggestion全部属于生产profile白名单；
- 默认真实预标注：无key时exit2，有fake adapter时成功完成结构验证；
- 冻结manifest冲突前后完整SHA-256相同；
- 真实数据库仍可诚实BLOCKED。

## 交付物

1. `docs/acceptance-P13-2-1-delivery-fix-3-20260711.md`
2. 更新后的metrics、mutation gate、real export和artifact SHA证据
3. fake adapter成功/失败机器证据
4. manifest freeze before/after SHA证据

## 交付报告模板

```markdown
# P13-2-1 fix-3交付报告：白名单、pack一致性与冻结保护

## 结论

## 生产profile白名单复用

## A/B与pack逐字段一致性

## source/capture完整性

## fixture/live预标注隔离与fake adapter证据

## manifest冻结冲突前后SHA

## 40类mutation target-check结果

## Artifact SHA守恒

## 真实DB导出与P13-1回归

## 未覆盖风险
```

## 完成边界

fix-3通过只代表P13-2-1基础设施可信，不代表真实人工金标、评测指标或校准完成。P13-2-2在Commander最终验收前继续冻结。
