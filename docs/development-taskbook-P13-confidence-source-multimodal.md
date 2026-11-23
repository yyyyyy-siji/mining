# SignalMiner P13 开发任务总书：可信信号、真实数据源与多模态证据

版本：2026-07-10  
状态：待逐阶段执行  
执行方式：Commander / Executor 双会话串行工作流

## 1. 总目标

将 SignalMiner 从“功能链路可运行的原型”升级为“输出可信、来源真实、算法可验证、证据可追溯”的信号挖掘系统。

本任务书不是要求一次性重写系统。P13-1 至 P13-10 必须串行执行：每次只向执行会话下发一个阶段；执行者提交交付报告后，由指挥官独立验收。未通过时只生成该阶段返修指令，不得提前开发后续阶段。

执行者质量缺陷控制指标见：`docs/commander-executor-quality-metrics-20260710.md`。

## 2. 当前基线与问题分级

以下结论来自 2026-07-10 对当前代码和 `signal_miner.db` 的只读审查。历史数据库可能混有样例数据，但足以证明当前安全门禁不足。

### P0：最高等级

#### P0-1 置信度并非真实概率，却被当作真实置信度使用

- `confidence` 由 LLM 自行输出，没有人工金标校准。
- 固定阈值 `0.5` 被用于过滤信号。
- 去重时以该分数决定保留/淘汰哪个信号。
- 前端以百分比和彩色等级展示，容易让使用者误解为准确率或统计概率。
- 没有区分 `model_self_score`、`calibrated_confidence`、`source_trust`、`evidence_validity`。

#### P0-2 默认 DeepSeek 路径使用伪 Embedding

- 当前数据库 1,425 条信号全部标记为 `deepseek_pseudo_embedding`。
- 伪向量由 80% signal_type 随机分量和 20%文本哈希分量组成，不表示文本语义。
- 同类型信号预期余弦相似度约 0.94，高于当前去重阈值 0.92。
- 当前 1,425 条信号中 1,408 条被 dismissed，淘汰率约 98.8%。
- 禁止继续把这一结果用于需求频率、优先级或趋势判断。

#### P0-3 聚类结果没有形成有效主题

- 当前 17 个主题全部为单信号主题。
- 聚类查询没有按 pipeline profile 隔离，存在产品反馈与视频信号混用风险。
- 新信号不会并入既有主题，只会在新批次继续创建主题。
- 固定距离阈值没有金标集、稳定性或轮廓系数等验证。

#### P0-4 旧数据和新结果没有版本边界

- 默认运行只处理pending原始反馈，但所有旧信号、主题和需求资产继续保留。
- 旧结果没有dataset_version、run_id、算法版本和“当前发布版本”边界。
- 新挖掘结果与旧结果可能在API和前端混合显示。
- 模型、Prompt、Embedding或阈值升级后，没有安全重算、对比、发布和回滚机制。
- 来源内容更新或删除后，没有确定的下游失效传播规则。

### P1：严重但可在 P0 安全门禁后处理

#### P1-1 数据来源存在多条绕过统一门禁的入库路径

GitHub、Webhook、CSV、人工/API导入没有统一经过同一个 ingestion service，造成 URL 校验、capture_method、profile、去重和审计语义不一致。

#### P1-2 多数平台只是策略登记或离线转换器

- 抖音、B站、微博、小红书 MediaCrawler 仍是 mock。
- 博客园、搜索、B站证据适配器主要接收调用方已有 JSON/文本，不主动获取真实数据。
- 平台出现在下拉框不代表已具备真实采集。

#### P1-3 历史数据可信状态缺失

- 当前 1,257 条原始反馈中约 670 条没有 external_url。
- 1,257 条均没有结构化 capture_method。
- 测试、样例、历史、已验证生产数据没有明确分区。

#### P1-4 多模态能力尚未进入挖矿管线

- 已具备主模型/多模态模型分离入口和能力展示。
- 当前 DeepSeek 仍是文本主模型；Google/OpenAI可作为独立多模态模型。
- 但图片、音频、视频尚未进入信号提取；没有帧、时间码、截图资产等媒体证据定位。

### P2：非阻断但应在发布前完成

- 静态 SPA 与 Streamlit 行为和文案不完全一致。
- 缺少数据来源、置信度校准、去重、聚类的运营质量面板。
- 交付报告曾出现验证脚本假阳性、报告与代码事实漂移，需要强化机器门禁。

## 3. 全局开发原则

### 3.1 真实性原则

- 禁止伪 Embedding 参与去重、聚类、相似检索和自动 dismiss。
- 禁止把 LLM 自评分数命名或展示为“真实准确率”。
- 禁止把 mock、样例 JSON、手工构造证据包描述为真实平台采集。
- 禁止自动伪造来源 URL、截图、OCR、作者或互动量。

### 3.2 可逆原则

- 所有 dismiss、合并、隔离操作必须保存原因、算法版本、阈值、主记录 ID 和被合并记录 ID。
- 原始信号和原始反馈不可因去重被物理删除。
- 算法升级后必须能够重新计算和回滚。

### 3.3 评测先于调参

- 没有冻结的人工金标测试集，不得以“看起来合理”调整置信度或阈值。
- 训练/校准集与最终测试集必须分离。
- 阈值必须随 embedding_model、版本、语言和 profile 记录，不得全局共用一个常量。

### 3.4 主模型与专用模型解耦

- DeepSeek可继续承担文本提取和资产生成。
- Embedding必须使用独立、真实的Embedding模型配置，不能依赖主LLM是否提供Embedding。
- 多模态模型作为独立资源，不强制替换DeepSeek。

### 3.5 交付真实性

- 每个验收脚本输出 JSON，包含 `checks`、每个子项 `passed`、顶层 `passed`。
- 顶层 `passed` 必须等于所有阻断子项的逻辑与。
- Markdown报告必须由同一份机器结果生成或逐字段核对。
- 外部API因无密钥不能执行时标记 `BLOCKED`，不得以mock测试冒充真实联网通过。

## 4. 严重等级与阶段映射

| 严重等级 | 问题 | 处理阶段 |
| --- | --- | --- |
| P0 | LLM自评置信度被当作真实概率 | P13-1、P13-2 |
| P0 | 伪Embedding参与语义去重和聚类 | P13-1、P13-3 |
| P0 | 98.8%信号被错误dismiss | P13-1、P13-3、P13-5 |
| P0 | 聚类未隔离profile且主题全部单例 | P13-4 |
| P0 | 旧数据、新结果和算法重算没有版本边界 | P13-5 |
| P1 | 多入口绕过统一来源契约 | P13-6 |
| P1 | 历史无URL/无capture_method数据污染 | P13-6 |
| P1 | 真实采集未形成垂直闭环 | P13-7、P13-9 |
| P1 | 多模态未进入证据链 | P13-8 |
| P2 | 双前端和运营状态不一致 | P13-10 |

## 5. 分阶段任务

## P13-1：置信度可信基线与伪向量熔断

### 目标

先停止产生新的误导性结论，不追求一次性提升算法效果。

### 开发方法

1. 将现有 `confidence` 明确定义为模型自评分数，增加可区分字段，例如：
   - `model_self_score`
   - `calibrated_confidence`（允许为空）
   - `confidence_method`
   - `confidence_model_version`
   - `evidence_validation_status`
2. 保持旧API兼容，但响应中必须明确置信度类型；前端将“置信度92%”改为“模型自评 0.92（未校准）”。
3. 对 signalType 做当前Profile白名单校验。
4. 检查每条 evidence 是否能在原始输入中找到；不匹配时不得标为已验证证据。
5. 伪Embedding只能用于测试夹具，生产/正式pipeline检测到 `_pseudo_embedding` 时必须跳过去重与聚类，并返回明确的 degraded/blocked 状态。
6. 禁止再用未校准模型自评决定 destructive dismiss。
7. 只标记历史问题，不在本阶段批量重写或删除1,425条信号。

### 验收标准

- LLM返回0.99时，API仍标识为 `llm_self_reported`，`calibrated_confidence=null`。
- 非法signalType不会入库为有效信号。
- 模型编造的evidence不会获得verified状态。
- 伪Embedding路径不会执行deduplicate或cluster，也不会新增dismissed记录。
- 前端不再单独显示没有限定语的“置信度XX%”。
- 现有1,408条历史dismissed信号数量不会因迁移自动增加或减少。
- 全量测试、迁移升级和回滚测试通过。

### 禁止项

- 禁止在没有金标集时声称“置信度已校准”。
- 禁止简单删除pseudo fallback后让pipeline静默失败。
- 禁止顺手重写聚类算法或批量清洗历史数据。

## P13-2：人工金标集与置信度校准

### 目标

建立可复跑的离线评测，让“提取得准不准”和“0.8是否接近80%正确”有数据依据。

### 开发方法

P13-2采用“自动预处理/预标注 + 小规模人工盲标 + 人工确认 + 主动学习”的混合方案。100条指**经过人工验证的最低样本量**，不要求100条全部从空白手工制作；机器预标注永远只是suggestion，不能直接成为gold label。

1. 建立脱敏评测集，初始不少于100条真实或经授权反馈，覆盖两种profile、主要来源和难例。
2. 自动完成资格筛选、脱敏、重复过滤、分层抽样、evidence区间校验和预标注候选生成，减少人工机械工作。
3. 推荐冻结分割为：50条development、25条calibration、25条test。
4. development和calibration允许展示机器预标注供人工确认/修改，但必须隐藏模型自评分；人类最终标签与机器suggestion分字段保存。
5. test必须完全盲标，不得向标注员展示DeepSeek预测、预标注、模型来源或模型分数，不得用于Prompt和阈值调参。
6. 双标数量不少于`max(20, ceil(总样本数 × 20%))`，优先从冻结test中选择；保留原始A/B标签、分歧和裁决结果。
7. 每条人工标签覆盖：是否可提取、信号类型、摘要要点、原文证据区间、隐含需求是否有依据。
8. 使用模型分歧、低置信区间、新来源、新profile、evidence失败、去重硬负例和聚类边界样本进行主动学习；每轮只追加最有信息量的样本。
9. 输出提取Precision/Recall/F1、类型准确率、evidence exactness、幻觉率及置信区间。
10. 在独立calibration集上使用可解释方法校准模型自评分数，记录Brier Score和ECE；样本不足或指标不稳定时保持未校准状态。
11. 不同模型、Prompt版本、profile分别生成评测报告。

### 子阶段

1. **P13-2-1**：标注协议、授权/脱敏、确定性抽样、预标注隔离和冻结manifest。
2. **P13-2-2**：人工标注导入、25条test盲标、按20%且不少于20条执行双标、一致性与分歧裁决。
   - **P13-2-2-1**：授权候选接入、人工任务包、标签导入和一致性工具。
   - **P13-2-2-2**：真实人工标注执行、双标一致性和分歧裁决验收。
3. **P13-2-3**：主动学习补充难例、提取/证据/幻觉指标与置信区间。
4. **P13-2-4**：独立calibration集拟合、Brier/ECE评测和校准概率发布门禁。

### 验收标准

- 人工验证样本数 ≥100，其中冻结test ≥25；test为盲标且不存在预测、模型分数或预标注泄漏。
- 双标样本数 ≥`max(20, ceil(总样本数 × 20%))`；A/B标签独立保存，不能只保留裁决后答案。
- 双标部分 Cohen's kappa 或等价一致性指标 ≥0.70；不足时必须先修订标注规范。
- 测试集提取Precision ≥0.85、Recall ≥0.75、F1 ≥0.80。
- signalType准确率 ≥0.85。
- 已验证evidence原文匹配率 ≥0.98。
- 无依据新增事实的幻觉率 ≤0.02。
- 校准后ECE ≤0.10；若未达到，只能保留“未校准模型分数”展示，不得发布校准概率。
- 评测脚本对故意错误样例必须失败，证明不存在假阳性。

### 混合方案边界

- 允许LLM为development/calibration生成预标注suggestion，但suggestion不能计入人工验证数量。
- 禁止在冻结test标注包中包含任何模型预测、模型身份、自评分或预标注字段。
- 禁止把模型间一致、规则标签、合成数据或LLM-as-judge单独当作真实正确性证据。
- 若暂时不完成最低人工验证集，系统可以继续作为候选分析工具，但`calibrated_confidence`必须为空，去重/聚类不得执行破坏性自动决策。

## P13-3：真实 Embedding 与高精度语义去重

### 目标

用独立真实Embedding替换伪向量，并建立高精度、可追溯、可撤销的去重机制。

### 开发方法

1. 新增独立 `embedding_provider`、`embedding_model`、`embedding_dimension`、`embedding_version` 配置。
2. DeepSeek继续作为文本LLM；Embedding可由OpenAI、Google、Qwen或经过验证的本地句向量模型提供。
3. 不同维度和模型向量不得混合比较；数据库和pgvector迁移必须验证维度。
4. 建立不少于200对去重金标样本，包含同义重复、同类型不同需求、否定关系、版本差异、跨语言等硬负例。
5. 在开发集选择阈值，在冻结测试集报告结果。
6. 去重结果保存duplicate group、canonical signal、相似度、模型、阈值、时间、算法版本和撤销状态。
7. 优先ANN召回候选，再做精排或规则确认；不得无限O(n²)扫描全库。

### 验收标准

- 正式路径中0条新记录使用pseudo embedding。
- 所有向量记录均有模型、版本、维度。
- destructive自动合并/淘汰的Pairwise Precision ≥0.95，Recall ≥0.75。
- 测试集必须包含至少50个硬负例，硬负例误合并率 ≤0.03。
- 相同输入重复运行结果幂等。
- 跨批次重复可以识别；不同profile默认不互相去重。
- 每个被dismissed信号可查询其canonical signal和判定依据，并可撤销。
- 历史伪向量不得直接沿用；必须重算或隔离。

## P13-4：聚类有效性、Profile隔离与增量主题

### 目标

让主题真正代表多个相近信号，并能够随新数据稳定更新。

### 开发方法

1. 聚类查询必须通过RawFeedback关联过滤pipeline_profile。
2. 对Agglomerative、HDBSCAN或等价方案做小规模对照实验，不预设某个算法必胜。
3. 阈值和参数按Embedding模型、语言和profile版本化。
4. 对噪声点和单例主题设置明确语义，不得用LLM命名掩盖聚类失败。
5. 新信号先尝试并入已有主题；不满足阈值时才创建新主题。
6. 主题合并、拆分和重算必须保留版本与成员历史。
7. LLM只负责主题命名/摘要，不参与掩盖成员不一致问题。

### 验收标准

- 产品反馈和AIGC视频信号绝不进入同一主题。
- 至少100条人工审查信号的主题纯度 ≥0.80。
- 人工判定同主题信号Pairwise F1 ≥0.80。
- 输出Silhouette或等价内部指标，但不得单独以该指标宣称业务通过。
- 单例主题率必须在报告中呈现；若测试集仍为100%单例则阶段失败。
- 新增已知同主题信号后，能够并入既有主题且不创建重复主题。
- 重跑幂等，主题成员变化有审计记录。

## P13-5：数据生命周期、数据集快照与运行版本

### 目标

明确每次挖掘与旧数据的关系：原始证据默认保留且不可变；新数据只做增量处理；算法重算产生并行候选版本；审核发布后替换“当前版本”；旧结果可追溯、可回滚但默认不混入当前视图。

详细策略见：`docs/data-lifecycle-policy-P13.md`。

### 开发方法

1. 建立`DatasetVersion`或等价数据集快照，冻结一次运行使用的raw feedback revision集合。
2. `PipelineRun`必须记录dataset_version、run_mode、profile、模型、Prompt、Embedding、阈值和配置指纹。
3. Signal、Theme、PainPoint、Opportunity、Requirement必须能追溯到run_id和dataset_version。
4. 原始反馈采用不可变revision：同一外部记录内容未变时幂等；内容变化时新增revision并将旧revision标为superseded。
5. 定义三种运行模式：
   - `incremental`：只处理新增或变化的原始revision及受影响主题。
   - `rebuild`：基于指定快照和新算法生成并行candidate版本，不覆盖当前版本。
   - `resume`：恢复同一失败/中断run，不创建重复派生资产。
6. 派生资产至少具有`candidate`、`active`、`superseded`、`invalidated`、`archived`状态。
7. 建立发布事务：candidate通过质量门禁后整体promote为active，前一active整体转superseded；不得逐表半发布。
8. 建立回滚事务：可把上一个已发布版本重新设为active，不重新调用LLM。
9. 来源删除采用tombstone和下游invalidated传播；除法律/隐私硬删除要求外，不立即物理删除证据链。
10. 测试、样例和生产数据必须使用不同namespace/dataset，不得共同进入正式运行。
11. 默认API和前端只显示当前active版本；另设历史视图按run、dataset和版本查看。
12. 大型raw payload和媒体资产采用可配置保留期，元数据、哈希和审计记录保留更久。

### 旧数据处理规则

| 场景 | 原始数据 | 旧信号/主题/需求 | 新运行行为 |
| --- | --- | --- | --- |
| 重复点击同一次运行 | 不复制 | 不复制 | resume或返回原run |
| 新增一批反馈 | 原记录保留，新记录新增 | 当前active继续可用 | incremental只处理新增/变化数据 |
| 原来源内容更新 | 新增revision，旧revision=superseded | 受影响资产进入待重算/invalidated | 只重算受影响链路 |
| Prompt/模型/Embedding升级 | 原快照不变 | 旧active继续服务 | rebuild生成candidate，对比后再promote |
| 新版本发布 | 全部保留 | 旧active→superseded | 新candidate原子切换为active |
| 新版本质量差 | 全部保留 | 旧版本仍可恢复 | rollback，不重新调用LLM |
| 来源删除/合规撤回 | tombstone或按政策硬删除 | 下游资产invalidated并退出默认视图 | 记录传播范围和审计事件 |
| 测试/演示数据 | 独立namespace | 不进入生产资产 | 仅测试run可见 |

### 验收标准

- 相同来源ID和相同content_hash重复导入，不新增raw revision。
- 相同来源ID但内容变化时生成revision 2，revision 1保留且为superseded。
- 相同idempotency key重复触发run，不新增第二套派生资产。
- incremental run只处理新增/变化revision，不重新提取全部历史数据。
- rebuild使用同一dataset snapshot生成并行candidate；旧active数据在发布前不变化。
- candidate未promote前不出现在默认API/前端当前结果中。
- promote必须原子完成；故意在中途抛错时不能出现一半新、一半旧的active链路。
- promote后旧版本可在历史视图查看，并可无LLM调用回滚。
- tombstone一个来源后，其所有下游派生资产可被完整定位并invalidated，其他来源资产不受影响。
- 任一Requirement可回溯run_id、dataset_version、算法配置和原始revision。
- 两种profile、测试namespace和生产namespace完全隔离。
- 迁移前后实体计数守恒；除明确测试事务外不得物理删除。

## P13-6：统一来源入库与历史数据治理

### 目标

所有数据入口使用同一来源、去重、profile、审计和证据契约；隔离历史不可信数据。

### 开发方法

1. 建立唯一 ingestion service，GitHub、Webhook、CSV、JSON、人工和平台适配器不得直接写RawFeedbackRow。
2. 统一输出新增、更新、重复、隔离、失败数量。
3. 增加数据可信状态：`verified`、`unverified`、`legacy`、`sample`、`quarantined`等。
4. 对历史数据生成只读盘点报告，不自动删除。
5. 缺URL、mock URL、缺capture_method、未知来源的数据默认不进入正式pipeline。
6. `raw_payload`脱敏并设置大小、保存方式和保留期限。
7. 修复Webhook：配置secret后，缺签名与错签名均拒绝。

### 验收标准

- 所有入库路由调用统一ingestion service，代码扫描不存在绕过路径。
- 批量导入全量预校验，任一失败时0条写入。
- 重复执行GitHub/Webhook/CSV不会触发唯一索引错误或部分写入。
- 当前1,257条历史数据全部获得可信状态；670条无URL数据不得参与正式pipeline。
- source_captured_at、raw_payload引用、screenshot/OCR字段结构化保存，不拼进备注后丢失。
- Webhook安全正负例通过。
- 数据治理报告包含处理前后计数，顶层合计守恒。

## P13-7：真实数据源垂直闭环

### 目标

先完成少量来源的生产级闭环，再扩展平台数量。

### 开发方法

1. 第一垂直切片固定为GitHub Issues/Comments。
2. 完成分页、增量游标、更新时间、幂等、429/超时重试、失败恢复和同步统计。
3. 第二来源选择低限制公开来源，例如博客园公开API或合规搜索API。
4. 建立SourceConfig和SyncRun：配置、游标、开始/完成时间、新增/更新/重复/失败、最近错误。
5. 平台状态分级：策略登记、离线解析、人工可用、真实采集、增量生产级。

### 验收标准

- GitHub真实API受控运行至少两次，第二次无变更时新增数为0且无重复错误。
- 中断后可从游标恢复，不重复写入已提交项。
- 模拟429、超时、5xx时有有界重试和明确失败状态。
- 真实联网因无凭证不能测试时阶段状态为BLOCKED，不得以mock替代最终通过。
- 前端显示来源真实完成等级，不能把“策略登记”显示为“已连接”。
- 第二来源复用同一同步框架，而不是复制一套独立入库逻辑。

## P13-8：多模态证据管线

### 目标

保持DeepSeek文本管线，同时让独立多模态模型处理图片、截图、音频和视频，并把结果纳入证据链。

### 开发方法

1. 使用现有primary/multimodal双模型资源；多模态未配置时明确blocked，不得退化成伪分析。
2. 建立MediaAsset模型：MIME、哈希、大小、来源URL、采集时间、存储引用、权限和保留期限。
3. 图片证据保存区域或坐标；视频保存时间码/关键帧；音频保存时间段/转写片段。
4. 长视频不得整段盲送，采用元数据、字幕、镜头采样、关键帧和分段汇总。
5. 多模态提取结果必须注明provider、model、prompt版本和输入资产ID。
6. 前端展示主模型和多模态模型能力，并展示每条信号对应的媒体证据入口。

### 验收标准

- DeepSeek主文本模型和多模态模型可同时启用，互不覆盖。
- 未配置多模态模型时，媒体任务返回明确blocked状态且文本任务正常。
- 图片测试样本能生成带asset_id和区域引用的信号。
- 视频测试样本能生成带时间码或关键帧引用的信号。
- 删除/不可访问资产不会继续显示为可验证证据。
- 前端显示实际provider/model/modalities，不根据名称猜测能力。
- 至少一个受控真实模型调用证据；无密钥时只能标记BLOCKED。

## P13-9：受限平台与人工辅助采集

### 目标

为B站、小红书、抖音等受限平台建立合规的浏览器可见内容、截图/OCR和人工确认闭环。

### 开发方法

1. 不绕过登录、验证码、风控或反爬。
2. 截图证据必须有asset_id、文件哈希、原页面URL、采集时间和OCR版本。
3. `source_note`不能代替真实截图资产。
4. 人工确认OCR文本与页面来源绑定，记录确认者和时间。
5. 每个平台独立记录允许的方法、授权要求、频率和限制。

### 验收标准

- 截图缺资产时拒绝，不接受仅备注通过。
- OCR文本可追溯到具体截图和原URL。
- 页面受限或登录过期时显示真实失败，不生成模拟数据。
- 每个平台至少提供一条完整正例和三条负例。
- 采集完成等级和限制在前端可见。

## P13-10：质量面板与发布门禁

### 目标

让使用者知道系统何时可信、何时降级、哪些数据不可用于决策。

### 开发方法

1. 建立质量面板：来源覆盖、新鲜度、URL有效率、重复率、隔离率、提取F1版本、ECE、去重Precision、单例主题率、同步失败率。
2. 静态SPA和Streamlit统一核心状态；若只保留一个正式前端，明确废弃另一个。
3. pipeline run保存所有模型、Prompt、Embedding、阈值、评测版本。
4. 发布前自动阻断伪Embedding、未校准概率文案、跨profile主题和不可信来源进入正式资产。

### 验收标准

- 面板数字可由数据库查询独立复算。
- 任一P0门禁失败时，系统显示degraded/blocked，不能显示“全部完成”。
- 前端不存在把模型自评分数显示为真实概率的文案。
- 发布门禁脚本至少包含一个故意失败fixture并正确返回非0退出码。
- 全量回归、API、浏览器和数据库守恒检查通过。

## 6. 每阶段统一验收命令

执行者必须根据阶段补充聚焦测试，但不得省略以下基线：

```bash
git diff --stat
git diff --check
.venv/bin/ruff check signal_miner tests
node --check frontend/static/app.js
.venv/bin/python -m pytest -q
```

涉及迁移时增加：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

涉及前端时必须启动本地服务并提供目标区域截图或DOM断言；证据保存到：

```text
docs/P13-X-screenshots/
```

涉及业务质量时必须生成：

```text
docs/P13-X-evidence/metrics.json
```

机器报告最小结构：

```json
{
  "phase": "P13-X",
  "checks": {
    "static": {"passed": true},
    "tests": {"passed": true},
    "business_metrics": {"passed": true},
    "runtime": {"passed": true}
  },
  "passed": true
}
```

顶层 `passed` 必须由所有阻断项计算；任一关键项缺失、false或blocked时不得为true。

## 7. 每阶段交付报告模板

```markdown
# P13-X 交付报告：阶段名称

交付日期：YYYY-MM-DD

## 结论

- 自评：PASS / FAIL / BLOCKED
- 机器证据：docs/P13-X-evidence/metrics.json

## 修改文件

| 文件 | 修改目的 |
| --- | --- |

## 数据迁移与兼容性

## 开发方法与关键决策

## 验收指标

| 指标 | 门槛 | 实际 | 是否通过 | 证据字段 |
| --- | ---: | ---: | --- | --- |

## 命令证据

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |

## 运行态/API/浏览器证据

## 负例证据

## 未覆盖风险

## 需要指挥官重点复核
```

## 8. 执行顺序

P13-1、P13-2-1、P13-2-2-1、P13-2-2-1A及P13-2-2-2A已独立验收通过。P13-2-2-2A fix-5已关闭源candidate缺失`near_duplicate_group_id`和非空near-duplicate group跨split两类READY假绿；最终报告见`docs/acceptance-P13-2-2-2A-final-pass-20260715.md`。下一阶段为 **P13-2-2-2B：真实人工标注、双标一致性与裁决**，执行指令见`docs/deepseek-instruction-P13-2-2-2B-real-human-annotation-execution.md`。该阶段当前受外部输入阻塞：真实授权候选仍为0，正式默认结果必须继续为`BLOCKED_INPUT_REQUIRED/exit2`；只允许生成输入阻塞报告，不得用AI、fixture、规则标签、测试密钥、空pack或内存override制造真实READY，不得提前进入P13-2-3、置信度拟合、P13-3或任何后续阶段。
