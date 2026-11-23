# D1 最终验收：国内来源接入准备与原文追溯

签收日期：2026-11-06（Asia/Shanghai）。结论：**接入准备范围通过；知乎授权实网验收尚未执行。**

## 验收范围

用户希望从公开社区及评论发现值得开发的产品或功能机会，并要求国内来源可追溯；当前没有知乎账号/Access Secret，明确要求先完成接入准备。

本轮完成知乎官方搜索线索入口、原文录入字段、来源快照和候选引用保护。现有 V2EX 用于真实网络端到端验证。小红书/B站仍通过实际可见原文材料录入，本轮没有实现自动登录、全站采集或通用评论接口。此前国内连接器中的 mock 未被改称真实采集。

按 commander-workflow，由执行代理实现，Commander 独立运行测试、隔离 API 与浏览器验收，另有两名只读代理预审。没有改业务数据库、密钥、数据库结构、MASTER 或 P13 冻结计划；本验收不代表正式金标/人工校准完成。

## 验证结果

| 项目 | 独立结果 |
| --- | --- |
| 知乎缺凭据 | status 明确 configured=false，preview 返回503；离线测试证明创建网络请求前停止，界面禁用检索，无示例结果 |
| 知乎接口准备 | 固定官方端点、单次最多10条、创建时间筛选、鉴权/限流/上游错误、安全导出等75项离线用例通过；没有带密钥的真实请求 |
| 真实来源留存 | V2EX 真实预览3条，选择其中1条导入；平台、对象ID、原URL、正文、作者、源创建/更新/采集时间、原始响应进入快照；预览不写库 |
| 幂等与版本 | 同对象同文重复导入保留首次记录；正文变化新增记录；相同局部ID但不同页面/域名，以及不同评论/平台分别保存 |
| 旧记录兼容 | 缺自身ID、仅父页面的不同评论不再误复用旧记录；旧父评论101与新父评论102分别留存，旧记录保持not_recorded |
| 完整性拦截 | 只改临时库正文、URL或raw_payload后均为mismatch，候选analyzed_count=0；恢复原值后重新verified。单元测试另覆盖作者、字段删除和来源包修改 |
| 原文门槛 | 产品反馈导入摘要/精选评论返回422；候选再次过滤。只匹配单一正文字段，父标题、生成标题或跨字段拼接不能成为quote |
| 浏览器快照下载 | 实际点击下载JSON；下载文件与API快照逐字段相同 |
| 真实模型引用链 | 浏览器只勾选1条真实V2EX，现有DeepSeek返回2张待验证候选、3处引用（2句独立原话）；全部ID/正文/URL/快照hash与该材料一致，其他离线夹具未进入结果 |
| 只读分析 | 真实模型调用前后临时库表计数一致；信号、主题、痛点、机会、需求资产、审计及运行记录均为0 |
| 最终网页 | 未配置提示、手工来源字段、来源快照、父页面定位和导出可用。人工录入默认manual_browser；原访问地址重载后确认使用D1新资源版本 |
| 自动回归 | Commander扩大后端/来源/旧O1/O2回归：**398 passed, 1 warning in 5.96s**，退出0。最后仅前端收尾后独立复跑Node **22/22**、两个pytest wrapper **2 passed**、node语法检查，均退出0 |
| 静态及范围 | D1 Python Ruff/编译、CLI help通过；runner AST 除ingest_feedback外与本轮基线相同 |

398项是指定相关回归，不宣称整个历史脏工作区所有测试或lint均通过。唯一警告是已有Starlette/TestClient弃用提示。最后人工默认值与资源版本修正只涉及前端，未改后端，未无故重复真实模型调用。

### Commander 回归命令

```bash
.venv/bin/python -m pytest tests/test_community_preview_routes.py tests/test_community_preview_frontend.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py tests/test_connector_response_models.py tests/test_connectors.py tests/test_github_connector.py tests/test_webhook_connector.py tests/test_auth.py tests/test_pipeline.py tests/test_pipeline_integration.py tests/test_source_acquisition_contract.py tests/test_source_evidence_D1.py tests/test_zhihu_search_preparation.py tests/test_d1_source_frontend.py -o addopts='' -q
node --test tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs
.venv/bin/python -m pytest tests/test_d1_source_frontend.py tests/test_community_preview_frontend.py -o addopts='' -q
```

## 已发现并修复的问题

1. 新key最初在存在external_id时忽略URL，可能合并不同网页的相同局部ID。现在稳定来源URL始终参与身份，仅移除utm_*，保留HN的id等身份query及fragment。
2. 兼容旧key最初遗漏父评论身份。现在严格比较父对象和定位，缺自身ID的评论不复用无法核实的旧对象。两项原复现均由独立预审代理再次验证通过。
3. 人工录入最初默认crawler。最终默认人工浏览，知乎补原文也显式人工；主动选择的合法方式保留。浏览器确认旧访问地址重载后正确。
4. 知乎状态最初展示重复配置说明与JSON数组，已改为一次说明及逐条正文。JS/CSS入口版本同步更新，避免继续使用旧资源。

## 可检查证据

- [最终汇总：关键门槛、当前代码哈希和清理状态](../outputs/D1/commander/acceptance-summary-20261106.json)
- [API独立验收：8项、真实/离线边界及改动拦截](../outputs/D1/commander/commander-api-acceptance.json)
- [真实V2EX预览](../outputs/D1/commander/live-v2ex-preview.json)、[已存来源快照](../outputs/D1/commander/live-v2ex-source-snapshot.json)
- [浏览器实际下载一致性](../outputs/D1/commander/commander-browser-download-acceptance.json)、[实际下载JSON](../outputs/D1/commander/browser-downloaded-source-snapshot.json)
- [真实模型候选/全部引用核对](../outputs/D1/commander/commander-live-candidate-acceptance.json)、[实际下载TXT](../outputs/D1/commander/browser-real-candidates.txt)
- [最终前端22项及wrapper检查](../outputs/D1/commander/final-frontend-checks-20261106.json)、[Python编译/CLI等检查](../outputs/D1/commander/static-checks.json)
- [最终代码SHA与runner范围核对](../outputs/D1/commander/verified-code-hashes.json)、[浏览器最终资源/人工默认值](../outputs/D1/commander/browser-final-manual-default.json)
- [知乎未配置页面](../outputs/D1/commander/browser-zhihu-unconfigured.png)、[真实来源快照页面](../outputs/D1/commander/browser-real-source-snapshot.png)、[真实候选引用页面](../outputs/D1/commander/browser-real-candidate-evidence.png)
- [执行交付报告](delivery-D1-domestic-provenance-20261105.md)、[用户操作说明](domestic-source-preparation-D1.md)

独立脚本首轮将V2EX节点误填为all，接口正确返回422；脚本改为已有支持的qna后通过，没有修改应用放宽限制。验证脚本的最终passed包含全部8项检查，不以文件存在代替成功。

## 使用与边界

在“导入反馈”填写实际正文、原链接及已知对象/评论信息，未知作者和时间留空；在反馈或机会引用处查看/下载来源快照。摘要仅作线索，不能替代原文。只有父页链接时明确“仅定位父页面”。

哈希verified只表示当前内容与留存快照一致，不能认证平台真实性、网页永久可达或市场需求成立。手工提供的文本明确未联网核验；历史记录没有快照时不补造。截图路径作为来源信息保留，不等于本轮已建立截图文件托管。

知乎未来在本机配置Secret并重启后，才进入单独的真实授权调用验收；当前准备通过不代表授权、额度或真实响应已经验证。小红书/B站自动采集不在本轮已交付能力内。

## 清理与后续

本轮临时服务 `127.0.0.1:18815` 已停止，唯一D1验收标签页已关闭，用户原有页面未动。[清理记录](../outputs/D1/commander/cleanup-20261106.json)。隔离SQLite及证据文件保留用于复核，业务库未写入验收材料。

已准备 [D2知乎授权小样本实网验收指令](executor-instruction-D2-zhihu-live-verification-20261106.md)，**未执行**。没有凭据期间，现有V2EX及国内可见原文录入可继续使用，不要求先完成大批人工标注。
