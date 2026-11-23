# D3-M1 国内页面访问等待交付

日期：2026-11-09。按`docs/executor-instruction-D3-M1-domestic-page-wait-20261109.md`实施。**仅支持国内小红书任务，不启用国际站采集；本轮无实网请求，LIVE未完成。**

## 已知事实与本轮处理

Commander独立377项/Node26项与Ruff通过后，真实任务836d224423a64734b843db266df99e89明确诊断为HostNotAllowed。Commander另观察到专用新页面访问国内首页/Explore会跳到Rednote，普通Chrome现有会话表现不同。不能据此断言是哪项账号、代理或网络设置导致，也不据此修改主Chrome或全局网络。

本轮只把**已知的精确国际页跳转识别为国内访问尚未恢复**：保留可见专用窗口，等待用户在同一个标签页处理国内访问。没有国际API、登录入口、内容适配或域名泛化。

## 为什么暂停放在client创建前

实读固定pin `xhs/core.py`：104行首页导航后，106行调用`create_xhs_client`；该方法384行起会读取专用context Cookie，107行还会执行pong，之后才进入人工登录入口。若只在login入口暂停，无法如实声称“尚未读取登录态或发送client请求”。

经Commander确认，桥接仅对本任务XHS**首次create_xhs_client调用前**加本地等待门槛。国内页校验通过后才调用原方法；原client实现、pong、上游文件均不改。既有login入口继续二次严格校验，不开启第二轮等待。该时序由离线fake client/cookie/pong事件顺序断言覆盖。

## 状态与安全边界

- 首次页只有在HTTPS、主机精确`rednote.com`/`www.rednote.com`、默认或443端口、无URL凭据时可进入`waiting_for_domestic_page`。这只是暂停识别，**这些主机仍不通过国内来源校验**。
- 每2秒只读取同一受控Page的本地URL和关闭状态。等待代码不读Cookie、页面正文或截图，不调用locator/click，不自动goto/reload，不创建client、不发内容请求。浏览器已打开页面自身的加载与用户手动访问不被冒称为程序无网络环境。
- 用户使同一标签页回到原国内官方HTTPS白名单后才恢复原client，随后进入已有人工登录等待和确认。原Cookie基线只在子进程本地使用，未新增凭据导出。
- 其他外域、伪后缀/子域、非HTTPS、URL凭据、错误端口、错误页及关闭页面均失败；关闭页只新增固定安全异常`XHSPageClosedError`，无URL或页面内容。已恢复后或已确认登录后再跳离国内页仍失败，不反复暂停。
- 原600秒总时限、stop/cancel及专用上下文清理继续生效；取消/超时无部分结果，不能标成功。B站/微博逻辑不变。
- runner仅增加同名有限阶段、运行中状态映射与安全提示。既有UI用`task.message`/`terminal`即可显示暂停和启用停止，无新前端流程。

页面提示明确当前跳到国际站、请恢复同一专用标签页的国内访问、尚未读取登录态/采集、不要在国际页登录。没有国际站登录建议；没有代理/TLS/主Chrome权限改动。国内采集/来源适配/D1身份规则和业务数据库不变，原始日志仍不回传。

## 测试与实际退出码

```sh
.venv/bin/pytest -o addopts='' -q tests/test_mediacrawler_D3.py
```

exit0：**151 passed，2.16s**。新增25项（含现有登录后跳转用例补充）覆盖：精确暂停→国内页→手动登录→collecting；暂停前client/cookie/pong均未触发；低频同Page观察；不允许的链接不暂停；暂停中外域/错误页/关闭页失败；取消传播；恢复后不再次暂停；登录后再跳到Rednote仍拒绝；其他平台不修改；真正本地OFFLINE子进程暂停阶段可stop/timeout且不开放部分结果。

```sh
.venv/bin/pytest -o addopts='' -q tests/test_mediacrawler_D3.py tests/test_mediacrawler_frontend.py tests/test_community_preview_frontend.py tests/test_d1_source_frontend.py tests/test_source_evidence_D1.py tests/test_auth.py tests/test_source_acquisition_contract.py tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_zhihu_search_preparation.py
```

exit0：**402 passed**（原377项加25），1个既有Starlette/httpx弃用warning。

```sh
node --test tests/mediacrawler_frontend.test.cjs tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs
node --check frontend/static/app.js
.venv/bin/ruff check scripts/run_mediacrawler_task.py signal_miner/connectors/mediacrawler_runner.py tests/test_mediacrawler_D3.py
.venv/bin/python -m compileall -q scripts/run_mediacrawler_task.py signal_miner/connectors/mediacrawler_runner.py
```

各exit0：**Node26/26**、JS语法通过、Ruff **All checks passed**、编译通过。按既有SHA基线重算，**36/36历史测试文件一致，changed=[]**。没有删除或弱化历史门禁。

## 精确交付文件

- `scripts/run_mediacrawler_task.py`
- `signal_miner/connectors/mediacrawler_runner.py`
- `tests/test_mediacrawler_D3.py`
- `docs/mediacrawler-local-runtime.md`
- 本报告 `docs/delivery-D3-M1-domestic-page-wait-20261109.md`

未修改前端、上游checkout、国际配置/API、原策略/适配/D1身份、数据库、`.env`、密钥、主Chrome或全局网络。未新增子代理、未实网重试、未重装依赖、未提交Git。

交付后由Commander独立验收并通过UI协调一次国内页面恢复。暂停功能是外部访问问题的本地任务控制，不能作为已登录、已采集或LIVE成功的证明；如果国内页仍无法停留，继续如实说明访问阻断，不盲目请求内容。
