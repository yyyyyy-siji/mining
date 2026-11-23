# D4 当前 Chrome DOM 采集后端交付报告

日期：2026-11-12。执行范围：后端实现、真实搜索时序返修与离线验证。Executor 未连接或操作真实普通 Chrome；真实采集、导入与机会判断以 Commander 的独立验收为准。本报告不代表总目标完成。

## 1. 变更摘要

- [NEW] `signal_miner/connectors/existing_chrome.py`：严格读取默认 Chrome 根目录的 `DevToolsActivePort` 两行，构造明确本机 WebSocket 端点；持久连接、临时标签 ID、单活动任务、固定公开 DOM 选择器、原文预览批次和取消/超时处理。
- [NEW] `signal_miner/routes/existing_chrome.py`：8 个异步路由；复用应用 API key，补充浏览器同源与 loopback 限制。客户端不能提交端点、脚本、文件路径或采集范围外参数。
- [MODIFY] `signal_miner/main.py`：应用 lifespan 创建/释放自有采集器，注册认证路由。启动应用和读取状态均不触发浏览器发现或连接。
- [MODIFY] `pyproject.toml`：增加 `browser = ["websockets>=15,<17"]` 可选依赖。未给产品运行依赖增加 Playwright 或浏览器下载流程。
- [NEW] `tests/test_existing_chrome_D4.py`：73 项参数展开后测试，含真实本地 WebSocket 协议测试与独立 Chrome for Testing 渲染器 DOM 检查。

未编辑前端、旧测试、上游 MediaCrawler、顶层需求、主 `.env`、业务数据库、Chrome 设置或登录态。仓库已有大量历史工作区变更，Git 总 diff 不能代表本轮后端改动。

## 2. 连接与资源保护

采用自有窄 CDP WebSocket 客户端，不采用 Playwright `connect_over_cdp`。审计发现 Playwright 即便 `no_defaults=True` 仍会全局自动附加并启用 Network，因此产品代码没有依赖这一连接路径。

仅允许下列命令：

- 浏览器根连接：`Target.getTargets`、`Target.getTargetInfo`、`Target.attachToTarget`、`Target.detachFromTarget`。
- 仅本次选中 target 的 session：`Page.navigate` 和固定 `Runtime.evaluate` 正文/搜索选择器/导航文档元数据表达式。

无 `Target.setAutoAttach`、`Network`、Cookie、storage、Browser.close、Target.closeTarget、context.close 或启动浏览器操作。断开只关闭自有 WebSocket；任务结束尝试 detach 自有 session，留给清理的预算已计入 120 秒总限时。测试断言 wire 发出的实际方法属于白名单，并验证断开不发送关闭浏览器/标签命令。

发现文件不接受用户路径，有限长只读、拒绝非普通文件和软链接；端口仅限 1..65535，第二行路径严格匹配 `/devtools/browser` 或合法 ID 子路径。不会探测固定 9222、调用 `/json/version` 或打印端点/发现文件内容。ENOENT、访问被拒与无效元数据分别提供确定说明，不将它们解释为未登录。

所有浏览器请求带 Origin 时，只接受 `127.0.0.1`、`localhost`、`[::1]` 且与当前应用 base origin 精确一致的 Origin，错协议/主机/端口、null Origin、DNS rebinding Host 均拒绝。无 Origin 保留 CLI API 兼容；应用配置 API key 时仍需要 key。

## 3. API 协议

统一前缀 `/api/v1/existing-chrome`，已与前端 Executor 消息对齐。

| 方法 | 路径 | 结果 |
| --- | --- | --- |
| GET | `/status` | 纯内存状态 `{status,message,active_task,capabilities}`，不触发发现/网络/授权 |
| POST | `/connect` | 202；后台连接，最初状态 connecting；只尝试当前已有会话 |
| POST | `/disconnect` | 取消自有任务并关闭传输，返回 disconnected |
| GET | `/tabs` | `{tabs:[{id,title,url}]}`，仅公开国内 XHS 支持页面，不暴露原 target ID |
| POST | `/tasks` | 202；`{tab_id,mode,query,url,max_posts:1,max_comments:0..3}` |
| GET | `/tasks/{id}` | `{id,status,terminal,phase,mode,tab_id,message,error,created_at,finished_at,summary}` |
| POST | `/tasks/{id}/stop` | 终止活动任务，completed/failed/cancelled 保持各自终态 |
| GET | `/tasks/{id}/results` | 仅 completed 可读取 `{items,summary}`；不自动入库或调用模型 |

任务模式 `current/search/detail`，仅一个活动任务，最多 1 篇笔记与 3 条顶层已加载评论。任务批次只保存在内存中，最多保留最近 30 个；服务重启后失效。未完成、取消和失败均没有可导入结果。

状态枚举为 `disconnected/connecting/connected/authorization_required/unavailable`；任务枚举为 `running/completed/failed/cancelled`。确定错误为标准 HTTPException `detail={code,message}`，不回显 CDP/网络内部错误信息。

## 4. 采集边界和来源

目标标签允许国内 HTTPS exact host `xiaohongshu.com/www.xiaohongshu.com` 的首页、`/explore`、`/search_result`、`/search_result_ai` 以及正规单篇笔记路径。`search_result_ai` 仅作为 search/detail 导航起点，current 模式拒绝；固定 DOM 脚本绝不读取 AI 摘要。

搜索从该标签导航到标准关键词结果页，只读取实际笔记卡片并导航一篇。实际卡片如为 `/search_result/<24hex>`，转为同 ID `/explore/<24hex>`，保留 query；批次记录 `search_result_href` 与真实 `navigated_note_url`，并复核最终笔记 ID。current/detail 同样检查预期笔记 ID，避免切换到其他笔记后误生成材料。开始、导航及读取前后均校验页面 URL，跨域/国际站/浏览器错误页/标签关闭/验证遮罩都终止并说明原因。

固定选择器只读笔记标题、描述正文及最多 3 条顶层评论，不使用整页 innerText，不读隐藏 JS 状态，不提取账号资料。正文不沿用 512 字截断；100000 字符安全上限或正文容器裁剪/折叠均明确标为片段。评论正文与时间只取当前层，帖子时间排除评论区；无直接证据的评论 ID、父评论关系、绝对时间保留 null。可见日期文本单独留在 raw_payload，不补造年份。

若请求评论，正文出现后额外有界等待已加载评论或明确空状态（默认最多 3 秒，不加载更多）。未见评论和明确空状态时，结果说明“评论覆盖未知，不能认定真实零评论”。summary 的 `comment_coverage` 区分 `not_requested/loaded_comments/explicit_empty/unknown`。

每项材料兼容现有 IngestRequest，`capture_method=crawler`，`capture_version=mining-existing-chrome-dom/v1`，raw_payload 的 `acquisition_kind=existing_chrome_loaded_dom` 与 `selector_version=xhs-public-note-dom/v1` 明确项目自有采集，不冒充上游导出。保留真实采集时间、原始来源 URL、对象 ID、可见源时间、覆盖及不完整原因。没有获取图片文字、视频口播、未加载评论或楼中楼。

## 5. 依赖与静态自检

产品可选安装：`uv pip install --python .venv/bin/python -e '.[browser]'`，不会下载浏览器。本次项目环境已有 websockets 16.0。为运行独立 owned DOM fixture，经 Commander 明确允许，额外执行 `uv pip install --python .venv/bin/python playwright==1.61.0`，退出码 0，安装 playwright 1.61.0 与 pyee 13.0.1；没有下载浏览器，使用已有 Chrome for Testing 148 缓存，不使用用户普通 Chrome。

最终静态自检：

```text
$ .venv/bin/ruff check signal_miner/ tests/test_existing_chrome_D4.py
All checks passed!
exit 0

$ .venv/bin/python -m compileall -q signal_miner/connectors/existing_chrome.py signal_miner/routes/existing_chrome.py signal_miner/main.py
[no output]
exit 0
```

## 6. 测试运行结果

受影响测试覆盖发现文件、域名/路径/authority 攻击、纯状态、连接取消、标签过滤、当前 AI 搜索页导航、三种任务模式、正文与评论映射、完整长正文、折叠与安全上限、unknown/null 溯源、迟到评论、明确空状态、忙状态、任务取消/总超时、跨域与标签关闭、DOM 错误传播、批次独立、API key、同源/错端口/null Origin/DNS rebinding 防护以及 wire 命令白名单。

真实 fixture 测试：独立测试进程启动已有 Chrome for Testing，所有 HTTPS 请求由本地 fixture route fulfill，执行原样 production DOM script。确认 1200 字正文、3 条评论、伪 ID 保持 null、帖子不借用评论时间、裁剪标记、缺正文报错和登录遮罩报错；隐藏区、推荐区、子评论、第四条评论及脚本状态均不进入结果。此测试不是平台成功采集的证据。

```text
$ .venv/bin/python -m pytest tests/test_existing_chrome_D4.py -ra
73 passed in 3.87s
exit 0

$ .venv/bin/python -m pytest tests/
921 passed, 3 warnings in 60.45s (0:01:00)
exit 0
```

以上为导航返修后的最终全量，退出码 0；全部通过，没有测试跳过。总数同时包含本轮 Commander/前端新增测试。

3 条已有 warnings 来自 Starlette/httpx 弃用提示及 `test_embedding_safety.py` 两项 AsyncMock 相关运行时提示；未修改旧测试或旧服务消除它们，不将 warnings 隐去。

## 7. 接口手动校验结果（离线 ASGI）

下列实际输出来自独立 FastAPI + ASGITransport，发现函数显式注入离线失败，不读 Chrome 文件、不建立 Chrome 连接；这不是平台登录/采集成功证据：

```text
GET /status 200 {status:disconnected,message:尚未连接当前Chrome,active_task:null}
POST /connect Origin=https://evil.test 403 {detail:{code:cross_origin_forbidden,...}}
POST /connect [no Origin] 202 {status:connecting,...}
GET /status [after fixture failure] 200 {status:authorization_required,message:OFFLINE fixture: no real Chrome discovery was attempted,...}
GET /tabs 409 {detail:{code:not_connected,...}}
POST /disconnect 200 disconnected
```

完整任务成功/失败、results 终态门禁和停止接口均由认证 ASGI API 测试实际调用，fixture 原文仅在测试内存中，没有写入业务数据资产。

## 8. 待 Commander 继续的真实验收

代码与离线结果供独立验收后，由 Commander 协调用户在已运行普通 Chrome 的 `chrome://inspect/#remote-debugging` 开启并允许本次连接。Executor 未执行该授权动作、未读取真实 Chrome ActivePort、未发起真实连接，也未触发权限弹窗。

授权后需要在 MINING 页面验证真实连接、实际目标标签、三种模式中的可用路径、小批原文预览、停止/断开且用户页面保持打开，再继续原文导入、重复导入、快照回读及“未满足缺口”机会判断。平台 DOM 与 Chrome 当前会话授权机制仍需实际环境验收，离线测试不能替代。

## 9. 真实搜索导航时序返修

Commander 已取得用户明确授权，并在真实环境验证 current 模式可自动产出 1 篇正文和 3 条评论。首个真实 search 任务 `75032a33b1254757a61d022c549c1fd1` 约 0.35 秒失败，code 为 `invalid_target_url`；Chrome 最终已经处于 `/search_result/?keyword=...&type=51`。现场证据为 `outputs/D4/commander-20261112/live-search-attempt-failed.json`；该旧任务没有 phase，无法事后确定具体拒绝位置。

静态审查和独立 fixture 证明原实现有两处导航竞态：

1. `Page.navigate` 返回后立即执行搜索 DOM 脚本，旧 `/search_result_ai` 文档虽然属于允许的导航来源，却被搜索脚本的目标路径守卫立即拒绝。
2. 搜索页导航笔记后，旧 target URL 还可能是 `/search_result/`；立即执行 `note=True` 校验会在笔记文档提交前拒绝。
3. 真实 Chromium 在 `Page.navigate` 刚返回的首轮轮询中，`Target.getTargetInfo` 会短暂返回空字符串 `targetInfo.url == ""`（随后约 50ms 更新为目标 URL）；若在 `_navigation_handoff` 期间对空字符串直接调用 `validate_url("")`，会在 `navigate_search` / `navigate_note` 阶段立即抛出 `invalid_target_url`。`_navigation_handoff` 现仅在自发导航交接窗口内将空 `targetInfo.url` 视为尚未完成目标匹配的过渡态继续有界等待（超时仍报 `navigation_document_timeout`），非空非法地址与交接窗口外的空地址仍立即拒绝。

修复没有放宽域名、路径或 DOM 内容白名单，也没有将所有 invalid_target_url 变成重试。仅对任务自己发起的导航，先有界等待 TargetInfo 与独立固定元数据脚本返回的 `location.href/document.readyState` 同时指向本次目标。搜索文档核对关键词与 type，允许同一标准搜索路径的尾斜杠规范化；笔记文档核对对象 ID。期间只允许原始来源文档暂存，不读旧文档正文/结果/账号字段。跨域、账号页、其他非源非目标页面仍立即拒绝。

确切的 CDP “执行上下文已销毁/默认上下文不存在”等错误在 wire 层被映射为不含原报文的 `execution_context_changed`，仅导航交接过程对其有界等待，其他错误直接传播。交接超时为 `navigation_document_timeout`，不会冒充采集完成。任务 public 增加有限 phase：`queued/validate_source/navigate_search/read_search_results/navigate_note/read_note/complete`，ChromeError 的 error 同时携带 phase，方便真实复验定位；没有输出原始 URL 或 CDP 报文。

新增 fixture 覆盖旧 AI 文档、target URL 先更新但 document 尚旧、commit 瞬间 `targetInfo.url == ""`、独立搜索到笔记的第二次切换、上下文销毁、跨站/账号页立即拒绝及停留旧文档/空 targetInfo 超时。独立 Chrome for Testing 还原样验证旧 AI 路径的 SEARCH 脚本返回 invalid_target_url，真实所见 `/search_result/` 尾斜杠路径可通过目标文档匹配，并提取实际 DOM 卡片形状链接，且真实 Chromium `Page.navigate` 交接不再因首帧空 `targetInfo.url` 误报失败。

返修冻结 SHA-256：

```text
f3dcac9dc952755fca2aa817062b4484f0617a6652c73e7903e2b3e61d847b30  signal_miner/connectors/existing_chrome.py
6cfad15e874b389589f944de6147cb014294baec4b4b1dd18ba0cf49384d2896  tests/test_existing_chrome_D4.py
```
