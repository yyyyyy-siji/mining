# P13-2-1 验收报告：混合金标协议、脱敏导出、预标注隔离与冻结清单

验收日期：2026-07-10

结论：**不通过，需要返修。P13-2-2继续冻结。**

## 已通过项

- P13-1 行为探针独立复跑通过。
- P13-2-1 聚焦测试显示 `19 passed`；全量回归显示 `215 passed, 3 warnings`。
- 合成fixture能够生成50/25/25的development/calibration/test分割。
- 当前合成test候选记录标记为`blind`，预标注文件中没有test suggestion。
- `human_labels_complete=false`、`human_verified_count=0`、`calibration_allowed=false`的基础状态方向正确。
- `git diff --check`通过。

上述结果只能证明基础骨架存在，不能抵消以下安全门禁和机器证据失真。

## 阻断问题

### P0-1：缺失授权依据被采集方式自动“推导”为已授权

位置：

- `signal_miner/evaluation/__init__.py` 的 `_derive_authorization()`
- `scripts/p13_2_export_annotation_pack.py` 的资格筛选

问题：

- `manual/import` 被自动映射为 `internal_feedback_channel`。
- `crawl/scrape/api` 被自动映射为 `public_forum_post`。
- 导出器在原始 `authorization_basis` 为空时调用该函数并把推导值写回样本。

独立证据：

```json
{
  "manual": "internal_feedback_channel",
  "crawl": "public_forum_post",
  "api": "public_forum_post"
}
```

影响：采集方式不能证明用户同意、公开可用或内部授权。该逻辑会把来源不明的历史数据伪装成授权数据，直接破坏金标集真实性。

验收要求：

- 删除授权自动推导；`authorization_basis`必须来自显式、可追溯的来源元数据。
- 缺失或非法授权依据必须进入rejection report，不能进入eligible样本。
- `source_platform`与`capture_method`分开；禁止用`manual/api/import/crawl`冒充平台分布。

### P0-2：验证器对关键篡改全部假阳性

位置：`scripts/p13_2_validate_goldset.py`

问题：

- `manifest_hash_valid`直接读取`manifest.passed`，没有重新计算任何哈希。
- test泄漏扫描先经过Pydantic默认忽略额外字段，再扫描`model_dump()`，泄漏字段可被静默删除。
- evidence检查硬编码`passed=true, mismatch_count=0`。
- 双标只计算ID列表长度，不验证唯一性、成员存在、A/B分配或独立包。
- 输出中的`human_verified_count=0`等字段被硬编码，没有忠实反映manifest。

独立mutation结果：

| 篡改 | 实际结果 | 应有结果 |
| --- | --- | --- |
| `ordered_samples_hash="tampered"` | READY / passed=true | FAIL / 非0 |
| test候选加入`model_self_score=0.99` | READY / passed=true | FAIL / 非0 |
| 同一个sample ID重复20次充当双标 | READY / passed=true | FAIL / 非0 |
| 预标注evidence使用`[999:1000]`错误区间 | READY / passed=true | FAIL / 非0 |
| manifest写入`human_verified_count=100` | READY / passed=true | FAIL / 非0 |

影响：`goldset-contract-metrics.json`的`passed=true`不能证明交付契约成立，属于发布安全假阳性。

验收要求：验证器必须从原始候选、三个标注包、预标注、指南和manifest独立重算所有关键值；不得信任manifest中的`passed`。

### P0-3：所谓13类负例没有真实证明“错误实现会非0”

位置：`tests/test_p13_2_goldset_contract.py`

问题：

- `test_export_deterministic`在两次导出结束后才连续读取同一个最终文件，比较的是文件与自身。
- `test_minimum_sample_count`、`test_profile_minimum`、`test_source_imbalance`是空`pass`。
- 多数“负例”只调用辅助函数或手工复写判断，没有把错误artifact交给正式验证器并检查非零退出码。
- 聚焦测试会写入项目固定路径；结束后`candidates.json`变成50条BLOCKED，而旧`metrics.json`仍是100条READY。

影响：测试全绿仍会留下互相矛盾的机器证据，复发了“验证脚本假阳性 / 报告漂移”高频缺陷。

验收要求：所有测试使用`tmp_path`隔离；新增独立mutation gate，对每类错误artifact真实启动验证器、检查非零退出码和对应`checks.*.passed=false`。

### P1-1：必需的真实数据库导出证据缺失，交付报告的阻断原因不实

要求交付物`docs/P13-2-evidence/real-candidate-export.json`不存在，报告明确写“真实 DB 导出未执行”，却又自行判断“不足100条”。

指挥官实际执行后得到：

```json
{
  "status": "BLOCKED_INSUFFICIENT_PROFILE_SAMPLES",
  "profile": "aigc_video",
  "count": 0,
  "required_minimum": 30
}
```

这与报告声称的“不足100条合格记录”不同，而且由于P0-1的授权自动推导，该结果仍不能作为可信资格统计。

验收要求：无fixture执行真实导出，始终生成机器JSON和拒绝原因统计；READY退出0、BLOCKED退出2、内部/契约错误退出1。

### P1-2：预标注、双标包和schema尚不能承担后续人工流程

- `p13_2_generate_preannotations.py`为所有样本固定生成`feature_request`模板，包括AIGC profile；这不是有效预标注，只能是显式fixture。
- 只有`double_annotation_ids`，没有互相隔离的A/B标注包或分配清单。
- `GoldRecord`缺少指令要求的`schema_version`。
- 数据契约声称模型位于`signal_miner/evaluation/goldset.py`，实际全部写在`__init__.py`。
- `source_distribution`实际统计的是capture method，而不是来源平台。

验收要求：fixture suggestion必须显式标记fixture；默认预标注路径要么调用真实配置adapter，要么诚实BLOCKED，不能生成伪语义模板。生成A/B独立包并补齐schema契约。

### P1-3：交付报告声称Ruff通过，独立执行失败

独立命令：

```bash
.venv/bin/ruff check signal_miner tests scripts
```

结果：`SIM103`，位置`signal_miner/evaluation/__init__.py:190`，退出非0。

影响：报告与代码事实再次漂移。

## 非阻断观察项

- 当前敏感信息模式只覆盖部分邮箱、中国大陆手机号和`sk-` token，与文档所称“国际格式、其他key”不完全一致。
- export早期BLOCKED路径没有完整写出rejection report、profile/source分布和manifest状态，阻断原因难以审计。
- `selection_query_fingerprint`只包含seed和schema，没有包含输入清单、资格规则版本或查询边界。

## 复验要求

1. 只执行`docs/deepseek-instruction-P13-2-1-fix.md`，不得进入P13-2-2。
2. 提交新的fix交付报告、真实导出JSON、mutation gate JSON和隔离测试证据。
3. Commander将重新执行授权缺失、哈希篡改、test泄漏、重复双标ID、错误offset和人工计数六类独立负例。
4. Ruff、聚焦测试、全量回归、P13-1行为探针和证据artifact前后SHA守恒必须同时通过。

## 问题统计归类

- 验证脚本假阳性 / 关键行为未参与顶层passed：复发。
- 交付报告、代码与机器artifact漂移：复发。
- 契约测试缺少真实负例：复发。
- 授权/来源真实性被采集方式替代：新增P0类别。
