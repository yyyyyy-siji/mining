# D3-M1：首页导航超时定向修复

日期：2026-11-06。先读 `outputs/D3-M1/commander/second-live-attempt.json`。

独立复验：安全诊断版315项通过；第二次UI真实任务e41c861fef7440d59e3491e11a0a4225运行约33秒后失败。诊断为TimeoutError / navigating_platform / timeout，实际栈定位固定上游xhs/core.py:104的首页Page.goto。浏览器启动已完成；尚未进入登录，无采集材料。TMPDIR/socket假设未获支持，禁止据此改动。

## 单一修复

在本项目bridge中，对小红书crawler的**首次官方首页导航**将默认load完成条件改为 `domcontentloaded`，保持原30秒或更短有界超时。仅影响本次任务的受控页面和精确官方首页；不重写上游源码，不扩大到任意URL或所有页面，不修改TLS/代理/验证码/主Chrome配置。不使用networkidle，不延长为无限等待，不自动重试。

这是待验证修复：超时可能源于动态页一直加载，也可能是网络；不得在交付报告把真实根因预写成已确认。若DOMContentLoaded仍超时，保留安全诊断，交由Commander判断本机网络。

允许修改bridge、新D3测试及交付/操作文档。保留phase诊断、原参数与正常/取消清理。新增确定性测试：仅首次XHS官方首页在默认等待参数下使用domcontentloaded；显式等待条件/其他URL/之后导航不被扩大修改；timeout与安全参数不弱化。跑受影响回归与语法，正式交付；不新增子代理，不自行实网重试。

Commander在UI按同样1篇/3评论再验证一次。若仍超时，不继续盲试。
