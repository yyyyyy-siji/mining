# D3-M1：国际站跳转时保留专用窗口供用户处理

日期：2026-11-09。

## 观察证据

Commander独立377项/26项与Ruff通过。真实任务836d224423a64734b843db266df99e89明确失败于XHSPageHostNotAllowedError。另通过CUA实际打开 `https://www.xiaohongshu.com/` 和 `/explore`，两者均跳到 `https://www.rednote.com/`；公开、无账号、trust_env=False的HTTP连通探针也最终到rednote（文件direct-redirect-chain.json）。用户确认普通Chrome可保持www.xiaohongshu.com国内站。新会话与既有Chrome会话表现不同，**不能据此断定必然是哪项代理/账号设置导致**。

固定上游本身有XHS_INTERNATIONAL及rednote端点，但用户选择国内使用，不开启国际站、不扩大采集域名，不把国际材料冒充国内样本。

## 单一改动

只针对XHS、首次人工登录入口，若当前页面**精确HTTPS rednote.com/www.rednote.com、无URL凭据且默认/443端口**，进入新有限状态 `waiting_for_domestic_page`，保持专用可见窗口打开。用低频本地Page.url观察等待用户在**同一个受控标签页**手动访问国内站；不自动导航/重试、不读取账号Cookie/页面正文、不发送请求、不修改网络/代理/TLS。等待受已有600秒总时限与stop/cancel约束。

状态文案应说清：当前跳到Rednote国际站，请先使当前专用标签页停留在国内小红书；此时尚未读取登录态或采集。不能叫用户在国际页登录。官方国内HTTPS校验通过后才进入既有人工登录等待；原URL其他拒绝类别继续失败关闭，非精确rednote不能进入暂停。若用户导航到外域/错误页/关闭页，则安全失败，不放宽白名单。已确认登录后的再次域名变化仍失败，不开启第二轮无限等待。

可以用固定安全异常/原因标记已知Rednote跳转，诊断不得含任意URL/主机/query/Cookie。UI复用现有task.message与terminal语义，不需要新增前端流程。上游、原策略/适配/D1身份、业务库、主Chrome/全局网络均不改。

## 范围与门禁

允许bridge、runner新有限阶段/文案、新D3测试、操作/交付文档。不要新增子代理或自行实网。

离线测试明确验证：精确国际页暂停→国内页→手动登录→collecting；暂停时不读Cookie、不调用原二维码XPath、不发网络请求；外域/伪后缀/非HTTPS/凭据/错误端口不暂停；停止取消传播且无部分结果；登录后域名变化仍失败；B站微博行为不变；前端已有运行中/停止/迟到结果逻辑不回归。跑完整受影响377项+新增、Node26项、Ruff/编译，交付实际结果。

这是让外部访问问题可由用户处理的任务控制，不是绕过国际站限制或宣称平台采集成功。Commander会从UI启动一次验证并协调必要的用户操作；仍不盲目请求内容。
