# P13-2 正式人工标注启动条件复核（2026-09-09）

状态：**BLOCKED_INPUT_REQUIRED**

## 结论

当前不能生成或分发 `fixture=false` 正式人工标注任务包，也不能把现有75条
assisted任务当作正式金标。DeepSeek运行条件已经具备，但真实数据来源的授权、
来源平台持久化、授权记录引用、脱敏证明和正式批次治理仍不完整。

本轮没有调用DeepSeek生成建议，没有修改历史数据库授权字段，没有生成正式标签，
也没有使用fixture替代真实输入。

## 本轮独立复核结果

### 1. 数据库与数据来源

- 数据库：`signal_miner.db`
- 原始反馈：1,257条，全部文本非空
- 最新入库时间：2026-06-24；本轮未发现更新的真实候选输入
- profile分布：`product_feedback=1,206`，`aigc_video=51`
- source_type分布：
  - `support_ticket=223`
  - `douyin=220`
  - `manual=206`
  - `bilibili=204`
  - `kuaishou=197`
  - `app_review=193`
  - `xiaohongshu=13`
  - `video_douyin=1`
- 帧ურ器可跳转的`external_url`记录：587条
- 按文本SHA-256去重后仅392条唯一文本，重复行865条
- 唯一文本中带`external_url`的仅84条
- 使用当前敏感信息规则扫描，命中0条；这只能说明规则未命中，不能替代每条记录的
  `pii_scanned=true`、`pii_redacted=true`和脱敏哈希证明

数据库模型当前没有持久化 `authorization_basis`、`authorization_record_ref` 和
独立 `source_platform` 字段。不能根据 `source_type` 或公开URL反推授权。

### 2. 最新真实候选导出复跑

执行：

```bash
.venv/bin/python scripts/p13_2_export_annotation_pack.py \
  --out /tmp/signal-miner-audit-20260909-candidates.json \
  --rejects /tmp/signal-miner-audit-20260909-rejections.json \
  --manifest /tmp/signal-miner-audit-20260909-manifest.json
```

实际完整命令同时将 rejects 和 manifest 写入 `/tmp` 独立审计路径；仓库内既有证据未被覆盖。

结果：

```text
exit_code=2
status=BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES
eligible_count=0
rejected_count=1257
missing_or_invalid_authorization=1257
missing_source_platform=1257
```

### 3. DeepSeek建议生成条件

- `DEFAULT_LLM_PROVIDER=deepseek`
- `DEEPSEEK_API_KEY`已配置（本报告不记录密钥值）
- 运行时可构建`DeepSeekAdapter`
- 模型配置：`deepseek-chat`
- 当前`preannotations.json`仍为`fixture_only=true`，共75条，模型标识为`fixture`

因此DeepSeek不是当前第一阻断项。真实候选未通过来源门禁前，不应消耗API生成建议。

### 4. 任务包与人类输入

- 当前4个`human_tasks_*.json`全部为`fixture=true`
- development 50条、calibration 25条、test A 25条、test B 20条
- 当前样例人工标签也是fixture生成结果，不是真实人工标注
- 未发现正式`real-authorized-launch-config.json`
- 未发现真实roles、splits、governance配置
- 未配置`ANNOTATION_PACK_SIGNING_KEY`

### 5. 启动门禁

执行：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish
```

结果：`BLOCKED_INPUT_REQUIRED / exit 2`，9个阻断项：

1. `real_candidates`
2. `production_signing_key`
3. `human_roles`
4. `pack_trust`
5. `task_identity`
6. `task_candidate_binding`
7. `test_blind_leakage`
8. `split_isolation`
9. `annotation_governance`

相关工具回归：94项测试通过。

## 最短补齐路径（按顺序）

### P0：建立真实数据来源授权清单

由数据所有者、平台合规负责人或授权数据供应方提供至少100条唯一候选。每条必须包含：

`dataset_id`、`sample_id`、`raw_feedback_id`、`source_url`、`source_adapter`、
`source_version`、`captured_at`、`content_sha256`、`authorization_basis`、
`authorization_record_ref`、`permitted_use`、`pii_scanned=true`、
`pii_redacted=true`、`raw_text_sha256`、`redacted_text_sha256`、`profile`、
`language`、`source_tier`。

要求：

- 不得从`source_type`、URL或“公开可见”自动推导授权；
- `authorization_record_ref`必须指向可审计的同意记录、许可证、内部授权单或平台使用依据；
- 原始文本不得进入标注页面，只分发脱敏文本；
- 先按内容hash去重，再冻结split；
- 保留所有被拒记录及逐条拒绝原因；
- 为满足既有exporter分布门禁，两类profile各至少30条，单一来源占比不高于60%。

现有数据库最多只能作为“待补授权的候选池”。其中84条唯一文本带URL，仍少于100条，
且URL本身不是授权证明。

### P1：补齐人工角色和治理

由项目负责人提供三个互不相同的真实人类pseudonym：annotator A、annotator B、
adjudicator，并确认A/B访问隔离。双标计划不少于
`max(20, ceil(候选数 × 20%))`。

同时提供带时区的标注开始时间、结束时间、保留期限和允许访问的角色ID清单。

### P1：配置生产签名

通过运行环境安全注入`ANNOTATION_PACK_SIGNING_KEY`。不得写入仓库、任务包、报告或聊天；
不得与test key相同，也不得使用fixture/test/example/dummy字样的替代密钥。

### P2：生成正式批次

在P0/P1输入齐备后：

1. 创建新的dataset version和冻结manifest，不覆盖fixture样例；
2. 对development/calibration调用DeepSeek生成真实建议；
3. test A/B保持完全盲标，不包含suggestion、model、prompt、confidence或score；
4. 生成四类`fixture=false`任务包并生产签名；
5. 使用真实launch config运行readiness；
6. 只有得到`READY_FOR_HUMAN_ANNOTATION`才在标注页面直接载入。

正式门禁应满足：

```text
status=READY_FOR_HUMAN_ANNOTATION
passed=true
exit_code=0
batch_id非空
```

## 下一次继续执行的触发条件

收到以下三类输入后即可继续自动生成与验证：

1. 至少100条符合上述字段契约的真实授权、脱敏候选和对应rejections；
2. A、B、裁决员角色配置及governance配置；
3. 已在运行环境中安全注入生产签名密钥。
