# P13-2 金标数据契约 v1

## 命名空间与版本

- `schema_version`: `"1.0.0"`
- 所有 schema 类定义位于 `signal_miner/evaluation/goldset.py`
- 命名空间: `signal_miner.evaluation.goldset`

## 核心记录

### GoldRecord（金标候选样本）

每个待标注样本必须有稳定 `sample_id`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sample_id` | `str` | 稳定样本 ID（`gs_` 前缀 + uuid） |
| `raw_feedback_id` | `str | None` | 原始反馈 ID，可能因脱敏缺失 |
| `profile` | `str` | `product_feedback` 或 `aigc_video` |
| `source_platform` | `str` | 来源平台标识 |
| `capture_method` | `str` | 采集方式：`manual`/`api`/`import`/`crawl` |
| `authorization_basis` | `str` | 授权依据（必须非空且在白名单） |
| `content_hash` | `str` | 原文 SHA-256 |
| `redacted_text` | `str` | 脱敏后的标注文本 |
| `redaction_applied` | `bool` | 是否执行了脱敏 |
| `language` | `str` | 原文语言代码 |
| `hard_case_tags` | `list[str]` | 难例标记（为空则 `[]`） |
| `split` | `str` | `development`/`calibration`/`test` |
| `split_seed` | `int` | 用于 split 的确定性 seed |
| `annotation_mode` | `str` | `assisted_review` 或 `blind` |
| `annotation_status` | `str` | `pending`/`in_progress`/`complete`/`conflict` |
| `annotator_slot` | `str` | `A`/`B`/`none` |

**双标规则**：`annotation_mode=blind` 优先选为双标。A/B 不能看到对方标签。每个双标样本产生 A 和 B 两条记录。

### HumanAnnotation（人工标签）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sample_id` | `str` | 关联样本 |
| `annotator_slot` | `str` | A/B |
| `has_signals` | `bool` | 是否存在可提取信号 |
| `signal_count` | `int` | 提取的信号数量 |
| `signals` | `list[SignalAnnotation]` | 逐信号标注 |
| `completed_at` | `str | None` | 完成时间 |
| `notes` | `str | None` | 标注员备注 |

### SignalAnnotation（单条信号标注）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `signal_type` | `str` | 信号类型 |
| `summary` | `str` | 摘要要点 |
| `evidence_spans` | `list[EvidenceSpan]` | 原文 evidence 区间 |
| `implicit_need` | `str | None` | 隐含需求 |
| `implicit_need_has_basis` | `bool` | 隐含需求是否有原文依据 |
| `hallucination` | `bool` | 是否包含无依据的新增事实 |
| `notes` | `str | None` | 标注员备注 |

### EvidenceSpan（evidence 字符区间）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `start` | `int` | 起始位置（含） |
| `end` | `int` | 结束位置（不含） |
| `text` | `str` | 对应原文片段 |

验证器必须断言 `redacted_text[start:end] == text`，处理中文和 Unicode。

### AnnotationDispute（分歧）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sample_id` | `str` | |
| `field` | `str` | 分歧字段 |
| `value_a` | `Any` | |
| `value_b` | `Any` | |
| `resolution` | `str | None` | 裁决结果 |
| `resolved_by` | `str | None` | 裁决者 |
| `resolved_at` | `str | None` | |

### Suggestion（机器预标注，仅限 assisted_review）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `suggestion_id` | `str` | |
| `suggestion_model` | `str` | 模型名称 |
| `suggestion_model_version` | `str` | |
| `suggestion_prompt_version` | `str` | |
| `suggested_signals` | `list` | 预标注信号 |
| `suggestion_created_at` | `str` | |

**禁止出现在 test 盲标包中。**

### FrozenManifest（冻结清单）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dataset_id` | `str` | |
| `schema_version` | `str` | |
| `created_at` | `str` | ISO datetime |
| `selection_query_fingerprint` | `str` | 查询指纹 hash |
| `seed` | `int` | |
| `splits` | `dict[str, list[str]]` | split→sample_ids |
| `double_annotation_ids` | `list[str]` | 双标 sample_ids |
| `double_annotation_count` | `int` | |
| `double_annotation_ratio` | `float` | |
| `annotation_mode_by_split` | `dict[str, str]` | |
| `sample_count` | `int` | |
| `profile_distribution` | `dict[str, int]` | |
| `source_distribution` | `dict[str, int]` | |
| `blind_pack_hash` | `str` | test 盲标包 hash |
| `blind_pack_leakage_count` | `int` | 泄漏检查计数 |
| `content_hash_list` | `list[str]` | 所有 redacted_text 的 SHA-256 |
| `ordered_samples_hash` | `str` | 全部样本有序清单 SHA-256 |
| `guideline_hash` | `str` | annotation guideline SHA-256 |
| `human_labels_complete` | `bool` | 始终 `false` 直到 P13-2-2 |
| `human_verified_count` | `int` | 始终 `0` 直到 P13-2-2 |
| `calibration_allowed` | `bool` | 始终 `false` 直到 P13-2-4 |
| `passed` | `bool` | |

## 授权白名单

`authorization_basis` 必须属于：

- `explicit_user_consent` — 用户明确同意
- `public_forum_post` — 公开论坛/社交媒体帖子
- `internal_feedback_channel` — 内部反馈渠道
- `licensed_dataset` — 已授权数据集

## 敏感模式（默认拒绝）

redacted_text 不得包含：
- 邮箱：`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- 手机号：`1[3-9]\d{9}` 或国际格式
- Token/Key：`sk-[a-zA-Z0-9]{20,}` 等
- 用户配置的其他敏感模式

## Profile 支持

- `product_feedback`
- `aigc_video`
