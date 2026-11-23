# D3-M1 接入准备验收

日期：2026-11-06。更新结论：**安装、离线适配及接入回归通过；XHS真实登录启动仍需定向修复，本阶段整体尚未最终签收。** 文件名保留草稿链接，内容结论优先；不能将本报告解读成小红书/B站/微博实采均已通过。

## 独立结果

| 层次 | 实际验证 | 结论 |
| --- | --- | --- |
| Installed | 固定上游pin、干净checkout、原LICENSE/锁SHA、Python3.12.13、Node、真实Chromium、实际help与verify-only | 通过 |
| Offline/API | 最终337项Python回归，exit0；同一任务不同父对象、空简介评论、精确ID、XHS访问签名幂等、原URL快照、源时间和有限诊断 | 通过 |
| 前端行为 | 独立Node26/26、JS语法；初始只读、限量/取消、迟到响应、选择/导入/实际ID回读/快照与机会交接 | 通过；材料交接使用明确OFFLINE数据 |
| 真实UI启动 | 隔离服务18816，独立空SQLite，从数据源UI设置1篇/3评论并启动；越过首页超时后在旧登录按钮定位超时 | 登录入口返修中 |
| LIVE材料闭环 | 没有采集成功材料、真实导入或机会结果；等待阶段不代表扫码图显示 | 未通过 |
| B站/微博LIVE | 未启动平台任务 | 未验证 |

定向Ruff、编译、JS语法均exit0。36个既有测试SHA与本轮起点一致，没有删除或减弱原断言；D1/O2/鉴权/来源回归包含在337项中。没有写业务数据库、密钥、主Chrome配置，也没有提交Git/PR。

## 实网问题与修复证据

1. 首次UI任务 `cfd227a0257647a3a0aac979ef36516f` 失败，无材料，原始日志未泄露；诊断不足导致不能定位。新增有限阶段/错误类别/相对栈帧，并以含敏感样例的离线负例验证。
2. 第二次 `e41c861fef7440d59e3491e11a0a4225` 定位到首页Page.goto默认load等待超时，浏览器已能启动。其余平台/网络根因不能据此推断。
3. 仅首次受控XHS官方首页改等DOMContentLoaded，保持30秒上限、TLS和后续导航。第三次 `f154ee966507427e83f84048437fef1f` 越过首页导航，随后在xhs/login.py:182硬编码XPath点击超时（约77秒exit1）。waiting_for_login早于扫码图就绪，Commander已撤回提前发出的用户登录提示；没有采集成功。
4. 已下发 `docs/executor-instruction-D3-M1-manual-login-fix-20261106.md`：用户自己在专用官方页面发起登录，桥接仅等待完成；当前尚未交付/复验，不预写成功。

TMPDIR过长曾是待证假设，最终没有修改；Python标准AF_UNIX限制不等同macOS Chromium扩展地址结构。没有按猜测修环境。真实任务全部由Commander通过UI启动；Executor未自行请求平台。

## 证据与后续

本地证据在 `outputs/D3-M1/commander/`：最终pytest-navigation-fix.txt、node-tests.txt、installation-verify.json、pre-live-checks.json、三次live-attempt.json、verified-code-hashes.json，以及ui-ready.png / ui-first-live-failed.png / ui-waiting-for-login.png。未留存扫码图、Cookie、账号密码或原始上游日志。

用户已确认普通Chrome小红书网页登录，但独立profile不会继承该会话；第三次任务已失败关闭，旧登录请求暂不操作。后续任务总时限10分钟，超时/用户选择稍后则停止，并按实际结果更新，不伪装成成功。闭环验证指令已准备于 `docs/executor-instruction-D3-M2-xhs-live-20261106.md`，须先完成当前返修。

缺陷门禁：有限诊断已在第二/三次实网失败中定位具体阶段，首次首页等待修复已越过导航阻断；登录就绪、平台采集及证据闭环门禁尚未证明。不能用总体passed掩盖LIVE待办。
