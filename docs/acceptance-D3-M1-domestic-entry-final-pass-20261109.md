# D3-M1 国内采集入口与等待控制验收

验收日期：2026-11-09。

结论：**接入准备和等待控制通过；国内小红书真实采集尚未通过。** 本报告取代旧的 `acceptance-D3-M1-final-pass-20261106.md` 草稿状态说明，不把准备完成解释为 LIVE 完成。

## 用户目标和范围

从国内公开社区帖子、评论中寻找值得开发的产品或功能机会，保留原文、来源链接和快照。用户明确只做国内平台，登录和验证由用户手动完成。当前先验证国内小红书，随后再验证 B站、微博；不开展国际站或其他海外来源工作。

## Antigravity 已完成的工作

Antigravity 完成了国内小红书人工登录入口：不再依赖已失效的固定登录按钮 XPath，等待用户手动发起登录，再调用固定上游的登录确认逻辑。Commander 收到的代码经独立复验为 Python 359 项、Node 26 项通过；未取得真实帖子或评论。因此，其进度是人工登录接入修复完成，实采闭环未完成。

## 本次继续完成的工作

1. 将页面检查失败细分为有限安全原因，实际任务 `836d224423a64734b843db266df99e89` 定位为主机不在国内白名单，未保存任意 URL、Cookie 或原始异常日志。
2. 新会话访问国内站会跳转，而用户普通 Chrome 保持国内站。公开无账号、关闭环境代理继承的连通探针也会跳转，故不能断言唯一原因是代理、账号或浏览器设置。本轮不修改用户网络或主 Chrome。
3. 对已知首次跳转保留专用窗口，状态为 `waiting_for_domestic_page`。仅在同一受控标签页恢复国内官方 HTTPS 页面后，才继续原 client 和人工登录流程；未增加国际登录或内容适配。
4. 等待门槛放在首次 `create_xhs_client` 之前。固定上游原方法会读取浏览器 Cookie、随后调用 pong，因此仅在登录入口等待不足以保证时序。本轮测试对 client、Cookie、pong 事件顺序作独立断言。
5. 保留单任务、600 秒总时限、手动停止、失败无部分结果等边界。前端复用现有任务消息和停止按钮。

## 独立验证

| 层次 | 结果 | 本地证据 |
| --- | --- | --- |
| 安装验证 | exit 0，固定 pin、独立 Python、浏览器及 upstream help 正常；`live_verified=false` | `outputs/D3-M1/commander-20261109/installation-verify.json` |
| Python 受影响回归 | exit 0，402 passed，1 个既有 Starlette/httpx 弃用 warning | 同目录 `pytest-domestic-wait.txt` |
| Node 前端检查 | exit 0，26/26 | 同目录 `node-tests.txt` |
| Ruff、编译、JS 语法 | 均 exit 0 | Commander 实际执行结果；交付命令见本次 delivery |
| 历史测试保留 | 36/36 SHA 一致，changed=[] | 同目录 `verified-code-hashes.json`；原基线 `outputs/D3-M1/existing-tests-sha256-20261106.json` |
| 实际 UI/API | 从 UI 启动一篇、三条评论任务；真实进入非终态等待，停止按钮可用；results 返回 409 | 同目录 `domestic-wait-live-attempt.json`、`ui-waiting-for-domestic-page.png` |
| 业务数据与模型 | 本轮没有导入或模型调用；隔离 SQLite 八张表均为 0 | 本轮只使用 `acceptance.sqlite` |

实际任务：`7d5d2cb4888b41538c0eeaa514ca9667`，2026-11-09 14:12:05（北京时间）启动，最迟约 14:22:05 到达总时限。初次截图仅包含下方区域，已用含国内访问提示、停止按钮和 0 条预览的正确区域截图覆盖。用户随后报告已登录，任务 API 当时仍返回 `waiting_for_domestic_page`；核对后用户确认登录的是普通 Chrome。已明确请用户在本次自动打开的独立窗口处理国内访问和人工登录；不共享普通 Chrome 登录态，不据用户报告冒称程序已确认会话。

此前一次 Commander pytest 命令误把测试路径拆开，exit 4，保存在 `pytest-page-check-command-error.txt`。纠正命令后 377 项通过，随后新增等待控制后 402 项通过。错误调用不计作应用回归，也不计作通过。

## 仍待完成

- 同一次专用采集任务确认国内页面和用户人工登录。
- 真实笔记、评论结果预览，显式选择导入隔离数据库，回读实际 ID 和 D1 来源快照。
- 取得足够需求证据时显式分析机会，逐字核对引用；没有需求机会时如实报告。
- B站、微博仅已有导出适配和离线验证，本轮没有真实采集通过记录。知乎仍缺本机官方凭据。

服务 `127.0.0.1:18816` 暂保留供本次交接；用户原有服务和 Chrome 未改。若等待超时，应记录 `timed_out`，不能循环重试或称任务仍有效。

下一阶段：`docs/executor-instruction-D3-M2-domestic-live-20261109.md`。

## 14:19 后续实测更新

原任务已于14:18:41以exit1结束，阶段为collecting，失败在XHS关键词搜索请求，诊断RetryError。窗口随cleanup已关闭，14:22只是原预计总时限，不是实际终止时间。用户报告找不到窗口时已经没有活动任务。此变化不撤销本报告对准备/等待功能的限定验收，也不使真实采集通过；后续真实状态见 `acceptance-D3-M2-domestic-live-20261109.md`。下一单一工作为安全根因诊断，指令 `executor-instruction-D3-M2-search-diagnostic-20261109.md`。
