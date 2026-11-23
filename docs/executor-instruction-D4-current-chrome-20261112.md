# D4 执行指令：项目内连接现有 Chrome，完成小红书真实采集闭环

日期：2026-11-12。

## 总目标与本轮完成标准

用户确认总目标：从国内公开社区和评论中找值得开发的产品或功能机会。用户自行登录，MINING负责后续自动采集、来源留存和分析。本轮优先让一个国内平台在产品内真正跑通；不以新一批CUA手工材料或一份下一阶段指令代替交付。

本指令调整此前D3-M4“再手工取B站小样本”的执行优先级。保留旧证据及历史文档，不修改冻结顶层需求。

## 背景

当前普通Chrome版本157.0.8103.50，已登录小红书。现有MediaCrawler强制独立profile；不能直接打开上游CDP开关，因为上游会读Cookie、失败回退开新浏览器、cleanup关闭用户context。改用独立的项目自有DOM采集器。

采用Chrome144+官方当前会话授权机制：用户在 `chrome://inspect/#remote-debugging` 启用并允许本次连接。不能静默启用、重启Chrome、复制Cookie、要求再次登录或修改TLS/代理。先完成代码、离线测试及可核验连接页，再由Commander在必要授权点协调用户。

官方依据：https://developer.chrome.com/blog/chrome-devtools-mcp-debug-your-browser-session 。连接发现机制由只读审计代理核实后提供，未核实的行为不得硬猜成可用。

## 允许修改范围与分工

后端Executor负责：新增 `signal_miner/connectors/existing_chrome.py`、`signal_miner/routes/existing_chrome.py`、自有固定DOM提取资源文件（如需要），小范围修改 `signal_miner/main.py` 注册lifespan/route，`pyproject.toml`增加明确可选Playwright依赖，以及独立新增测试。可写本阶段安装/连接说明和交付报告。

前端Executor负责：`frontend/static/app.js`、`frontend/static/style.css`（仅必要时）、独立新增前端测试，以及本轮前端交付报告。后端与前端按下列API契约协作，禁止互改对方文件。

## 禁止修改范围

上游MediaCrawler checkout、旧采集器及旧测试、业务数据库、.env、Chrome配置/登录态、网络/TLS、其他项目。不得提交或输出Cookie、storage、私信、通知、账号资料。不得安装扩展、启动浏览器进程、启用真实Chrome调试或发起真实Chrome连接；这些由Commander在用户授权后验收。

## 连接与API契约

所有路由前缀 `/api/v1/existing-chrome`，复用现有应用API鉴权；页面只在用户点连接后请求连接。

- `GET /status`：只返回本地连接状态，不触发连接、Chrome授权弹窗或网络访问。状态至少含 `disconnected/connecting/connected/authorization_required/unavailable`，`message`、`active_task`、实际能力/范围。不得将“依赖已安装”写成已连接。
- `POST /connect`：仅连接已经运行的普通Chrome，后台异步尝试，202返回connecting；通过Chrome144+发现端点并等待用户允许。端点仅本机固定浏览器发现，不接受客户端任意URL。连接失败不launch、不重试登录。
- `POST /disconnect`：取消自身任务，只断开传输。绝不调用borrowed browser/context的close，不关闭用户页面。
- `GET /tabs`：仅列HTTPS国内小红书笔记/搜索/首页标签的临时ID、标题与URL，不返回其他页面内容或账号字段。
- `POST /tasks`：body=`{tab_id, mode:'current'|'search'|'detail', query:'', url:'', max_posts:1, max_comments:0..3}`。首版固定最多1篇。current读取所选笔记；search从所选小红书标签执行一次关键词搜索并打开实际结果；detail在该标签访问已校验的单个小红书笔记链接。一个活动任务，实际总时限120秒，可取消。
- `GET /tasks/{id}`，`POST /tasks/{id}/stop`，`GET /tasks/{id}/results`：状态/取消/结果。结果仅terminal completed可读；失败和取消不能混成完成。成功结果=`{items:[IngestRequest-compatible原文材料],summary:{...真实计数/覆盖...}}`，无自动入库和模型调用。

前后端Executor可以在消息中共同收窄必要字段，但不得各写一套不兼容协议。

## 采集要求

1. Playwright或等效标准CDP客户端只连接现有会话。选中的既有标签和context都为borrowed；退出只detach/stop传输。不要使用上游client、Cookie API、storage、隐藏JS状态、平台请求签名/接口重放或通用脚本执行API。
2. 只允许所选标签在 `xiaohongshu.com/www.xiaohongshu.com` 的HTTPS页面工作。任何跳转国际站、验证/登录遮罩、浏览器错误页、标签关闭或内容缺失都给确定状态；原因不明就说明未知，不再次让用户登录。检查任务开始、导航后及读取前的URL。
3. 固定DOM选择器读取已加载标题、描述正文、最多3条评论；不能用页面通用innerText混入AI摘要/推荐流，不能拿标题补正文。记录选择器版本、真实采集时间、对象ID、原始URL、可见源时间、范围及不完整原因。
4. 正文不能沿用CUA的512字符截断。DOM本身存在折叠/未加载或长度上限时明确标为片段，说明边界。评论独立ID/父子层级/绝对时间没有直接证据时保持unknown/null；不得用本地序号冒充。
5. 输出capture_method符合现有契约，capture_version明确 `mining-existing-chrome-dom/v1`、raw_payload标采集方式，不冒充MediaCrawler上游输出。不得把执行器测试fixture作为真实材料。

## 前端要求

在现有数据源页面添加清楚的“使用已登录 Chrome”入口：连接状态、连接/断开、目标标签选择、关键词/单链接/当前笔记、范围、开始/停止/刷新、原文预览、选择导入、来源快照回读和用本批材料发现机会。复用既有批量导入与机会页交接，不创建第二套数据资产。

初始状态不能自动连接/采集；成功连接后才允许启动。连接说明解释一次性Chrome授权，不把程序缺口说成用户登录错误。保留旧独立采集器，避免两者状态混淆。

## 验收

- 新增有意义的连接生命周期、域名/路径校验、正文与评论解析、超时/取消/标签关闭、错误传播、批次边界测试。mock只能证明离线逻辑；至少增加一条真实本地DOM fixture浏览器解析检查。
- borrowed保护测试必须断言browser/context.close及launch、cookies、storage均不调用；来源含不可信脚本/伪ID/跨域链接时保持边界。
- 静态Ruff、编译与JS语法按受影响文件运行，实际记录每条退出码；原36测试SHA不得变。完成受影响回归；本仓库Golden Rules要求全量pytest，若运行受既有问题阻挡，逐项如实报告，不能冒称通过。
- 交付报告列改动、API、依赖、离线结果、待用户授权的真实步骤及所有限制。冻结本轮文件等待Commander独立验收；Commander随后继续真实任务、导入去重、快照和机会判断，不在离线通过处结束整个工作。
