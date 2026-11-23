# D1 执行指令：国内来源可追溯接入准备

日期：2026-11-05。用户要求“看看怎么接入国内平台，保证数据可溯源”；已回答没有知乎账号/Access Secret，要求“先完成接入准备”。

## 任务目标

交付最小可运行准备：**知乎官方检索线索 → 明确区分摘要/精选评论 → 取得或人工提供原文材料 → 保存来源快照 → 引文绑定本批记录和快照 → 页面回源/导出**。

本轮缺少真实知乎密钥，必须诚实显示“未配置”，不调用需要凭据的真实接口、不编造知乎实网成功。已有V2EX可作为真实网络材料验证来源链。小红书/B站沿用可见材料/原文录入入口，本轮不把旧mock改名为真实采集。

继续采用Commander/独立Executor分工。可派两个子代理分别处理知乎后端与前端，你负责溯源核心和集成；同时编辑文件需明确归属。

## 已核实问题与官方事实

- 现 API dedupe_key 只用 source_type_api+正文，同文不同URL/平台可能误合并。
- IngestRequest 不接 external_id/source_created_at；AcquisitionEvidence.to_ingest_payload 丢 raw_payload/结构化采集时间/OCR字段。
- 候选引用现在对 subject+正文拼接校验，可能引用父帖/生成标题；没有摘要/原文门槛与快照完整性检查。
- 知乎文档：https://developer.zhihu.com/docs?key=zhihu_search；鉴权：https://developer.zhihu.com/docs?key=authorization；官方页面公开文档JSON为 https://developer.zhihu.com/console/api/v3/docs 。后两项只读文档无需Secret。
- 搜索固定 GET https://developer.zhihu.com/api/v1/content/zhihu_search ，Bearer Secret + X-Request-Timestamp秒级时间戳，Query非空、Count<=10、单次请求，HasMore当前false。
- ContentText明确是摘要。CommentInfoList仅Content，没有独立评论ID/作者/时间；不能拆成完整可定位的用户证据。CreateTime是创建时间，EditTime不能冒充原始发布时间。
- 现zhihu来源策略不允许official_api，要明确新增该合法方式，不用custom绕过。

## 允许修改范围

- 新增 `signal_miner/utils/source_evidence.py`（或同等单一模块）构建/验证来源包及哈希。
- `signal_miner/routes/feedback.py`：来源字段接收、保留、源感知去重key、详情/来源快照返回；兼容原请求。
- `signal_miner/pipeline/runner.py`：**仅 ingest_feedback 的精确幂等/兼容旧记录逻辑**，不得改其他pipeline逻辑。
- `signal_miner/connectors/source_acquisition.py`：转换字段无损；`community_samples.py`：HN/V2EX补明实体/内容性质和真实ID/时间，明确Atom content与summary差异。
- `signal_miner/pipeline/opportunity_discovery.py`：正文引用范围、内容性质门槛、快照完整性、返回溯源字段；原最多30条/3候选/只读/无Embedding保护保留。
- 新增 `signal_miner/connectors/zhihu_search.py`；`routes/connectors.py`、`settings.py`、`utils/source_platforms.py` 的最小接入配置/状态/规则。
- `frontend/static/app.js`、`style.css`：局部知乎检索状态/线索展示，原文材料来源字段，来源详情/快照导出和候选溯源显示。
- 新增D1测试和必要文档。旧测试不删断言；若新需求确实改变旧精确字段断言，先回报，避免“修测试”掩盖回归。

## 禁止修改范围

不改MASTER/P13冻结计划、数据库结构/迁移、业务数据库、已有密钥或.env、不接入任意URL爬虫、不安装MediaCrawler、不执行登录/CAPTCHA/账号创建、不声称真实人标/校准完成、不修改旧聚类/PRD/视频算法。保留整个脏工作区，不reset/clean/提交。

## 实现要求

### A. 来源包与完整性

1. 在现有context JSON内保存版本化来源包，无需新表。至少包含：平台、实体类型(post/comment/answer/article/video/unknown)、external_id、原始URL、父帖/父评论ID及URL（可选）、定位等级（条目/父页面/未知）、内容性质(original_text/api_excerpt/curated_comment/ocr_text/manual_text/unknown)、覆盖范围、创建/更新时间、真实采集时间、采集方式/版本、原始payload。
2. 未提供作者/时间/评论ID就保持未知，不能借父帖属性填充。人工提供文本明确“用户提供，未联网核验”；原始正文、API摘要、精选评论、OCR各自标识，不发明“来源真实性已认证”。
3. `external_id/source_created_at` 进入现有对应字段；其他来源属性进context。源时间须有时区并统一可比较语义；SQLite回读丢tz时不能误判哈希。AcquisitionEvidence转换保留 raw_payload/source_captured_at/screenshot_path/ocr_text 等结构化值。
4. 服务端计算正文SHA-256和覆盖来源/正文/原始payload的快照SHA-256，存入来源包。API请求不得由调用方指定“已核验”状态；详情回读/候选分析时重新核对。哈希只能证明当前内容与留存快照一致，不能证明平台真实性或原网页永久可达。
5. 详情可查看并下载完整来源快照JSON：正文、来源字段、原始payload、哈希及核对状态；严禁携带配置/请求Authorization/Secret。历史记录没有来源包时明确“历史文本，未记录快照”，不自动补造或批量改写。

### B. 精确幂等与多出处保留

1. 新API导入按“pipeline_profile＋平台/实体身份（ID或原始URL）＋内容快照”生成稳定key，不能只按正文。相同正文不同URL/平台/评论ID必须分别保留；同对象同内容重复导入复用ID，正文变化新增记录而不覆盖原记录。
2. 避免把采集时间、搜索请求ID等每次变化的字段纳入幂等key而导致重复收录。完整snapshot hash可以变，幂等身份不能随每次捕获时间漂移；复用已有记录时保留其首次留存原文和时间并如实回读。
3. 如需兼容旧key，只在原URL、profile、精确正文及可核实对象身份均一致时复用；无从确认时保留新记录，不能错并。禁止自动修复/覆盖旧来源。保留唯一约束，处理命中幂等约束的重试，不让并发变成不明500。

### C. 候选证据

1. API摘要/精选评论不能直接进入“原文依据”机会分析，服务端必须过滤并给原因，不只靠UI。缺少正文时不因标题存在就通过。
2. 引文只匹配该对象的单一正文文本字段，禁止匹配subject/父帖标题/生成标题，也禁止跨标题正文拼出原话。实际title-only来源可把真实标题作为明确记录来源字段的文本，不能引用模型生成标题。
3. 有来源包时，快照不一致的材料拒绝用于候选；无有效证据的卡剔除；旧材料保持明确未记录快照状态。返回/导出包含feedback_id、quote_field、source_url、实体/父对象ID、定位等级、内容性质、创建/采集时间、snapshot hash/核对状态。
4. 只有父页URL的评论明确“仅定位父页面”，不能显示“直达该评论”。正文匹配不等于语义或市场验证，保留现有诚实提示。

### D. 知乎检索准备

1. 新增server-only `ZHIHU_ACCESS_SECRET` 配置（repr不显示，建议SecretStr）；不进浏览器/localStorage/URL/日志/导出。新增受既有API鉴权保护的只读状态，只返回configured布尔/能力/限制，不返回Secret。
2. 可用新增独立知乎preview入口，或扩展community preview；保留HN/V2EX兼容。来源为zhihu+official_api，不访问任意用户URL，不重定向、不分页/重试，最多10条、1个请求，沿用O2流式字节/并发/超时预算。
3. Query必填。days若使用，映射官方SortBy CreateTime:desc:(from,to)，并明确是创建时间范围。响应检查HTTP和业务Code：参数/鉴权/限流/上游错误各明确，不能假empty；缺Secret返回诚实未配置状态（例如503），不得联网或生成示例结果。
4. 保留SearchHashId、Query/Count/SortBy、采集时间、ContentType/ContentID、原始带溯源参数Url、CreateTime/EditTime、AuthorName、完整原始item和摘要hash。校验URL平台、类型与响应结构；不补造缺失属性。
5. 网页显示“知乎官方搜索（检索线索）”，摘要/精选评论分别标注，不能把它们写成“展开原文”。线索不直接送机会分析；提供原页面链接及用现有导入入口补充原文的操作路径，必要时保留线索原始记录作为参考。可下载线索来源记录。**本轮不必建立多级状态机/新线索数据库。**
6. 未配置时展示申请入口和本机配置说明，禁用误导性搜索按钮或返回明确错误，不展示mock笔记。用户已有“先完成准备”的明确授权，不要再次问域名/行业/批量人工标注。

### E. 网页材料与可追溯操作

原文导入入口可填写内容性质、平台对象/评论ID、父页、源时间等；默认“人工提供文本，未联网核验”而非“平台已认证”。不要求用户核对100条；只在补充所用少量材料时保留来源信息。候选和详情能查看快照并下载，即使源网页后续变化，也可知道当时保存的内容。对第三方文本安全转义，禁止失效异步响应污染新页面/新批次。

## 验收标准

### 静态/兼容

本轮Python Ruff/编译、app.js/CJS语法、CLI help通过。保留O1/O2回归、连接器/鉴权/反馈/来源/证据链测试；新增与本次变化相称的语义测试，不机械追求数量。

### 必须证明

- 不同平台同文、同平台不同评论ID同文分别入库，回源各自正确。
- 同对象同内容重复导入幂等；正文变化新增记录、旧引文/快照不变。
- ID/原始payload/创建时间/采集时间经预览→导入→详情→导出无损，未知字段不冒充父属性。
- 修改DB中的正文、来源URL或原始payload后，快照校验失败且候选排除；基线未动。
- 只在subject/父标题出现的引文被拒绝；摘要/精选评论不作为原文进入模型；缺评论定位如实显示。
- 知乎缺Secret零网络请求；错误不伪装empty；Secret不出现在响应/日志/快照；真实接口用mock明确标离线测试。
- 页面能看出配置缺失、内容性质和来源快照；保留O2精确ID交接及异步保护。
- 本轮没有真实知乎账号，不得把离线测试写成LIVE采集；Commander会用隔离库和已有真实V2EX材料做溯源端到端验收。

### 回归建议命令

```bash
.venv/bin/python -m pytest tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_community_preview_routes.py tests/test_community_preview_frontend.py tests/test_feedback_ingest_source_contract.py tests/test_source_acquisition_contract.py tests/test_source_clickthrough_contract.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_pipeline.py tests/test_pipeline_integration.py tests/test_connector_response_models.py tests/test_connectors.py tests/test_auth.py -o addopts='' -q
```

再加入本轮新增用例。若旧测试确因语义变化失败，先分类回报，不弱化源验证来让测试绿。

## 交付报告

`docs/delivery-D1-domestic-provenance-20261105.md`：最终文件范围、行为、命令/退出码、离线/LIVE边界、已知限制、缺Secret配置步骤。记录每个阻断问题及修复。工作区历史改动不计入本轮贡献，不创建PR或提交。准备完成和知乎真实运行验收必须分开表述。
