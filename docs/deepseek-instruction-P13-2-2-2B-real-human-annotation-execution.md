# DeepSeek 执行指令：P13-2-2-2B 真实人工标注、双标一致性与裁决

指令日期：2026-07-15

优先级：P0

当前状态：**INPUT-GATED / BLOCKED**。P13-2-2-2A readiness工具已通过，但当前真实授权候选为0，不能直接完成本阶段。

## 任务目标

在真实授权数据和真实人工角色到位后，使用已验收工具链完成：

1. 不少于100条真实人工验证样本；
2. 不少于25条冻结test盲标；
3. 不少于`max(20, ceil(真实候选数 × 20%))`条A/B独立双标；
4. Cohen's kappa不低于0.70且非退化；
5. 所有A/B分歧保留原始标签并由独立裁决员完成裁决；
6. 输出可复核的真实人工标注机器证据。

这不是让DeepSeek代替人工标注。DeepSeek只允许执行数据接入、任务包验证、导入、机器校验和报告生成。

## 启动前置条件

以下输入必须全部由用户或授权外部流程提供：

- 至少100条真实授权、脱敏候选及真实rejection记录；
- dataset manifest、四类task pack、pack manifest和生产签名；
- 冻结development/calibration/test split；
- 三个互不相同的pseudonym角色：annotator A、annotator B、adjudicator；
- 时区完整的annotation governance配置；
- 生产签名密钥通过环境安全注入，不得写入仓库或报告；
- A/B及裁决员是实际独立人类，不得由LLM、规则或同一身份冒充。

任一输入缺失时，本阶段必须保持`BLOCKED_INPUT_REQUIRED`，不得修改代码绕过。

## 第一门禁：2A正式readiness

使用真实输入的launch config运行：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py \
  --launch-config <real-authorized-launch-config.json> \
  --environment production \
  --no-publish
```

只有同时满足下列条件才可分发人工任务：

```text
status = READY_FOR_HUMAN_ANNOTATION
passed = true
exit_code = 0
batch_id = 非空
7个batch_id_components全部非空
human_verified_count = 0
human_labels_complete = false
calibration_allowed = false
```

如果当前无真实输入，应运行默认门禁确认安全阻塞：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish
```

预期为`BLOCKED_INPUT_REQUIRED / exit2`。此时只提交输入阻塞报告并停止，不得生成标签、不得把fixture READY当成真实READY。

## 允许范围

在前置条件满足后允许：

- 使用现有P13-2工具生成或验证真实任务包；
- 将实际人类完成的annotation文件导入独立真实annotation store；
- 生成独立adjudication记录；
- 生成`docs/P13-2-evidence/`下的本批次机器证据；
- 编写P13-2-2-2B交付报告和人工操作交接记录。

真实输入路径和输出路径必须带`dataset_id`或`batch_id`，不得覆盖fixture样例和历史批次。

## 禁止范围

- 不得让DeepSeek或任何LLM填写、改写或补齐人工label；
- 不得使用fixture、规则标签、模型一致意见、LLM-as-judge计入`human_verified_count`；
- 不得把assisted suggestion带入冻结test包；
- 不得把模型名、prompt、prediction、confidence、score泄漏给test A/B；
- 不得让同一pseudonym承担同一样本的A和B；
- 不得覆盖A/B原始标签；裁决必须是独立记录；
- 不得把`FIXTURE_PASS`或validator exit0单独解释为真实READY；
- 不得设置`calibration_allowed=true`；
- 不得进入P13-2-3、P13-2-4、P13-3或前端概率发布；
- 不得修改已验收的readiness、信任链、导入器或validator来适配不合格输入。若工具发现缺陷，停止并报告，由Commander另行立项。

## 人工执行要求

### 1. 任务分发

- development/calibration可显示明确标记的脱敏suggestion，但隐藏模型身份、provider、prompt和全部score；
- test A和test B必须完全盲标；
- B包只包含冻结双标sample；
- 任务分发记录必须绑定`dataset_id`、`batch_id`、task hash和人类pseudonym角色。

### 2. 人工标签

每条真实annotation必须：

- `fixture=false`；
- provenance为真实人工；
- dataset/sample/task/content hash与冻结任务一致；
- evidence span与脱敏原文严格匹配；
- signal type符合profile白名单；
- assisted-review保留accepted/modified/rejected动作；
- started/completed时间为真实、时区完整的时间。

### 3. 导入

对每个实际人类交付文件运行现有导入器：

```bash
.venv/bin/python scripts/p13_2_import_human_annotations.py \
  --input <real-human-annotations.json> \
  --tasks <batch-specific-human-task-dir> \
  --store <batch-specific-human-annotation-store.json>
```

任何schema、hash、slot、evidence、PII、身份隔离或重复冲突失败都必须停止，不得手工删除错误后继续冒充完整批次。

### 4. 分歧裁决

- 先冻结A/B原始标签与SHA；
- 生成分歧列表；
- 由独立adjudicator形成单独adjudication记录；
- 不得修改A/B原始记录；
- 未裁决分歧必须保持`BLOCKED_PENDING_ADJUDICATION`。

## 最终机器验收

```bash
.venv/bin/python scripts/p13_2_validate_human_annotations.py \
  --tasks <batch-specific-human-task-dir> \
  --store <batch-specific-human-annotation-store.json> \
  --adjudications <batch-specific-adjudications.json> \
  --stage-policy docs/P13-2/stage-policy.json \
  --out docs/P13-2-evidence/<batch-id>-human-annotation-contract-metrics.json
```

真实阶段通过必须同时满足：

| 指标 | 门槛 |
| --- | ---: |
| `status` | `READY` |
| `passed` | `true` |
| `fixture_count` | `0` |
| `human_verified_count` | `>=100` |
| `test_blind_real` | `>=25` |
| `double_annotation_count` | `>=max(20, ceil(n×20%))` |
| has_signals kappa | `>=0.70`且非退化 |
| 未裁决分歧 | `0` |
| `human_labels_complete` | `true` |
| `calibration_allowed` | `false` |

validator输出`FIXTURE_PASS`、任意`BLOCKED_*`、`FAIL`或关键check false均不得声明阶段完成。

## 回归与证据要求

真实批次完成后还必须运行：

```bash
.venv/bin/ruff check scripts/p13_2_import_human_annotations.py scripts/p13_2_validate_human_annotations.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_human_annotation_contract.py
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
git diff --check
```

证据必须包含：

- readiness batch_id及7组件SHA；
- 四类task pack SHA；
- A/B原始标签文件SHA；
- adjudication文件SHA；
- validator机器JSON SHA；
- 每条命令实际退出码、测试数量和warnings；
- 人工身份只使用不可逆pseudonym，不得写真实身份或生产密钥。

## 当前阻塞分支的交付要求

在当前真实授权候选仍为0的情况下，只允许生成：

```text
docs/acceptance-P13-2-2-2B-input-blocked-20260715.md
```

内容必须列出：

- readiness实际`BLOCKED_INPUT_REQUIRED / exit2`；
- 缺失输入清单；
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`；
- 未生成真实标签、未导入fixture、未进入校准；
- 需要用户或外部人工流程提供的下一项输入。

此阻塞报告不是阶段交付报告，不能回复“P13-2-2-2B已完成”。

## 完成交付报告

只有真实机器验收达到`READY`后才允许新增：

```text
docs/acceptance-P13-2-2-2B-delivery-<batch-id>-YYYYMMDD.md
```

报告必须逐项引用同批次机器JSON，不得手写不同的计数、kappa、状态或SHA。Commander独立验收通过前，不得进入P13-2-3。
