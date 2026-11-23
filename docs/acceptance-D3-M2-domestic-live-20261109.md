# D3-M2 国内小红书实采验收记录

日期：2026-11-09。

结论：**真实采集尚未通过；已经失败的任务不能继续供用户登录。** 国内入口准备的独立验收仍见 D3-M1 报告，不将该准备验收等同于本阶段通过。

## 本次真实任务

- 任务：`7d5d2cb4888b41538c0eeaa514ca9667`。
- 固定上游：`54a3d92412f4b20c06b45f1d542b78dd92049d6d`。
- 范围：国内小红书，关键词“效率工具”，最多1篇、每篇3条一级评论。
- 北京时间14:12:05启动；14:17:19观测仍为 `waiting_for_domestic_page`；14:18:41已exit1终止，并非600秒超时。
- 最终诊断：`RetryError`，phase=`collecting`；受控frames为XHS search → limited_page → get_note_by_keyword → post。没有记录原始异常文本、响应、URL或Cookie，故底层请求原因尚未确定。
- 当前bridge只有人工登录确认为True且国内页检查通过后才对XHS写入collecting。因此页面与登录检查曾通过；不能据此推断用户具体做了什么。最终搜索失败，未取得材料。
- 用户14:19报告找不到窗口。此时任务已失败并执行cleanup，不应再叫用户寻找或登录这一个已经结束的窗口。已将面板手动刷新到真实失败终态。

## 分项结果

| 项目 | 状态 | 证据/限制 |
| --- | --- | --- |
| 国内访问等待 | passed | 初次实际进入非终态等待，results409，停止可用 |
| 国内页、人工登录检查 | passed（程序观测） | 最终阶段collecting；未记录人工操作或账号内容 |
| 关键词搜索 | failed | RetryError，请求底层原因未确定 |
| 笔记、评论 | pending | 任务目录无data文件；失败不开放部分结果 |
| 实际导入ID、来源快照 | pending | 没有材料，不用fixture补足 |
| 机会分析 | pending | 本轮未调用模型 |

证据目录：`outputs/D3-M1/commander-20261109/`，包括 `domestic-wait-final-task.json`、`domestic-wait-database-proof.json`、`ui-search-request-failed.png`。初次等待截图为历史状态，不再代表当前仍有有效任务。

## 定向后续工作

先按 `executor-instruction-D3-M2-search-diagnostic-20261109.md`补充安全根因类型和受控定位，独立复验后再决定一次真实验证。未确定原因前不重复要求用户登录、不盲目循环采集；不修改国内白名单、不适配国际站、不改用户网络或主Chrome。

服务18816暂保留供本阶段复验；没有活动任务。后续结束时清理自身服务或说明交接。

用户随后明确：其已完成登录，接下来只关注登录后的爬取验证。Commander将沿搜索、正文、评论、来源快照继续，不再重复请求登录，不将未知搜索异常归为登录问题。
