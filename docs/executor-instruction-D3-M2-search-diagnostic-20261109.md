# D3-M2 执行指令：定位真实搜索请求失败

日期：2026-11-09。

## 任务目标

为已经失败的国内小红书搜索请求补充有限、安全、可操作的诊断，使下一次真实运行能够区分网络、平台验证、登录失效、数据响应和程序错误。不是绕过登录或平台限制。用户继续手动登录、处理验证。

## 背景 / 当前问题

真实任务 `7d5d2cb4888b41538c0eeaa514ca9667` 于 14:12:05 启动。14:17:19 的 API 仍为 waiting_for_domestic_page；14:18:41 以 exit1 结束。诊断为 RetryError、phase=collecting，frames 最终为 XHS search → limited_page → get_note_by_keyword → post。任务目录没有 data 文件。用户 14:19 报告找不到专用窗口；该窗口已经随失败清理，不能再要求其操作原任务或重复登录。

固定 bridge 只有人工登录确认为 True 且国内页面校验通过后才将 XHS phase 置 collecting。可以说检查曾通过，不能据此推断用户具体在哪个窗口做了什么。

现有 diagnostic 只保留最外层异常类和最外层 traceback，RetryError 遮蔽真正请求异常。_error_category 虽读取 cause/context，但只分网络/证书，平台请求错误仍是 runtime_error。不得通过开启原始 stdout/stderr、保存异常文本、响应正文、headers、URL 或 Cookie来诊断。

## 允许修改范围

- `scripts/run_mediacrawler_task.py`
- `signal_miner/connectors/mediacrawler_runner.py`（严格 schema、有限状态消息）
- `tests/test_mediacrawler_D3.py`
- 如需说明，`docs/mediacrawler-local-runtime.md`
- `docs/delivery-D3-M2-search-diagnostic-20261109.md`

## 禁止修改范围

前端业务流程、来源适配/D1、业务数据库、.env、主 Chrome、全局网络/代理/TLS、上游 checkout、登录确认规则、国内白名单、任何国际站适配。不得自行发实网请求、启动采集或新增代理。

## 实现要求

1. 保留最外层异常类型；从至多8层 cause/context，以及已安装 Tenacity RetryError 的 last_attempt.exception() 安全读取真正异常。避免环、不调用任意不相关属性，不序列化 exception/future。本地读取过程也必须有界。
2. 可以增加一个严格验证、长度有界的根因异常类型与至多5个受控仓库相对根因 frames；兼容已有诊断或明确版本策略。所有新增字段均需 runner 严格 schema 校验，仍保持4096字节、有限枚举、首次失败不被 cleanup 覆盖、不含原始 message/locals/URLs/账号信息。
3. 用固定安全类别区分已知上游异常类（如 PlatformAccessError、IPBlockError、DataFetchError）、JSON解析失败及已有连接/超时/证书错误。只在证据足够时归为平台验证或登录失效；未知保持未知，不靠泛化关键词臆断。需要读取静态上游定义核实映射，不能修改上游。不要新增HTTP请求拦截或重放、签名算法、代理轮换、重试次数调整。
4. 给已知固定类别提供相应有限提示；未知类型明确搜索/请求失败且原因未定，不笼统要求用户反复登录。失败仍为失败，结果409，无部分输出。
5. 若判断只增加根因类仍不足以区分下一步，先说明最小缺口和安全观测办法，不擅自保存平台原始响应。

## 验收标准

### 语法 / 静态检查

执行 Ruff、compileall；每条命令实际检查退出码。

### 功能验证

使用真实依赖的 RetryError/Future 包裹本地构造异常，验证根因类/frames 的实质价值；恶意异常文本内含 Cookie、URL、token、响应正文，所有导出均无这些值。覆盖环、缺失/失败 future、过深链、超长/伪造诊断、schema拒绝、4096限制和 cleanup 首错保留。

### 回归验证

执行原受影响402项+新增、Node26项，原36测试 SHA不变；国内等待/人工登录确认、取消/超时和无部分结果语义不回归。根因定位不能变成原始日志回传。

### 交付前质量门禁

交付报告按真实命令退出码和总数填写。明确当前真实任务已结束、无材料、没有执行本轮实网重试。下一次任务由Commander从UI启动，仅在需要人工登录/验证时协调用户；若平台拒绝，应停止并报告，不能绕过。

## 交付报告模板

列出修改文件、诊断字段/兼容策略、确定类别与不确定性、测试命令/退出码/结果、本次没有实际运行的步骤。交付后停止编辑，等待Commander独立复验。
