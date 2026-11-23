# D3-M1 交付报告

日期：2026-11-06。Executor实现已完成，等待Commander独立签收。**真实本地运行器、三平台导出适配和网页交接完成；尚未启动任何真实平台采集/登录，三个平台LIVE均待验证。** 用户确认的普通Chrome小红书登录不等于专用profile已登录。

## Installed：实际完成

- 上游真实checkout：`tools/mediacrawler-runtime/upstream/`，HEAD固定 `54a3d92412f4b20c06b45f1d542b78dd92049d6d`；上游源码、配置、LICENSE原样保留，git status干净。
- 独立`.venv`：Python3.12.13，Node v24.16.0；上游锁的89个依赖经hash校验安装。没有往MINING虚拟环境注入MediaCrawler依赖。
- Playwright1.61.0实际下载Chromium1228 / Chrome149.0.7827.55、对应headless shell及FFmpeg到独立browsers目录，安装命令退出0；未启动浏览器。
- 原LICENSE为NON-COMMERCIAL LEARNING LICENSE1.1，版权标记relakkes@gmail.com。LICENSE与锁SHA见`outputs/D3-M1/installed-runtime-20261106.json`和第三方说明，不混入MINING MIT许可。

实际安装/校验命令及结果（均在项目目录执行）：

| 命令 | 结果 |
| --- | --- |
| `git clone --no-checkout --filter=blob:none https://github.com/NanmiCoder/MediaCrawler.git tools/mediacrawler-runtime/upstream`；`git ... checkout --detach <pin>` | 各exit0 |
| `UV_PROJECT_ENVIRONMENT=<runtime>/.venv uv sync --frozen --project <runtime>/upstream --python 3.12` | 首次exit1，TUNA镜像下载pydantic发生TLS EOF；保留准确失败，未改原锁 |
| `uv export --frozen --format requirements-txt --no-emit-project --project <runtime>/upstream --output-file <runtime>/requirements.lock.txt` | exit0，保留冻结版本及hash |
| `uv pip install --python <runtime>/.venv/bin/python --index-url https://pypi.org/simple --require-hashes -r <runtime>/requirements.lock.txt` | exit0，89包；官方PyPI下载同hash依赖 |
| `PLAYWRIGHT_BROWSERS_PATH=<runtime>/browsers <runtime>/.venv/bin/python -m playwright install chromium` | exit0，实际浏览器下载完成 |
| `<runtime>/.venv/bin/python scripts/run_mediacrawler_task.py --runtime <runtime> --upstream-help` | exit0，真实上游CLI帮助；没有创建crawler |
| `.venv/bin/python scripts/install_mediacrawler_runtime.py --verify-only` | exit0；installed=true, browser_present=true, help_exit0, live=false |

真实help另存`outputs/D3-M1/upstream-help-20261106.txt`。安装脚本可重复执行，缺依赖/错误pin/脏上游/缺browser/marker/Node都不会ready；空setting只自动探测本项目受管目录，显式服务器目录仍可覆盖，不改`.env`。

## Offline / API：执行结果

执行命令：

```sh
.venv/bin/pytest -o addopts='' -q tests/test_mediacrawler_D3.py tests/test_mediacrawler_frontend.py tests/test_community_preview_frontend.py tests/test_d1_source_frontend.py tests/test_source_evidence_D1.py tests/test_auth.py tests/test_source_acquisition_contract.py tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_zhihu_search_preparation.py
```

**294 passed，1个既有Starlette/httpx弃用warning，exit0，最终一轮3.30s。** 新增Python核心43项及前端wrapper1项包含在内。旧测试未删除、未修改或减弱。

覆盖实际pin的三平台规范化字段、秒/毫秒/未知时间、匿名作者、父页评论、空简介仍保留评论、缺正文/父对象/坏链接/凭据字段排除；不同父页评论身份保留；XHS精确末段ID、签名变化同ID复用、不同路径分别入库、原URL/原raw记录快照完整性。对同父ID多正文版本保留首条有效正文，不能绕过篇数/预览上限。

运行器用真正的本地OFFLINE子进程验证启动、argv而非shell、独立目录、exit0有材料/exit0无材料/非0退出、并发拒绝、取消、超时、启动失败、日志丢弃、无关密钥环境白名单；JSON/JSONL读取验证单文件2MB、总8MB、200行、旧输出、符号链接/错误路径和NaN/Infinity拒绝。三平台搜索参与后续处理的列表在调度正文/评论前限量，保留页返回数与选择数区别。

API沿既有API Key鉴权保护5类新端点，无鉴权均401；状态/结果读取不写反馈或资产、不调用模型。测试使用独立临时SQLite，未接触业务数据库。fixture明确OFFLINE，不能当平台LIVE样本。

## UI：实现与离线行为通过

```sh
node --check frontend/static/app.js
node --test tests/mediacrawler_frontend.test.cjs tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs
```

各exit0，**Node26/26通过**（新增4项）。覆盖初次只读环境检查、缺环境诚实禁用、显式启动、停止/失败不开放部分结果、手动刷新、正文安全文本渲染、过期路由响应隔离、选择导入、完整字段保留、实际唯一ID回读、失败只重试回读、D1快照入口与机会页交接。网页不轮询、不自动启动浏览器或模型；离开页不自动停任务。旧HN/V2EX/知乎入口保留，资源query已更新以免旧缓存。

Commander已准备隔离服务和独立浏览器验收；Executor没有将离线DOM测试冒充真实浏览器或账号实采。

定向Ruff覆盖本轮Python文件，**All checks passed**；compileall与JS语法exit0。

## 接口与材料契约

- GET `/api/v1/mediacrawler/status`：真实本机预检，ready/live_verified分开。
- POST `/api/v1/mediacrawler/tasks`：`platform=xhs|bili|wb`，`mode=search|detail`；search一个query，detail单个对应平台HTTPS正文url；`max_posts=1..3`（detail强制1），`max_comments=0..8`。额外字段、Cookie、任意平台、多关键词/多链接和不合法参数拒绝。
- GET `/tasks/{id}`，POST `/tasks/{id}/stop`，GET `/tasks/{id}/results`均在同一mediacrawler前缀内。一个活动任务，600秒总时限，stdout/stderr不回传，专用可见profile、CDP关闭。
- running/waiting_for_login/collecting → completed/empty/failed/cancelled/timed_out；取消/超时/失败不开放部分输出。停止先发自身进程组信号，桥接取消后清理专用上下文，最多7秒等待后清理自身组；不查杀用户Chrome。
- results `{task,items,summary}`，items直接符合既有`/feedback/batch`。`capture_method=crawler`，真实平台source_type/platform；XHS策略仅加crawler，仍校验原域名。原作者null，评论无专属URL用parent_page；source_captured_at只取采集端时间，缺失留空。
- raw_payload是上游规范化导出整行+任务/pin/范围元数据，不是原平台HTTP响应。B站简介最多500字符、不是口播；微博长文不保证完整。D1真实性仍未认证，hash仅本地完整性。
- 显式导入后按实际唯一feedback_ids回读已存记录，再建立机会选择；不声称新增数量、不覆盖重复旧快照。XHS幂等仅对真实正文域名/路径忽略访问签名，存档URL不动，HN id/其他query保留。

## 精确交付文件

新增：

- `signal_miner/connectors/mediacrawler_adapter.py`
- `signal_miner/connectors/mediacrawler_runner.py`
- `signal_miner/routes/mediacrawler.py`
- `scripts/run_mediacrawler_task.py`
- `scripts/install_mediacrawler_runtime.py`
- `tests/test_mediacrawler_D3.py`
- `tests/mediacrawler_frontend.test.cjs`
- `tests/test_mediacrawler_frontend.py`
- `docs/mediacrawler-local-runtime.md`
- `docs/third-party-mediacrawler.md`
- 本报告
- `outputs/D3-M1/installed-runtime-20261106.json`
- `outputs/D3-M1/upstream-help-20261106.txt`
- `outputs/D3-M1/upstream-cli-parse-20261106.json`（真实CLI只解析受控参数，不创建crawler）

局部修改：`.gitignore`、`README.md`、`signal_miner/main.py`（router/生命周期）、`signal_miner/settings.py`（服务器目录）、`signal_miner/utils/source_platforms.py`（XHS加crawler）、`signal_miner/utils/source_evidence.py`（仅XHS正文访问签名的身份规范化）、`frontend/static/app.js`、`frontend/static/index.html`。未修改CSS、历史测试、旧mock client/runner、D1哈希真实性/正文算法、MASTER/P13、数据库结构、业务库、密钥。未提交Git或创建PR。

独立安装目录已忽略，包含依赖/browser/profile/tasks，未作为应用源码提交。

## LIVE：待Commander协调用户

Executor启动目标平台任务数量 **0**。小红书/B站/微博均无实采通过声明。根侧接下来可重启18816隔离服务加载最终代码，在网页以1篇/3评论显式启动；用户在专用窗口人工登录，刷新状态，预览核对，选材料导入并回读D1快照。真实平台的可达性、账号权限、验证码与内容完整性只能以该轮证据为准。

首版运行一个本机单worker服务，任务回执在内存、输出仅本地。平台原始日志不开放，故失败用安全状态码、人工窗口与链接排查；没有验证码绕过、账号池、代理轮换或多平台调度框架。

## 启动诊断定向返修（2026-11-06）

Commander首次真实UI任务 `cfd227a0257647a3a0aac979ef36516f` 约15秒exit1，无材料，也没有可核实的登录窗口。LIVE结论仍为未通过；不能从安装或离线通过推断平台可用。见`docs/acceptance-D3-M1-startup-fix-20261106.md`。

本次仅修改 `scripts/run_mediacrawler_task.py`、`signal_miner/connectors/mediacrawler_runner.py`、`tests/test_mediacrawler_D3.py`、操作说明及本报告。未恢复原始日志，未改TLS、TMPDIR、环境白名单、上游代码或其他应用模块。Executor没有自行重试平台。

桥接在失败时写私有、最多4096字节的diagnostic.json，保留第一异常的安全类名、有限阶段、固定类别及最多5个仓库相对栈帧。没有异常文本/代码/局部变量/绝对路径。阶段区分导入、配置、启动crawler、launching_browser、navigating_platform、等待登录、采集、清理。取消与零退出不当作失败诊断；清理错误不覆盖第一位置。明确识别的证书/连接/超时/socket文本只转换成枚举，不直接回传；外层连接异常包含证书异常时优先标证书类别。

运行器只有failed终态可附严格校验后的diagnostic，拒绝未知字段、消息字段、超长文件、符号链接、绝对路径/路径穿越、非法类名/函数名/行号、超过5帧及未知枚举；损坏时仍用通用失败。stdout/stderr保持DEVNULL。API不开放原始运行目录。

同上回归命令结果更新为 **315 passed，1个既有warning，exit0，3.60s**；新增21项敏感文本/栈帧/分类/异常读取行为验证，含Cookie、URL访问参数、模型/知乎密钥样例及真正本地非0子进程的诊断回执。最终核心定向测试64项另复跑；Ruff与编译检查exit0。最终`--verify-only`仍exit0，安装ready=true、LIVE=false；没有启动平台。

下一步由Commander从UI执行一次相同范围的诊断任务。TMPDIR路径长度目前只是假设；Python AF_UNIX限制与macOS Chromium实现可能不同，未凭猜测修改。若诊断确认socket路径根因，最小候选是仅将任务临时IPC目录移到短系统临时根下的独立700目录，profile/tasks/源输出保持原位，再独立验收；本轮未实施。

## 首次官网导航定向修复（2026-11-06，待实网验证）

Commander第二次实际任务 `e41c861fef7440d59e3491e11a0a4225` 安全诊断确认：浏览器启动已完成，约33秒在 `xhs/core.py:104` 的官网首页Page.goto失败，TimeoutError / navigating_platform / timeout，未进入登录、无材料。证据为`outputs/D3-M1/commander/second-live-attempt.json`。这未证明是动态页面load等待还是本机网络问题；TMPDIR/socket假设未获支持，没有按假设改动。

按`docs/executor-instruction-D3-M1-navigation-fix-20261106.md`只修改bridge、新D3测试与本文/操作文档。桥接仅在本任务XHS专用context的首个新页面上，对第一次导航到精确 `https://www.xiaohongshu.com` 或末尾斜杠首页、默认wait_until条件，采用domcontentloaded并保持30秒上限（原有更短正超时保留）。不是全局Page补丁；第一次调用即消耗作用范围，其他URL或显式等待条件不会让之后导航再次被修改。其他页面/平台不处理，无自动重试，不改TLS、代理、验证码、TMPDIR或主Chrome。

新增22项确定性OFFLINE导航测试：精确首页、非目标链接/查询/片段/近似域名、第一次/后续/其他页面、其他平台、显式等待条件、短/零/过大超时、原其余参数保留、失败不重试且仍可有限诊断。核心 **86 passed，exit0，1.67s**；同上完整受影响回归 **337 passed，1个既有warning，exit0**。Node三组仍 **26/26**，JS语法、定向Ruff、bridge编译均exit0。

Executor本轮仍未自行实网重试；修复效果待Commander通过UI按相同1篇/3评论验证一次。若DOMContentLoaded仍超时，停止盲试，保留安全诊断并判断本机网络。LIVE不预写为通过。

## 小红书专用窗口人工发起登录修复（2026-11-06，待实网验证）

Commander第三次实际任务 `f154ee966507427e83f84048437fef1f` 验证了首页DOMContentLoaded导航修复生效（顺利越过 `navigating_platform` 进入 `waiting_for_login`），但约77秒后在固定上游 `upstream/media_platform/xhs/login.py:182` 的硬编码绝对XPath点击登录按钮处超时退出（exit 1）。

按 `docs/executor-instruction-D3-M1-manual-login-fix-20261106.md` 完成单一修复：
- 仅针对 `xhs`，在 `scripts/run_mediacrawler_task.py` 的 `configure_login_entry` 中覆盖 `login_by_qrcode`：先校验 `self.context_page` 确为允许的HTTPS小红书官方域名（`www.xiaohongshu.com` / `xiaohongshu.com`，拒绝 `chrome-error://`、非HTTPS、外域或带凭据URL，且仅返回布尔值、不导出URL），在子进程本地提取当前 `web_session` 作为未登录基线后写入 `waiting_for_login` 阶段，直接调用上游 `self.check_login_state(no_logged_in_session=baseline)` 等待用户在专用窗口中手动点击登录并完成扫码/验证。
- 仅当 `check_login_state` 返回 `True` 且页面仍为小红书官方HTTPS页时才进入 `collecting`；`False`、`None`、异常或跳离官方域名均抛错终止，绝不伪造成功。B站（`bili`）与微博（`wb`）仍调用原 `login_by_qrcode` 入口，上游checkout保持干净未改。
- `signal_miner/connectors/mediacrawler_runner.py` 在 `xhs` 处于 `waiting_for_login` 时返回明确提示：`“请在专用页面手动点击登录，程序正在等待登录确认；二维码是否出现以窗口实际内容为准。普通Chrome登录不会自动共享。”`
- 新增22项离线门禁测试（`tests/test_mediacrawler_D3.py`），核心测试 **108 passed**，完整回归 **359 passed，1个既有warning，exit0**，Node **26/26**，Ruff与编译检查全部通过。
