# D3-M2 现有Chrome真实材料验证

验收日期：2026-11-10。

结论：**现有Chrome辅助读取 → 材料导入 → 来源快照 → 机会候选预览通过。批量重复计数修复通过。** 本轮使用Codex的浏览器界面能力读取当前页面，不能将其写成项目MediaCrawler按钮已成功实采，或项目已自动复用普通Chrome。

## 本次范围与用户约束

用户明确：只做国内平台，已经在Chrome打开并登录小红书，不新开窗口登录，重点验证登录后的读取。Commander已停止专用任务 `e6891dfb15ba49cfa181ef84c90f4f1a`，随后全部真实读取均在用户原有Chrome标签页执行；没有复制Cookie、开启主Chrome调试、修改网络或再要求用户登录。

Chrome连接器仅暴露另一个profile且没有可用标签页，因此采用原生界面可访问性读取现有Chrome。项目已有批量接口接收真实材料；没有通过未知网页脚本、隐藏状态或账号资料提取内容。

## 真实结果

| 环节 | 本轮结果 |
| --- | --- |
| 搜索 | 当前Chrome搜索“效率工具”，打开实际返回的笔记 |
| 正文 | 1篇，标题《DSH 侧栏太挤？我给会话做了个「最近分区」》，笔记ID `6af1161c000000002c032019`，描述正文242字符 |
| 评论 | 选取3条已加载非作者评论；未展开回复，未验证DOM层级，故不声称全部是一级评论或覆盖全部11条评论 |
| 来源材料包 | 保留访问URL、笔记ID、采集时间、原文和页面显示的相对时间；评论独立ID、精确源时间未知，未伪造 |
| 导入 | 隔离SQLite实际新增4条，回读4个真实反馈ID，页面可查看 |
| 来源核对 | 4/4快照verified，正文逐字一致，原始URL与raw_payload正文保留；评论标parent_page，不能直达评论 |
| 重复导入 | 修复后实际回执0新增、4重复；ID、4条快照、数据库行数均保持不变 |
| 机会分析 | 从UI勾选这4条真实材料，显式触发配置模型；返回2个待验证候选，3处引用逐字匹配已存正文 |
| 资产 | 仅候选预览，没有写入正式机会/需求资产；预览与导入没有自动调用模型 |

真实反馈ID按材料包顺序：

- `rfb_a1d3ba1ccd424d6fb7b5`：笔记正文。
- `rfb_26909df2820a414abedc`：“安装了，好用”。
- `rfb_f9c628b26ebf443a80fa`：“这个很有用，不破坏分区的情况下，能快速找到最近的会话”。
- `rfb_51f448879a6b4b7ba1bb`：“太实用了，精准解决痛点”。

候选是“多会话状态聚合侧栏”和“不破坏原有分区的最近会话快捷入口”。两者来自同一笔记及其评论，且原文已经介绍一个现有插件。它们只能证明材料进入了分析链，不能说明出现两个独立市场机会或建议立即开发。模型没有把两条泛泛称赞当作具体问题依据。

## 本次发现并修复的问题

重复导入最初复用原ID、保持数据库4条，却仍回报4新增0重复。Commander的计数断言确实失败；随后按窄范围指令交现有Executor修复，未将失败计作通过。

修复仅在原入库事务结果上附加inserted信息，原 `ingest_feedback(...) -> str` 兼容；batch按实际commit/复用统计。未改来源键、快照、legacy或并发winner条件。独立服务重启加载修复后，在相同真实4条材料和同一隔离库复验，得到 **total4/ingested0/duplicates4**，实际ID和快照不变。

此前安全根因诊断v2的代码交付在11月9日冻结，Executor因额度中断未完成正式报告。Commander已实际审读并独立运行437项后再启动验证；本轮没有用诊断改动冒称MediaCrawler搜索问题已解决。

## 独立检查和证据

最终受影响Python **445 passed，exit0**；Node **26/26，exit0**；Ruff、编译、JS语法逐项exit0；**36/36历史测试SHA不变**。Python有一个既有Starlette/httpx弃用warning。计数修复含真实SQLite唯一冲突/rollback、legacy、混合/批内重复、预校验和错误传播测试。

证据目录：`outputs/D3-M2/commander-20261110/`。

- `xhs-existing-chrome-batch.json`：实际4条材料，capture_method=manual_browser，capture_version标明界面辅助读取，未伪装上游导出。
- `real-import-response.json`、4份 `rfb_*-snapshot.json`。
- `duplicate-response-pre-fix.json`：真实错误计数；`source-provenance-verification-final.json`：修复后实际回执、快照和行数断言。
- `opportunity-ui-result.txt`、`opportunity-evidence-verification.json`：本次UI结果和3处逐字引用核对。
- `ui-real-opportunity-evidence.png`：候选、引用、父页面定位与快照状态；`xhs-existing-chrome-note.png`：真实原页面。
- `pytest-final.txt`、`node-tests-final.txt`、`static-gates-final.json`、`final-handoff-state.json`。

IAB文件上传/下载未作为通过项：上传改用已有本地批量接口；候选下载点击后没有发现本次生成的下载文件，结果已另存本地UI证据，不冒称下载导出成功。一次截图定位坐标超出用户调整后的窗口，读取新截图后已改用实际坐标，最终截图包含正确结果区域。

## 交接和剩余边界

18817使用 `outputs/D3-M2/commander-20261110/acceptance.sqlite`，保留为本次核对页面；没有活动采集任务。用户既有18816等服务未停，原Chrome标签页保留在所读笔记。没有业务库写入；快照与材料包都保存在项目本机。

项目自带一键采集尚未验证为能复用现有Chrome，B站和微博也未进行本轮实采。评论独立ID/精确层级/源时间仍未知。此后继续应围绕真实内容与可重复采集推进，不恢复反复登录排查。

下一阶段指令：`docs/executor-instruction-D3-M3-existing-chrome-batch-20261110.md`。
