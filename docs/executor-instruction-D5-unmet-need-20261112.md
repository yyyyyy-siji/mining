# D5 执行指令：机会候选必须提供当前困难与尚存缺口

日期：2026-11-12。与D4连接工作并行，文件所有权分离；不是另起完整评分/评审系统。

## 目标与证据

用户完整目标是发现值得开发的产品/功能机会。D3-M3实际2候选、6处逐字引文全部匹配，但一项重述Qoder已提供的周报功能，另一项把现有日志/消耗可见/敏感操作确认推断成未满足信任痛点。现prompt已经禁止纯推广/赞美，故不能只重复加强prompt就声称修复。

## 修改范围

质量Executor：仅 `signal_miner/pipeline/opportunity_discovery.py`、`signal_miner/routes/assets.py` 的机会发现请求/调用、新增 `tests/test_opportunity_admission.py`、本阶段交付报告。不要改main、Chrome模块、数据库、旧测试或frontend。

前端Executor继续拥有app.js及自身新增测试；在根代理交接后，把下列真实UI选择/结果接入，不互改文件。

## 最小契约

- `POST /api/v1/opportunities/discover` 增可选 `require_unmet_evidence: bool = false`；保留既有请求和旧调用默认行为，标明兼容边界。
- 真实机会页增加默认选中的“只推荐有当前困难与尚存缺口依据的候选”控件；开启后发 `require_unmet_evidence:true`。关闭时说明是宽松线索预览。没有该新控件的历史测试/调用仍是既有行为，不修改旧测试。
- pipeline增同名可选参数。strict模式必须要求结构化need_assessment；没有该字段的旧模型响应不得回退为已通过。
- assessment最小区分：current_difficulty（statement及evidence）、current_solution（status=mentioned|unknown、description及evidence）、remaining_gap（status=explicit|unknown|already_addressed、description及evidence）、basis（current_complaint|feature_request|historical_resolved|solution_praise|unknown）。每条evidence都复用feedback_id+quote结构。

## 服务端门禁

1. 严格模式的当前困难和明确剩余缺口都需要本批原文证据。分别核对非空、ID属于实际分析材料、quote逐字命中正文；不能只因卡片任意一条evidence匹配就放行。
2. status=mentioned的现有方案也要原文依据；未知保持unknown，不凭外部常识编方案。basis为historical_resolved/solution_praise/unknown，或remaining_gap为unknown/already_addressed时，不作为严格模式候选推荐。
3. 将整条材料原文和可得父正文纳入本批上下文，提醒区分“过去很麻烦，现在已有办法”与“目前仍未解决”。不得把评论数当独立用户、把促销功能列表当缺口。不在本批的父正文不能暗中查询或混入。
4. 所有角色引文必须通过同一快照来源包装，并能在响应/导出中复核。补充“语义待核实/市场未验证”的明确标识；结构化模型判断仍是推断，不能声称统计准确率、语义保证或市场验证已完成。
5. 证据不够返回0候选并给清晰原因。不新增数值评分、DB写入、自动需求资产或自动外部产品检索。

## 前端与导出

严格模式默认启用；展示困难、现有办法、尚存缺口及各自原话，避免用户只见方案。清单导出包含质量模式和assessment证据。既有“尚未判断”、原话匹配/快照说明、显式分析及批次选择不变。

## 验收

新增负例覆盖D3-M3两种真实错误、缺失assessment、仅正面功能引文、角色证据错误ID/伪quote/来自标题、unknown缺口、历史已解决；新增正例覆盖当前具体困难+明确不足、直接功能请求、未知替代方案不编造。不能将关键词词典作为可靠语义分类器。

运行受影响Python/前端检查并保留退出码，原36测试SHA不变。旧schema与旧API调用仍兼容；strict调用缺证据必须0候选。当前真实D3材料可在隔离服务显式调用一次严格预览验证，只有Commander负责该真实模型/UI步骤。

交付明确哪些是确定的结构/逐字校验、哪些仍依赖模型判断。先交付冻结，根代理独立复验后继续D4真实自动采集→导入→机会判断的完整链路。
