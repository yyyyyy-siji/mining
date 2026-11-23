# D5 交付：当前困难与尚存缺口的显式准入

日期：2026-11-12。父正文关系返修后重新冻结时间：2026-11-12T07:14:43+00:00（北京时间15:14:43）。本报告仅覆盖质量后端与新增离线测试，前端由独立Executor交付，真实模型/UI由Commander复验。

## 行为与兼容边界

`POST /api/v1/opportunities/discover` 新增 `require_unmet_evidence: bool = false`，pipeline同名关键字默认false。省略或false仍接受旧候选结构、保持原宽松线索行为；不会把旧模式称为已经审查未满足需求。严格模式必须显式发送true，不根据来源、行业或已有数据库状态偷偷启用。

true模式使用独立模型候选schema，强制提供任务书规定的`need_assessment`：

- `current_difficulty`：statement和evidence。
- `current_solution`：status为mentioned/unknown，description和evidence。
- `remaining_gap`：status为explicit/unknown/already_addressed，description和evidence。
- `basis`：current_complaint/feature_request/historical_resolved/solution_praise/unknown。

服务端只接受current_complaint或feature_request且remaining_gap=explicit的严格候选。当前困难、尚存缺口分别必须有非空角色引用；mentioned的当前办法也必须有引用。任一角色引用跨批、伪造、仅出现在独立标题、不是正文连续逐字子串或含模型自行提供URL，整卡排除；普通evidence中另有正确原话不能补救无效角色。没有完整assessment不回退旧模式。unknown/current_solution允许保留未知，不强迫模型编造一个产品。

角色引用与普通引用共用服务端来源包装，包含原文反馈ID、URL、父页面定位、quote_field、采集时间和快照hash/status。各角色引用也去重并入原`candidate.evidence`，保持已有证据展示与来源回读入口可用。严格prompt包含所有本批合格材料的完整留存正文及本批可匹配的`parent_feedback_ids`；没有额外查数据库、获取未选父正文或联网访问。

Commander独立审读发现初版URL备用关联会把同页兄弟评论误作父正文，已按`executor-instruction-D5-fix-parent-context-20261112.md`返修。父候选必须是同来源/平台且类型明确为post/article/answer/video的本批正文；comment和unknown不匹配。已知parent_id与正文external_id优先精确比较，二者齐备但冲突时不能用相同URL覆盖；只有任一ID缺失时才允许URL备用匹配。新增一正文加两条同URL评论测试（父ID已知/未知两种），验证每条评论只指向正文；正文不在本批时都为空。另覆盖comment/unknown伪父正文、共享URL但ID冲突、其他平台相同ID，以及正文自身ID未知时的URL备用。

响应新增：

- `require_unmet_evidence`：实际执行的质量模式。
- `semantic_status`：strict模型结果为model_assessment_pending_review；旧模式或没有合格材料而未调用模型时为not_assessed。
- `market_validation`：固定not_performed。
- `candidate.need_assessment`：strict为带完整来源引用的角色结构；旧模式为null。

缺失、不足或全被排除时仍是合法200/0候选，并在`excluded`写清原因。没有新增评分、Embedding调用、资产写入、状态变更或自动外部产品检索。

## 确定能检查的范围与语义风险

确定性检查包括模式开关、schema完整性、枚举状态准入、角色引用是否齐备/属于本批/逐字存在、服务端来源元信息、只读数据库不变。

角色分类、description与引用是否在语义上相符，仍来自模型判断。本实现没有关键词词典，也没有把模型自报状态称为独立语义验证。**如果模型把现有产品正面能力错误标成current_complaint及explicit缺口，且提供了确实存在的原话，结构与逐字门禁仍可能放行。** 因此不能宣称所有纯推广已被可靠识别，不能据此承诺准确率或完成市场验证。

D3-M3回归固定了当时的两种错误卡标题和原话结构：旧模式仍复现机械引用通过；相同旧结构在strict缺少assessment时确定排除。另外覆盖模型明确标记solution_praise/historical_resolved/unknown及缺口unknown/already_addressed时不准入。这不是对D3真实材料重新调用模型后的有效性声明。

## 文件范围

- `signal_miner/pipeline/opportunity_discovery.py`：严格schema、prompt上下文、角色门禁、来源包装与响应元信息。
- `signal_miner/routes/assets.py`：仅机会发现request新增bool及调用传递。
- `tests/test_opportunity_admission.py`：新增40项OFFLINE参数化业务断言（含父正文返修6项）。
- 本报告。

未编辑旧测试、frontend、main、Chrome模块、数据库、密钥或业务数据；测试只使用AsyncMock及独立临时SQLite，没有真实模型、浏览器或本地运行服务调用。

## 已运行检查

| 命令 | 实际结果 | 退出码 |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/test_opportunity_admission.py tests/test_opportunity_discovery.py tests/test_source_evidence_D1.py -o addopts='' -q`（父正文返修后最终版本） | 105 passed in 4.63s；含新增40项、旧机会与D1来源回归 | 0 |
| `.venv/bin/python -m pytest tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_community_preview_routes.py tests/test_embedding_safety.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q`（父正文返修前） | 107 passed in 2.90s；该组不覆盖strict父关联，返修后未重复运行 | 0 |
| `.venv/bin/python -m ruff check signal_miner/pipeline/opportunity_discovery.py signal_miner/routes/assets.py tests/test_opportunity_admission.py` | All checks passed | 0 |
| `.venv/bin/python -m py_compile signal_miner/pipeline/opportunity_discovery.py signal_miner/routes/assets.py tests/test_opportunity_admission.py` | 成功 | 0 |
| 对照 `outputs/D3-M1/existing-tests-sha256-20261106.json` 用hashlib逐文件核对 | 36/36历史测试文件SHA不变，changed=[] | 0 |

父正文返修后的当前版本实际通过105项；另107项邻接回归是本阶段返修前结果，没有写成全部已在最终版本重跑。Ruff、编译与36历史测试SHA核对均已在返修后重新通过。没有宣称重跑全量445项或旧26项前端；前端检查归独立Executor与Commander。

新增断言包括：当前具体困难与明确不足、直接功能请求、当前方案未知不编造、D3两卡旧结构重现与strict拒绝、只有正面/历史已解决basis、未知/已解决gap、三角色缺证据/跨批/伪quote/标题/改写空白/自填URL、0候选、完整本批父正文与缺失父正文、API默认兼容及strict切换、角色来源包装通过response_model保留、全表前后不变、服务端验证状态不能由模型自称。

## 冻结文件SHA256

| 文件 | SHA256 |
| --- | --- |
| `signal_miner/pipeline/opportunity_discovery.py` | `06854ee2186da7ffc6721f51460e398a7a4c8cb148b47bc99276ab080d56ffa9` |
| `signal_miner/routes/assets.py` | `14a84a50137c02df55def1e58213b7cc1b086867da12e7784130eabb0b9ca057` |
| `tests/test_opportunity_admission.py` | `37946f44810fa92065792a3ae563b28b89f09565fc71a0880cdb96e8b4b260ae` |

下一步由Commander独立检查后，在隔离服务显式做一次真实strict预览，核对前端请求确实传true、角色依据与排除原因是否可信，再继续D4自动采集→导入→机会判断链路。本交付不把离线通过冒充该真实闭环已完成。
