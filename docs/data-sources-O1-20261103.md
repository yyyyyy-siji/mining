# O1 数据从哪里来

核实日期：2026-11-03（Asia/Shanghai）。

2026-11-04 更新：现在可在网页「数据源」直接预览 HN/V2EX 并勾选导入，不必先跑脚本。参见 [网页采集操作说明](community-data-entry-O2.md)。下文保留 O1 来源核实与 CLI 用法。

## 项目已有定义

本轮用途是从公开社区和评论中发现值得开发的产品/功能机会。MASTER 定义多渠道原始反馈到痛点、机会、需求与PRD；P12来源策略覆盖社区、搜索、购物评价、二手及研发平台。没有把产品范围限定为某个行业或开发者工具。

首轮只缩小采样范围来验证使用价值，不把示范领域、关键词或平台硬编码为产品的唯一范围。

## 已验证的入口

| 来源 | 本轮实测 | 本轮获取方式 | 适合什么、缺什么 |
|---|---|---|---|
| V2EX 问与答 | `https://www.v2ex.com/feed/qna.xml` HTTP 200，50条Atom entry | 公开订阅流，限量导出正文、标题、原帖URL与时间；用现有custom来源、crawler采集方式，并注明public_feed | 中文工具使用、工作流、替代方案等实际困扰；只覆盖feed近期内容，不覆盖全历史或全部评论，有技术用户偏差 |
| V2EX 奇思妙想 | `https://www.v2ex.com/feed/ideas.xml` HTTP 200，50条Atom entry | 同上；可作为可选节点 | 创意和需求线索；作者自己提出产品点子不能当作多人真实需求 |
| HN / Algolia | `search_by_date` Ask HN 请求HTTP 200；研究探针近30天窗口返回936个命中，仅读取3条 | 无需本轮登录/密钥，按明确时间、关键词和数量限制读取；custom来源、official_api并注明平台 | 英语工具、创业、技术工作流；有明显人群偏差，不代表中国普通消费者 |
| GitHub Issues | 已有真实连接代码；本轮匿名访问公开仓库返回HTTP403 rate limit exceeded | 先保留已有连接器；持续读取需适当只读凭据与可用额度，并有上限、去重及退避 | 功能缺口、绕行方案、限制和维护者回应；单个项目bug不等于独立产品机会 |
| 其他中文社区、产品评论、购物评价 | 当前仅核实本地导入契约，未宣称完成各平台真实采集 | 用户可访问的原文+原帖/评论页链接，经现有manual/CSV/JSON入口导入；有权限的官方导出也可使用 | 可补足普通消费者、垂直行业声音；首轮不承诺任意平台全量自动抓取 |

V2EX首页JSON接口本轮也返回HTTP200、39条；为减少对接口历史与评论覆盖的假设，首轮脚本使用平台公开Atom订阅流。

## 一条材料至少保留什么

- 原始正文和标题，不把模型摘要当原文。
- 可直接打开的原帖/评论链接。
- 平台原始ID、采集方法和采集时间。
- 发帖/更新时间（来源提供时），以及父帖信息（来源提供时）。
- 清理HTML后的文本、准确的平台元数据和源端点；不将技术可访问性写成训练/正式金标用途的授权证明。

本轮采集脚本只导出JSON，不自动写入业务数据库。可先检查材料，再通过既有批量导入入口导入并选择本批材料发现机会。

## 已交付的真实采样与操作

2026-11-03 已实际导出 [V2EX 12 条](../outputs/O1/v2ex-qna-20261103.json) 和 [HN 12 条](../outputs/O1/hn-20261103.json)。采集脚本位于 `scripts/collect_community_opportunity_samples.py`，运行目录为本项目 `signal-miner`。复现时输出文件须不存在：

```bash
.venv/bin/python scripts/collect_community_opportunity_samples.py --source v2ex --v2ex-node qna --days 30 --limit 12 --output /tmp/mining-v2ex-new-samples.json
.venv/bin/python scripts/collect_community_opportunity_samples.py --source hn --kind both --days 30 --limit 12 --max-requests 3 --output /tmp/mining-hn-new-samples.json
```

采集后进入“导入反馈”上传 JSON，再到“机会卡片”勾选材料并点击“发现机会”。候选与人工备注仅保留在当前页面，使用下载清单保留结果。当前没有自动定时采集或全平台采集任务。

真实模型、浏览器与下载结果见 [O1 独立验收](acceptance-O1-final-pass-20261103.md)。

## 采什么才可能有用

优先阅读具体场景中的“做不到、步骤太多、一直手工处理、现有工具太贵、找替代、不得不绕开限制”。它们只是发现线索，不能仅靠关键词命中就确认需求。

把新闻、广告、作者自推、泛泛抱怨与实际使用经历区分开。保留现有解决办法和反例。原帖数量、评论数、点赞不直接等于独立用户数、市场规模或付费意愿。

候选卡应分别写：原文事实、系统建议、待验证问题。付费验证还需要后续真实用户接触或小原型验证，不在本轮自动采集中伪造。

## 当前接口边界的官方依据

- HN Search API：https://hn.algolia.com/api
- GitHub Issues API：https://docs.github.com/en/rest/issues/issues#list-repository-issues
- GitHub限额（匿名按IP计数，通常60次/小时）：https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Google Play开发者评论接口针对有权限的自有生产应用，不能用于任意竞品全量评论：https://developers.google.com/android-publisher/reply-to-reviews
- Reddit当前API要求事先申请批准，商业用途另需明确书面批准，暂不作为首轮必需入口：https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy

以上是本轮技术核实和平台文档边界，不是对完整性、长期可用性或任何再利用用途的保证。
