# P13-2-1 fix-2 复验报告：独立验证器、来源平台与artifact隔离

验收日期：2026-07-11

结论：**不通过，需要fix-3。P13-2-2继续冻结。**

## 已通过项

- source platform与capture method已在fixture和export主路径分字段读取，未再直接互相赋值。
- 32类mutation gate已使用临时metrics读取指定target check；Commander复跑确认32/32的记录格式、exit=1和target=false成立。
- 聚焦测试`20 passed`，测试前后所有P13-2 artifact SHA变化数为0。
- mutation gate除自身输出外，其他artifact SHA变化数为0。
- Ruff、`git diff --check`、全量回归`216 passed, 3 warnings`通过。
- P13-1行为探针通过。
- 正例验证器21项check全部通过；真实数据库仍诚实BLOCKED，0 eligible / 1,257 rejected。
- 默认预标注不再伪造DeepSeek结果；不可用时返回`BLOCKED_PREANNOTATION_UNAVAILABLE`和exit2。

上述改进说明fix-2门禁部分有效，但仍存在未纳入32类mutation的关键契约漏洞。

## 阻断问题

### P0-1：fixture预标注使用不存在于生产profile的signal type

位置：`scripts/p13_2_generate_preannotations.py`

实际生成类型：

```text
bug_report
content_strategy
feature_request
platform_compatibility
ui_feedback
```

生产单一真源：

- `product_feedback`允许：`feature_request`、`bug_report`、`usability_issue`、`question`、`praise`、`complaint`、`churn_risk`。
- `aigc_video`允许：`viral_hook`、`content_pattern`、`visual_technique`、`audio_strategy`、`engagement_trigger`、`platform_algorithm`、`topic_trend`、`monetization_pattern`。

`ui_feedback`、`content_strategy`、`editing_request`、`platform_compatibility`均不是当前profile白名单类型。验证器没有检查suggested signal type，Commander将任一suggestion改为`totally_invalid`仍得到exit0 / passed=true。

影响：金标辅助工具会向标注员提供与生产提取契约冲突的标签，污染后续人工金标和评测。

验收要求：不得在评测模块复制一套自定义白名单；必须读取`signal_miner.pipeline.pipeline_profile.get_profile(profile).signal_types`并逐条验证。

### P0-2：冻结manifest在拒绝覆盖时反而被破坏

位置：`scripts/p13_2_export_annotation_pack.py:327-351`

问题：检测到同路径manifest与新内容不同时，脚本先构造`FAIL_FROZEN_MANIFEST_MISMATCH`，然后把该错误JSON写回原manifest路径，再exit1。manifest损坏时也通过`except: pass`静默覆盖。

独立证据：第一次导出成功后修改一条fixture正文，再对同manifest路径导出：

- 第二次exit=1；
- 原manifest SHA发生变化；
- 原冻结清单被替换为错误状态JSON。

影响：所谓“冻结清单”在检测到冲突时会丢失，破坏审计和可复现性。

验收要求：任何拒绝、解析失败或内容不一致都不得修改已存在manifest的一个字节；错误结果只能写stdout、独立`--error-out`或临时文件。

### P1-1：A/B包内样本slot实际为none，报告与验证器错误放行

报告声称A包“每条slot=A”、B包“每条slot=B”。实际：

```text
annotation_pack_test_A.json header=A, sample slots={'none'}
annotation_pack_test_B.json header=B, sample slots={'none'}
```

验证器明确允许`("A", "none")`和`("B", "none")`，因此正例仍PASS。

验收要求：导出A/B副本时把每条`annotator_slot`分别设为A/B；验证器只接受精确A或B，不接受none。

### P1-2：七类artifact只核对成员ID，没有核对内容一致性

Commander把development pack中一条`redacted_text`改成任意错误内容，但保持sample ID不变，验证器仍返回READY。A/B包也没有与candidate逐字段对照，仅检查ID集合、header和部分slot。

影响：标注员实际看到的正文、来源或profile可以与冻结候选不同，manifest却仍显示通过。

验收要求：每个pack样本必须与candidate的冻结字段逐字段一致，只允许`annotator_slot`按包产生受控差异。

### P1-3：来源与capture manifest仍有可绕过字段

独立篡改结果：

- 一条candidate的`source_platform=""`，同步更新manifest source distribution后，验证器仍PASS。
- 把manifest的`capture_method_distribution`改成`{"fake":100}`，验证器仍PASS。

原因：`source_balance`只看最大占比，不检查非空；`manifest_hash_valid`没有比较capture method distribution。

验收要求：新增明确`source_platform_contract`检查非空及与pack一致；manifest hash必须比较capture method distribution。

### P1-4：fixture/live预标注隔离仍可被伪装

Commander把preannotations顶层和每条`fixture_only`改为false，并把`suggestion_model`改成`deepseek`，验证器仍PASS。blind pack加入通用字段`model="deepseek"`并同步更新blind hash后，`blind_pack_leakage`仍PASS，因为扫描器只匹配`model_`而不匹配精确`model`。

此外默认预标注代码读取不存在的`settings.llm_provider/llm_api_key`，随后无条件抛出“No pre-annotation adapter implemented”；即使项目配置了`default_llm_provider`和`deepseek_api_key`也永远BLOCKED。交付报告的“真实预标注不可用”是诚实状态，但并未完成fix-2要求的可调用adapter入口。

验收要求：fixture标志、模型名、profile类型参与`suggestion_contract`；泄漏扫描覆盖`model/provider/prompt`精确键；实现可注入的真实adapter调用入口，缺密钥才BLOCKED。

### P1-5：测试未覆盖上述关键行为

现有20项测试和32类mutation没有覆盖：

- 生产signal type白名单；
- A/B内部slot必须精确；
- pack正文与candidate一致；
- 单条source platform为空；
- capture method manifest分布篡改；
- fixture suggestion伪装成真实模型；
- 通用`model`字段泄漏；
- 冻结manifest拒绝时字节不变。

## 非阻断观察项

- `content_hash`仍基于原文而非脱敏文本；报告已如实列为风险，但与任务书“脱敏文本hash”仍不一致。
- `test_manifest_freeze_idempotent`实际使用两个不同manifest路径，只比较dataset ID，没有验证同一路径字节级幂等或冲突后SHA不变。

## 复验要求

1. 只执行`docs/deepseek-instruction-P13-2-1-fix-3.md`。
2. P13-2-2继续冻结。
3. Commander将重复本报告全部独立负例，并检查冻结manifest冲突前后完整SHA-256相等。
4. 不再扩大mutation数量掩盖问题；fix-3必须逐一覆盖上述8个精确目标行为。

## 问题统计归类

- 验证器关键契约盲区：再次复发。
- 交付报告与实际pack内容漂移：再次复发。
- 来源字段完整性与分布重算不完整：再次复发。
- 测试未覆盖真实跨artifact一致性：再次复发。
