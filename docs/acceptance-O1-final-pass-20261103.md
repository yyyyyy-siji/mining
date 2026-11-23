# O1 独立验收：公开社区材料到待验证机会

日期：2026-11-03（Asia/Shanghai）。结论：**本轮约定范围通过**。

## 用户需求与范围

用户明确用途为“从公开社区和评论中，找值得开发的产品或功能机会”，并授权开始实施。项目 MASTER 定义多渠道用户原声输入、痛点/机会/需求资产输出，没有限定单个产品行业。本轮遵循这个定义，不把示范来源或技术领域硬编码为产品边界。

按 commander-workflow 分工，由执行代理修改应用代码，Commander 独立检查测试、真实采集、真实模型和浏览器结果。未修改冻结顶层需求，未宣告 P13 任何正式阶段或金标校准通过。

## 验收结果

| 项目 | 独立验证结果 |
| --- | --- |
| 公开材料 | HN 12 条、V2EX 问与答 12 条；分别 2 次/1 次请求；真实网络获取，不是生成样本 |
| 导入契约 | 两份 JSON 均可用于现有批量导入；保留正文、来源、平台原始信息和采集时间 |
| 真实模型 | 在隔离临时库导入 12 条 V2EX 材料，显式选择 5 条调用现有 DeepSeek，HTTP 200，4.99 秒，3 个候选、4 处通过原文匹配的依据 |
| 批次与来源 | 返回的依据全部来自所选批次；引用文本匹配真实材料，链接由服务器原始记录补充 |
| 数据库保护 | 机会发现调用前后，临时数据库所有业务表的内容快照一致；原始材料仍为 12 条，机会/需求/信号/痛点等资产仍为 0 |
| 页面 | 在隔离服务实际勾选 5 条、调用模型、看到 3 张候选和原文来源；原话与模型归纳/建议分栏，人工判断可填写 |
| 导出 | 实际点击下载并读取 TXT，包含 3 个候选、原始链接、“继续找用户了解”和手工填写的验证备注 |
| 自动回归 | 151 passed in 1.83s；新增 82 项，相关历史回归 69 项 |
| 静态检查 | 本轮服务/路由/采集脚本/新测试 Ruff 通过；app.js Node 语法检查通过；本轮 Python 文件及 Streamlit 兼容提示编译通过 |

测试命令：

```bash
.venv/bin/python -m pytest tests/test_opportunity_discovery.py tests/test_community_opportunity_samples.py tests/test_embedding_safety.py tests/test_evidence_validation.py tests/test_evidence_chain.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_prd_routes.py tests/test_prd_generator.py -o addopts='' -q
```

独立只读复核发现并修复了 V2EX 时间语义：缺少发布时间时不得用更新时间冒充。最终脚本仅按真实有效的 `published` 做发布时间和时间窗口判断；缺失/无效项明确跳过，`updated` 独立保留。新增 11 项针对性测试，复核确认无阻塞问题。已采集的 12 条 V2EX 均有真实发布时间，未修改或重新生成样本。

`frontend/app.py` 存在本轮前已有的第 263 行 F841；不能将本轮检查表述为整个工作区 Ruff 全量通过。工作区有大量历史未提交改动，本报告及执行报告仅覆盖 O1 指定文件的本轮新增/局部修改。

## 可检查的真实产物

- [V2EX 12 条原始材料](../outputs/O1/v2ex-qna-20261103.json)
- [HN 12 条原始材料](../outputs/O1/hn-20261103.json)
- [真实模型验收与数据库计数](../outputs/O1/acceptance-live-20261103.json)
- [真实模型响应](../outputs/O1/live-discovery-response-20261103.json)
- [浏览器与下载验收](../outputs/O1/acceptance-browser-20261103.json)
- [浏览器实际导出的候选和人工判断](../outputs/O1/browser-exported-candidates-20261103.txt)
- [候选预览截图](../outputs/O1/browser-opportunity-preview-20261103.png)
- [人工判断截图](../outputs/O1/browser-human-decision-20261103.png)
- [执行者交付报告](delivery-O1-opportunity-discovery-20261103.md)
- [数据入口与来源边界](data-sources-O1-20261103.md)

演示页：`http://127.0.0.1:18766/#opportunities`。这是使用单独临时 SQLite 的本地验收实例，原业务数据库未用于此次试验，密钥和 `.env` 未修改。演示服务停止后此地址不可用，以上文件仍可查看。

## 使用与边界

采集脚本限量导出 JSON → 在“导入反馈”上传 → “机会卡片”勾选本批材料 → “发现机会” → 核对原话/来源 → 记录后续行动并导出。采集脚本不会自动入库、调用模型或定时运行。

候选仅在当前浏览器页面保留，刷新或关闭会丢失，应先下载清单。此版本不把候选写成正式资产，不执行完整聚类管线，不依赖 Embedding。它验证的是“真实材料可追溯地形成研究候选”，不是市场机会质量或付费意愿已经验证。

V2EX 当前只覆盖公开订阅流的近期帖子，不含全站历史/评论；HN 及 V2EX 均有技术人群偏差。其他社区和评价仍可用可访问原文及真实链接导入，不能将本轮交付描述为所有平台的自动采集。GitHub 原有连接器的匿名额度问题没有在本轮解决。
