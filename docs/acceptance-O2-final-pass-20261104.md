# O2 最终验收：网页取得社区材料并交接本批机会分析

验收日期：2026-11-04（Asia/Shanghai）。结论：**本轮范围通过**。

## 验收范围

用户要求继续 O1 已完成的产品机会发现流程。本轮解决“第一批数据还需运行脚本再上传”的使用断点：产品反馈模式的「数据源」页面新增 HN/V2EX 采集预览、原文勾选、明确导入及实际反馈 ID 交接。继续沿用通用产品机会定位，不要求用户先指定行业。

按 commander-workflow，由执行代理实现，Commander 独立检查代码、运行测试及真实 API/浏览器验收。没有修改冻结需求、原 runner、数据库结构、模型配置、密钥或生产业务数据库；没有宣称 P13 正式阶段/金标校准通过。

## 验证结果

| 验证项 | 独立结果 |
| --- | --- |
| 最终后端真实 V2EX | HTTP 200，1次请求、3条材料、1.02秒；原文可用于现有导入契约 |
| 最终后端真实 HN | HTTP 200，3条材料、12.08秒，请求次数在上限内；非 mock |
| 只读预览 | 两源 API 预览及浏览器预览前后，临时数据库全表内容快照一致 |
| 网页选材导入 | V2EX 预览6条，仅勾选2条；确实只导入这2条，旧对照材料保持未选中 |
| 本批交接 | 实际已存 ID/正文/URL 回读成功；机会页显示选中2条，对照ID没有进入选中批次 |
| 不自动分析 | 导入/交接完成后，信号、主题、痛点、机会、需求、运行记录均仍为0 |
| 真实模型链路 | 显式点击「发现机会」，现有DeepSeek返回2个待验证候选、4处原文依据；下载清单中的全部ID/引文/来源均与所选材料一致 |
| 人工判断导出 | 实际填写“继续找用户了解”与验证备注，浏览器下载TXT，读取文件检查通过 |
| 重复导入 | 同一真实原帖再次导入后仍为原ID，临时库原始材料总量保持3，原来源元数据未被替换 |
| 失败/异步边界 | 离线测试覆盖401、422、429、502/504、读取超时、压缩/字节上限、迟到响应、回读失败仅重试GET；浏览器实测空查询结果如实为0条 |
| 自动回归 | Commander独立扩大到连接器/鉴权回归，**234 passed, 1 warning in 2.29s**；Node真实SPA函数行为测试 **11/11 passed**（其中一次也由pytest wrapper执行） |
| 静态/兼容检查 | 本轮Python Ruff/编译、app.js语法、CLI help通过；旧52项采集测试未修改；包内采集核心与O1原脚本逐字相同 |

本轮只证明真实材料可经页面形成可追溯的研究候选。两张试跑候选的实际市场价值、用户规模与付费意愿没有得到验证。

### 回归命令

```bash
.venv/bin/python -m pytest tests/test_community_preview_routes.py tests/test_community_preview_frontend.py tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py tests/test_connector_response_models.py tests/test_connectors.py tests/test_github_connector.py tests/test_webhook_connector.py tests/test_auth.py -o addopts='' -q
node --test tests/community_preview_frontend.test.cjs
```

两个命令均退出0。唯一警告为依赖内部的 Starlette TestClient/httpx 弃用提示，不是测试失败。本轮没有修改依赖或处理历史Streamlit F841，也不宣称整个工作区全量lint clean。

## 可检查证据

- [最终后端两源真实采集及数据库快照](../outputs/O2/acceptance-live-preview-20261104.json)
- [V2EX真实响应](../outputs/O2/live-v2ex-preview-20261104.json)、[HN真实响应](../outputs/O2/live-hn-preview-20261104.json)
- [浏览器预览前后数据库不变](../outputs/O2/acceptance-browser-before-import-20261104.json)
- [仅导入所选2条及未选中对照](../outputs/O2/acceptance-browser-import-20261104.json)
- [候选ID/4处引文/来源及模型后数据库验证](../outputs/O2/acceptance-browser-final-20261104.json)
- [重复导入与O1兼容验证](../outputs/O2/acceptance-repeat-and-compatibility-20261104.json)
- [浏览器真实下载的候选和人工判断](../outputs/O2/browser-exported-candidates-20261104.txt)
- [网页采集入口截图](../outputs/O2/browser-source-entry-20261104.png)、[导入回执截图](../outputs/O2/browser-import-receipt-20261104.png)、[精确选材交接截图](../outputs/O2/browser-handoff-20261104.png)、[真实候选截图](../outputs/O2/browser-candidates-20261104.png)
- [执行者交付报告](delivery-O2-community-ui-20261104.md)、[操作说明](community-data-entry-O2.md)

代码独立只读复核未发现阻塞：来源/时间语义沿用O1；采集不写库或调用模型；异步网络不阻塞事件循环；输入只允许固定来源；用户材料按文本显示；交接按实际ID回读；迟到结果不会覆盖新的选择。

## 运行与限制

当前验收页为 `http://127.0.0.1:18804/#connectors`，使用单独临时SQLite，保留作本地演示。最终后端加固后已重启该临时服务再实测；旧验收进程已停止。服务停止后地址不可用，以上文件仍保留。原业务数据、`.env`和密钥未修改。

网页HN最多3次请求、V2EX1次；每响应2MB、整批6MB。20秒是在读取期间检查的网络预算，正在阻塞的网络读仍受单次HTTP超时控制；24秒是HTTP等待上限，不能写成同步线程已被强制取消。等待超时后的worker结束前仍保持忙碌保护。

V2EX仅当前订阅流帖子，不含全历史/评论；HN和V2EX均偏技术人群。旧batch计数不可靠的问题没有扩范围重构，页面只显示实际处理/可用材料，不宣称全部新增。旧去重可能复用已有ID，因此以回读的已存正文和来源为准。

预览、候选和人工判断仍为页面会话态，刷新前需导出。新的批次交接会替换机会页原选择/候选/备注，页面已明确提示。

## 下一步

已准备 [O3机会质量验证指令](executor-instruction-O3-opportunity-quality-20261104.md)，本轮未执行。下一项应使用已有流程核查少量候选的替代方案和剩余缺口，不继续扩展功能来代替真实机会研究。
