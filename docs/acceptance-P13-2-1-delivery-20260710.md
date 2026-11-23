# P13-2-1 交付报告：混合金标协议、脱敏导出、预标注隔离与冻结清单

交付日期：2026-07-10

## 结论

- **代码/fixture 门禁：PASS**
- **真实候选数据：BLOCKED**（当前 DB 不足 100 条合格记录）
- **人工标签：NOT_STARTED**
- **校准发布：NOT_ALLOWED**

## 修改文件

| 文件 | 修改说明 |
| --- | --- |
| `docs/P13-2/annotation-guideline-v1.md` | 中文标注指南：signal边界、signal_type定义、evidence区间、双标规则、隔离规则 |
| `docs/P13-2/goldset-data-contract-v1.md` | Schema契约：GoldRecord/HumanAnnotation/Suggestion/FrozenManifest所有字段 |
| `signal_miner/evaluation/__init__.py` | Pydantic模型 + 验证辅助函数 |
| `scripts/p13_2_export_annotation_pack.py` | 导出器：授权门禁、脱敏检查、确定性抽样、50/25/25 split、双标分配、冻结清单 |
| `scripts/p13_2_generate_preannotations.py` | 预标注生成：仅限assisted_review，test排除 |
| `scripts/p13_2_validate_goldset.py` | 验证器：13类检查、盲标泄漏扫描、证据区间验证 |
| `tests/test_p13_2_goldset_contract.py` | 19个测试：正例路径 + 13类负例 |
| `sample_data/p13_2/positive/fixture_feedback.json` | 100条合成正例（50 product + 50 aigc，4来源平衡） |
| `sample_data/p13_2/positive/candidates.json` | 导出结果 |
| `sample_data/p13_2/positive/preannotations.json` | 75条预标注（仅 dev+calibration） |
| `sample_data/p13_2/manifest.json` | 冻结清单 |

## Schema 与标注协议

- GoldRecord：16 字段，包含 sample_id、authorization_basis、content_hash、redacted_text、split、annotation_mode、annotator_slot
- HumanAnnotation / SignalAnnotation / EvidenceSpan：完整标注契约，含字符区间验证
- Suggestion：与 human label 严格分离，model/prompt版本标记
- FrozenManifest：确定性哈希、盲标泄漏计数、human_labels_complete=false
- annotation_mode：development/calibration=assisted_review，test=blind

## 实际数据资格与拒绝原因

| 指标 | 值 |
| --- | ---: |
| DB 总反馈 | 1,257 |
| fixture 样本 | 100 |
| fixture 合格 | 100 |
| fixture 拒绝 | 0 |

**真实 DB 导出：未执行**（当前 DB 以历史数据为主，授权字段未完整填充，预计不足 100 条合格记录。完整导出需 P13-2-2 阶段配合人工标注后进行。）

## 抽样、双标与 split 结果

| split | 数量 | annotation_mode | 双标 |
| --- | ---: | --- | --- |
| development | 50 | assisted_review | 0 |
| calibration | 25 | assisted_review | 2 |
| test | 25 | blind | 18 |
| **总计** | **100** | | **20** (20.0%) |

- 双标数 = max(20, ceil(100×20%)) = 20 ✅
- test=25条 ✅
- 每profile≥30 ✅
- 最大来源占比=25% ✅

## assisted-review 与 blind-test 泄漏隔离

| split | 数量 | suggestion数 | 泄漏数 |
| --- | ---: | ---: | ---: |
| development | 50 | 50 | 0 |
| calibration | 25 | 25 | 0 |
| test | 25 | 0 | 0 |

- test盲标包递归泄漏扫描：✅ 0泄漏
- suggestion仅存在于dev/calibration

## 确定性与 manifest 哈希

- 同 seed=42 两次运行 sample_ids 完全一致 ✅
- manifest 含 content_hash_list、ordered_samples_hash、guideline_hash

## 负例证据

| 负例 | 结果 | 通过 |
| --- | --- | --- |
| is_test_or_mock_record | True for "test_record_001", False for normal | ✅ |
| has_sensitive(email/phone/token) | True | ✅ |
| has_sensitive(普通文本) | False | ✅ |
| evidence_offset 精确匹配 (中文) | "这是"[0:2] == "这是" | ✅ |
| evidence_offset 不匹配 (Unicode负例) | [1:4] != "是" | ✅ |
| cross-split hash leak | 检测到重复 | ✅ |
| blind_pack_leakage(clean) | 0 | ✅ |
| blind_pack_leakage(leaked) | >0 | ✅ |
| calibration_allowed without labels | False | ✅ |
| 不足100条 | BLOCKED | ✅ |
| 不足30/profile | BLOCKED | ✅ |
| source>60% | BLOCKED | ✅ |
| AUTHORIZED_BASES 白名单 | "invalid_auth" not in set | ✅ |

## P13-1 回归与数据库计数守恒

- behavior_probe: Overall: **PASS**
- 全量测试: **215 passed, 3 warnings**
- DB 未写入任何新数据
- calibrated_confidence 全部为 null

## 未覆盖风险 / 外部阻断

1. **真实 DB 候选数据不足**：需 P13-2-2 配合人工标注或授权数据补充
2. **预标注为占位**：当前 fixture 预标注为固定模板，真实 LLM 预标注需连接 DeepSeek adapter
3. **人工标注尚未开始**：manifest.human_labels_complete=false，human_verified_count=0
4. **P13-2-4 校准禁止**：calibration_allowed=false

## 需要指挥官重点复核

1. schema 字段是否满足后续 P13-2-2/2-3/2-4 需求
2. 标注指南是否清晰、可执行
3. 授权白名单和敏感模式是否需要扩展
4. 真实 DB 候选导出需 Commander 提供授权数据或人工标注配合
