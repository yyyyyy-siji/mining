# DeepSeek 返修指令：P13-2-1 fix-2 独立验证器、来源平台与artifact隔离

## 任务目标

在不扩大阶段的前提下，修复P13-2-1 fix仍存在的机器门禁假阳性、source platform混淆、伪预标注、manifest静默覆盖和测试artifact污染。完成后P13-2-1基础设施必须能抵抗Commander独立篡改。

## 允许修改范围

- `signal_miner/evaluation/`
- `scripts/p13_2_export_annotation_pack.py`
- `scripts/p13_2_generate_preannotations.py`
- `scripts/p13_2_validate_goldset.py`
- `scripts/p13_2_mutation_gate.py`
- `tests/test_p13_2_goldset_contract.py`
- `sample_data/p13_2/` fixture与标注包
- `docs/P13-2/`协议文档
- `docs/P13-2-evidence/`机器证据
- P13-2-1 fix-2交付报告

## 禁止修改范围

- 生产pipeline、runner、去重、聚类和资产生成
- 数据库模型、迁移、API、前端
- LLM adapter和生产prompt
- P13-1安全逻辑
- P13-2-2/2-3/2-4及P13-3以后阶段

## 实现要求

### 1. source platform与capture method必须分离

- fixture每条记录显式包含`source_platform`与`capture_method`。
- 导出器分别读取`fb["source_platform"]`和`fb["capture_method"]`，禁止从`source_type`互相推导。
- `source_platform`建议使用真实平台/渠道标识，如`github`、`internal_support`、`authorized_forum`、`licensed_corpus`；`capture_method`使用`api/manual/import/crawl`。
- 缺少任何一个字段都必须拒绝，并分别输出`missing_source_platform`、`missing_capture_method`。
- source balance只按`source_platform`统计，报告另外输出capture method分布。
- 真实数据库没有显式字段时诚实BLOCKED，不得推导补齐。

### 2. 验证器完整读取七类artifact

CLI必须显式接收且要求存在：

1. candidates
2. manifest
3. development assisted-review pack
4. calibration assisted-review pack
5. test A blind pack
6. test B blind pack
7. preannotations与annotation guideline

任一文件缺失必须生成`checks.files_exist.passed=false`并退出1。

验证器必须新增或强化以下目标check：

- `schema_validation`
- `files_exist`
- `sample_count`
- `profile_minimum`
- `source_balance`
- `capture_method_contract`
- `splits_valid`：必须精确50/25/25，不是只检查test≥25
- `annotation_modes`
- `authorization`
- `no_test_records`
- `sensitive_content`：只要`has_sensitive(redacted_text)`即失败，与`redaction_applied`值无关
- `no_cross_split_leak`
- `double_annotation`
- `pack_contract`
- `blind_pack_leakage`
- `suggestion_contract`
- `evidence_offsets`
- `manifest_hash_valid`
- `manifest_identity`
- `labels_not_complete`
- `calibration_not_allowed`

### 3. 逐字段独立重算

必须重算并严格比较：

- `dataset_id = sha256(ordered_samples_hash)[:16]`
- manifest schema version
- sample count与精确split ID列表/顺序
- profile、source platform、capture method分布
- double IDs唯一性、存在性、数量、ratio
- annotation mode mapping
- content hash list
- ordered samples hash
- selection query fingerprint
- guideline hash
- A/B实际包的规范化组合hash；manifest的blind pack hash必须基于实际A/B文件，而不是候选test列表
- A包25条且header/每条slot=A；B包恰好是double IDs且header/每条slot=B
- dev/cal pack样本集合、mode和无confidence/model identity契约
- preannotations存在；每个suggestion引用存在的dev/cal样本，不允许test或未知ID
- dev/cal suggestion数量符合fixture预期；每个evidence offset匹配
- `human_labels_complete`、`human_verified_count`、`calibration_allowed`的真实值和一致性

禁止硬编码输出状态字段。输出必须回显经过验证的manifest实际值。

### 4. manifest冻结语义

- 相同输入、seed、规则版本再次导出时必须字节级幂等，不更新`created_at`，不改变任何SHA。
- 输出路径已存在且不可变内容相同：复用原manifest。
- 输出路径已存在但dataset ID或不可变内容不同：默认退出1，状态`FAIL_FROZEN_MANIFEST_MISMATCH`。
- 只有显式`--new-dataset-version`才允许写新路径/新dataset；不得静默覆盖。
- 不同`PYTHONHASHSEED`下结果仍完全一致；遍历profile时使用排序后的稳定序列。

### 5. 预标注必须区分fixture与真实路径

- 增加显式`--fixture-mode`。只有该模式允许生成确定性模板，并强制：
  - `suggestion_model="fixture"`
  - `fixture_only=true`
  - 不得使用`deepseek`名称
- 默认非fixture模式调用现有配置adapter的评测入口；如果provider、密钥或调用能力不可用：
  - 输出JSON `status=BLOCKED_PREANNOTATION_UNAVAILABLE`
  - `passed=false`
  - 退出2
  - 不生成模板suggestion
- 使用注入fake adapter测试成功结构与异常路径，不要求验收环境真实联网。
- suggestion模型应遵守对应profile的signal type白名单，不能对AIGC固定输出`feature_request`。

### 6. mutation gate必须验证目标check

- 每个mutation子进程都传入临时`--out <tmp>/metrics.json`，不得写项目`docs/P13-2-evidence/goldset-contract-metrics.json`。
- 从临时metrics JSON读取`checks[target_check].passed`。
- 通过条件必须同时满足：
  - child exit=1；
  - 目标check存在；
  - 目标check的`passed=false`。
- 目标check缺失、只出现其他check失败、stdout只有overall false，均判mutation失败。
- BLOCKED退出2不算mutation成功；mutation是契约错误，必须exit1。

在原16类基础上至少新增并真实覆盖：

17. sensitive文本且`redaction_applied=false`。
18. A/B包缺失。
19. dataset ID篡改。
20. blind pack hash篡改。
21. manifest double ratio篡改。
22. manifest annotation modes篡改。
23. manifest schema version篡改。
24. suggestion引用不存在sample。
25. preannotations缺失。
26. B包header改为A或样本集合清空。
27. split改为49/26/25并同步篡改manifest。
28. source platform与capture method互换或缺失。
29. dev/cal pack缺失或成员不一致。
30. 同dataset ID静默覆盖不同内容。

原mutation 5必须真正修改中文Unicode evidence offset并以`evidence_offsets=false`通过；原mutation 12必须真正测试冻结manifest/dataset identity，不得再次用content hash list替代。

### 7. 所有测试必须使用临时路径

- 删除任何调用export/validator默认输出路径的测试。
- `_export()`与`_validate()`测试helper强制要求显式`tmp_path`输出，缺少即测试代码报错。
- 测试不能改写`sample_data/p13_2/`或`docs/P13-2-evidence/`。
- mutation gate也不得改写除自身最终`mutation-gate.json`以外的交付artifact。
- 聚焦测试、全量测试、mutation gate分别执行前后，对所有既有artifact计算SHA-256；除当前命令声明的唯一输出外必须0变化。

## 验收标准

### 静态与回归

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_goldset_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_1_behavior_probe.py
git diff --check
```

### 机器门禁

```bash
.venv/bin/python scripts/p13_2_validate_goldset.py
.venv/bin/python scripts/p13_2_mutation_gate.py
python3 -m json.tool docs/P13-2-evidence/goldset-contract-metrics.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/mutation-gate.json >/dev/null
python3 -m json.tool docs/P13-2-evidence/real-candidate-export.json >/dev/null
```

期望：正例validator exit0；mutation gate exit0且至少30/30，每项target check明确false；真实DB导出exit2且显式授权/来源字段统计真实；P13-1行为探针exit0。

### Commander独立负例

交付前必须用正式CLI证明以下各自exit1：

- test候选包含邮箱且redaction flag=false；目标`sensitive_content=false`
- A/B包缺失；目标`files_exist=false`
- dataset ID篡改；目标`manifest_identity=false`
- blind hash篡改；目标`manifest_hash_valid=false`
- preannotations缺失；目标`files_exist=false`
- suggestion未知ID；目标`suggestion_contract=false`
- B包清空/slot错误；目标`pack_contract=false`
- source platform缺失；目标`source_balance`或独立source contract=false

## 交付物

1. `docs/acceptance-P13-2-1-delivery-fix-2-20260711.md`
2. `docs/P13-2-evidence/goldset-contract-metrics.json`
3. `docs/P13-2-evidence/mutation-gate.json`
4. `docs/P13-2-evidence/real-candidate-export.json`
5. `docs/P13-2-evidence/real-rejections.json`
6. `docs/P13-2-evidence/artifact-sha-invariance.json`

## 交付报告模板

```markdown
# P13-2-1 fix-2交付报告：独立验证器、来源平台与artifact隔离

## 结论

- fixture validator：PASS / FAIL
- mutation gate：PASS / FAIL（x/30）
- artifact SHA守恒：PASS / FAIL
- 真实候选：READY / BLOCKED / FAIL
- 真实预标注：READY / BLOCKED / NOT_RUN
- 人工标签：NOT_STARTED
- 校准发布：NOT_ALLOWED

## 修改文件

## 显式来源平台与采集方式

## Manifest身份与逐字段重算

## 七类artifact与A/B契约

## 真实预标注 / fixture隔离

## Mutation target-check结果

| mutation | child exit | target check exists | target passed | detected |
| --- | ---: | --- | --- | --- |

## Artifact SHA守恒

| command | changed artifacts | passed |
| --- | ---: | --- |

## 真实数据库导出

## P13-1回归

## 未覆盖风险
```

## 完成边界

fix-2通过只代表P13-2-1基础设施可信，不代表人工金标、指标或置信度校准完成。P13-2-2在Commander最终验收前继续冻结。
