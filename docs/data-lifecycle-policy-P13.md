# SignalMiner 数据生命周期策略：每次挖掘如何处理旧数据

版本：2026-07-10  
状态：P13规划契约，待P13-5实现

## 1. 当前代码的实际行为

当前行为不是覆盖旧数据，也不是完整版本化，而是“半增量、永久累积”：

- 未指定feedback_ids时，pipeline只选择当前profile下`processing_state=pending`的原始反馈。
- 已完成的RawFeedback默认不会再次提取；显式传入已完成ID也会被extraction状态检查跳过。
- RawFeedback、Signal、Theme、PainPoint、Opportunity、Requirement均不会在新运行前自动删除。
- 聚类排除已经进入主题的信号，只聚类尚未分配主题的信号；新信号不会稳定并入旧主题。
- 资产生成只处理draft主题，随后把主题标成reviewed；旧资产一直保留。
- 派生资产没有统一run_id/dataset_version，因此前端和API可能同时展示不同时间、模型和算法生成的结果。
- 没有正式的全量重算、候选版本发布、回滚、来源更新和来源删除传播机制。

因此，当前系统最大的数据管理风险不是“旧数据丢失”，而是“旧数据和新结果混在一起，却无法知道哪一版才是当前可信结果”。

## 2. 总原则

### 2.1 原始数据默认不删除

RawFeedback是证据链底座，默认采用不可变revision。内容变化时新增revision，不覆盖旧正文；重复内容则幂等返回已有revision。

### 2.2 派生结果必须版本化

Signal、Theme、PainPoint、Opportunity和Requirement是可再生数据。它们必须归属于某个PipelineRun和DatasetVersion，不能只依靠created_at判断新旧。

### 2.3 新结果先候选，后发布

重算结果先进入candidate版本。只有通过置信度、去重、聚类和证据链质量门禁后，才整体切换为active；当前active版本在此之前继续服务。

### 2.4 旧结果保留但退出默认视图

新版本发布后，旧active变成superseded。默认API只返回新active；历史页面仍可查看旧版本及其证据链。

### 2.5 删除以失效传播优先

来源删除或合规撤回时，先tombstone原始revision，沿证据链把派生资产标为invalidated并退出默认视图。需要法律硬删除时再执行受审计的物理清除。

## 3. 核心实体

### DatasetVersion

表示一次运行所看到的确定数据快照，至少包含：

- dataset_version_id
- namespace：production/test/sample
- profile
- 创建时间
- raw revision集合或可复现查询边界
- 数据计数与内容清单哈希
- 父版本ID

### PipelineRun

在现有run记录上增加：

- dataset_version_id
- run_mode：incremental/rebuild/resume
- idempotency_key
- configuration_fingerprint
- primary_model与版本
- embedding_model与版本
- prompt版本
- 去重/聚类阈值和算法版本
- candidate/released/rolled_back状态

### RawFeedbackRevision

每个外部原始记录通过`source_id + external_id`确定逻辑实体，通过revision和content_hash确定内容版本。

推荐状态：active、superseded、tombstoned、quarantined。

### DerivedAssetVersion

Signal及后续资产至少保存：

- run_id
- dataset_version_id
- lifecycle_status：candidate/active/superseded/invalidated/archived
- supersedes_id或version_family_id
- created_by算法/模型版本

## 4. 三类运行

### Incremental

日常默认方式。只处理上一个已发布dataset之后新增或变化的raw revision，以及受到变化影响的主题和下游资产。未变化的旧数据通过引用复用，不重新调用LLM。

### Rebuild

当Prompt、模型、Embedding、分类体系、阈值或聚类算法变化时使用。基于明确DatasetVersion生成一套并行candidate结果，不覆盖当前active。

### Resume

同一个run失败或中断后的继续执行。必须使用相同idempotency_key和配置指纹，不创建第二套重复结果。

## 5. 发布与回滚

发布必须是数据库事务：

1. 验证candidate证据链完整。
2. 验证质量门禁和机器报告通过。
3. 将当前active版本整体标为superseded。
4. 将candidate整体标为active。
5. 更新profile的current_release指针。
6. 写入审计日志。

任一步失败必须整体回滚。

回滚只切换已存在的版本状态和current_release指针，不重新调用LLM，避免同一版本产生非确定性内容。

## 6. 保留策略建议

| 数据 | 默认策略 | 备注 |
| --- | --- | --- |
| RawFeedback正文与来源元数据 | 长期保留 | 是证据链根；受隐私/合同期限约束 |
| 原始API大payload | 可配置，例如90天 | 保存哈希、关键字段和对象存储引用 |
| 截图/音视频资产 | 按授权和存储策略配置 | 到期后保留哈希与失效状态，不伪装为可查看 |
| Signal及需求资产版本 | 长期保留 | 旧版本进入superseded/archived |
| PipelineRun与审计日志 | 长期保留 | 支持复现、问责和成本核算 |
| 测试/样例数据 | 独立namespace并定期清理 | 永不进入production默认查询 |

具体天数不得硬编码，应由数据来源授权、隐私政策和业务需求配置。

## 7. 前端规则

默认视图：

- 只显示当前production/profile的active release。
- 显示数据截止时间、dataset version、run ID、模型/算法版本。
- 明确显示新增、更新、沿用、失效的数据数量。

历史视图：

- 可按run和dataset version查看。
- 可以比较两个版本的新增/删除/合并/拆分主题和需求。
- 可执行受权限控制的promote/rollback，而不是直接删除数据库记录。

## 8. 不应采用的方案

- 每次运行前清空全部旧表：会破坏证据链、审计、对比和回滚。
- 每次对全量历史数据重新调用LLM：成本高、结果漂移且无法判断变化原因。
- 永久累积但不标版本：会让前端混合展示互相矛盾的需求资产。
- 直接覆盖旧信号或主题：无法复现当时的产品决策。
- 只按created_at判断最新版：不能保证一条完整资产链属于同一发布版本。

## 9. 最终决策

SignalMiner采用：

> 原始证据不可变revision + 日常增量挖掘 + 算法升级并行重算 + 候选版本原子发布 + 旧版本可追溯回滚 + 删除事件沿证据链失效传播。

P13-5负责实现本策略；在P13-5通过前，不得把当前累积式行为描述为已具备数据生命周期管理。
