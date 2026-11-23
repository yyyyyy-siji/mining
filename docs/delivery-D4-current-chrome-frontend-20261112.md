# D4 / D5 前端交付报告

日期：2026-11-12。交付给 Commander 独立验收；离线检查不代表已连接真实 Chrome、已实采或已验证市场需求。

## 1. 变更摘要

- [MODIFY] `frontend/static/app.js`：数据源页首位新增「使用已登录 Chrome」，挂载仅读取本地连接状态，用户显式点击后才连接。说明 Chrome 144+ 在 `chrome://inspect/#remote-debugging` 开启远程调试及允许本次连接；`authorization_required`、`unavailable` 明确区分连接授权与平台登录。
- [MODIFY] 当前 Chrome 面板支持连接/断开、合格小红书标签、当前笔记/关键词/单链接、固定 1 篇及 0–3 条已加载评论、开始/停止/手动刷新、原文预览、勾选导入、来源快照、机会页交接。保留旧采集器，标题改为「MediaCrawler 独立浏览器采集」。
- [MODIFY] 显式连接后每 1.5 秒自动读取状态，最多 40 次；开始任务后最多 85 次。完成自动读取原文结果；终态、断开、离页取消 timer。保留手动刷新，达到自动刷新预算会明确提示。离页只停止前端刷新，后台任务需显式停止或断开。
- [MODIFY] 仅 `completed` 读取结果，失败/取消不展示半成品。批次上限 4 条、1 篇正文/3 条评论；保留全文、采集范围、未知 ID/时间、版本、raw_payload，不作 512 字符截断。动态原文、标题和角色引文使用文本节点或 HTML 转义。
- [MODIFY] 导入复用 `/feedback/batch`，保留完整所选材料。按回执的逐条 ID 关系回读实际存量，核对 ID、profile、source_type、原文和标准化笔记 URL。仅排除 xsec 访问签名及 utm 参数的变动；正文或来源错配则阻止交接。去重后按实际唯一 ID 展示快照；回读失败只允许重试读取，不再次导入。
- [MODIFY] D5 机会页默认勾选「只推荐有当前困难与尚存缺口依据的候选」，显式发现机会时发送 `require_unmet_evidence:true`；关闭后明确为宽松线索预览。缺控件的旧 fixture 仍只发旧字段。服务未确认严格开关或严格卡片缺 assessment 时不展示为严格推荐。
- [MODIFY] D5 卡片在方案前展示当前困难、已有办法、尚存缺口及各自原话，逐处复用来源快照查看器；未知替代办法保持未知。导出清单包含质量模式、三角色陈述、完整角色来源证据、人工判断及「语义待核实/市场未验证」。模式切换不自动分析，也不改变上一次结果的模式标识。
- [MODIFY] 通用 API 错误提示兼容服务端 `detail:{code,message}`，避免显示 `[object Object]`。
- [NEW] `tests/existing_chrome_frontend.test.cjs`、`tests/test_existing_chrome_frontend.py`：18 项 D4 离线交互检查及 pytest 包装。
- [NEW] `tests/opportunity_admission_frontend.test.cjs`、`tests/test_opportunity_admission_frontend.py`：7 项 D5 离线交互检查及 pytest 包装。

本执行者未修改 CSS、后端、业务数据库、历史测试、Chrome 配置或登录态；未打开 Chrome 连接弹窗或发起真实 Chrome 连接。

## 2. API 对齐

全部 Chrome 路径使用既有鉴权 API helper，前缀 `/api/v1/existing-chrome`。

| 操作 | 接口 / 使用字段 |
| --- | --- |
| 状态 / 连接 / 断开 | `GET /status`、`POST /connect`、`POST /disconnect`；`status,message,active_task` |
| 标签 | `GET /tabs`；`tabs:[{id,title,url}]`，仅 HTTPS exact 国内主机、无显式端口/credentials/fragment/控制字符/逗号 |
| 目标路径 | `/`、`/explore`、`/search_result`、`/search_result_ai`、两种 24 位笔记路径；AI 搜索页只作为 search/detail 导航目标，current 仅笔记 |
| 启动 | `POST /tasks`；`{tab_id,mode,query,url,max_posts:1,max_comments:0..3}` |
| 状态 / 停止 / 结果 | `GET /tasks/{id}`、`POST /tasks/{id}/stop`、`GET /tasks/{id}/results`；仅 completed 获取 items |
| 导入 / 快照 | 复用 `/feedback/batch`、`/feedback/{id}`、`/feedback/{id}/source-snapshot` |
| 机会 | 复用 `/opportunities/discover`，新增可选 bool `require_unmet_evidence`；need_assessment 三角色证据为既有来源包装 |

## 3. 静态与受影响自检

全部在仓库根目录运行。以下检查实际退出码均为 **0**：

```text
node --check frontend/static/app.js

node --test tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs tests/mediacrawler_frontend.test.cjs tests/existing_chrome_frontend.test.cjs tests/opportunity_admission_frontend.test.cjs
tests 51
pass 51
fail 0
skipped 0

.venv/bin/ruff check tests/test_existing_chrome_frontend.py tests/test_opportunity_admission_frontend.py
All checks passed!

.venv/bin/pytest tests/test_existing_chrome_frontend.py tests/test_opportunity_admission_frontend.py tests/test_community_preview_frontend.py tests/test_d1_source_frontend.py tests/test_mediacrawler_frontend.py -q
..... [100%]
```

51 项 Node 中原 26 项仍通过；新增 D4 18 项、D5 7 项。可控 timer 测试实际验证 40 / 85 次自动刷新上界，以及完成自动预览、离页/终态/断开清理。回读测试验证正文错误、来源错误、同 ID 对应不同正文均不交接，访问签名轮换仍可回读重复材料。

按 Commander 的并发协调要求，全量 `pytest tests/` 和 `ruff check signal_miner/` 由 Commander 在各模块冻结后统一运行。本报告不把它们标为已通过。

## 4. 实采与手动验收边界

- 本轮前端仅离线 fixture；不声称完成真实 Chrome 授权、连接、真实 DOM、真实导入或真实模型判断。
- Commander 独立验收应先检查初始状态不触发连接，再在用户允许当次 Chrome 连接后，选择真实国内小红书标签并执行任务，确认自动进入原文预览、导入去重、快照、机会页严格判断和导出。
- 结构/逐字引文门禁可检查证据对应关系；角色语义仍取决于模型和人工核实，市场验证尚未完成。

## 5. 冻结文件

交付时冻结以下 SHA-256，等待 Commander 独立验收；之后如需返工只依据 Commander 指令解冻。

```text
dd321d24d64c240108d9668470cc37094ab62b85eeb2d5e816607f9738af6ef4  frontend/static/app.js
f3a0de66605a7fead2fc714985dac8e71a3cc9960b1cd1e993df2b50e7d18354  tests/existing_chrome_frontend.test.cjs
1bc5751a5d7d7686ee4fd7bf9cd2e1b56fd9ae6336fed8273d405e30e6f5b8e2  tests/opportunity_admission_frontend.test.cjs
6acecd2646cb6fae4f116a1c20f112960a4eca3e80260a298f4f375fea797f04  tests/test_existing_chrome_frontend.py
298d83b4746d8da8b603148b63b56eec7a2eb2724b5fc404b0b82ee4482ebea8  tests/test_opportunity_admission_frontend.py
```
