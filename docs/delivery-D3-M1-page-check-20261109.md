# D3-M1 页面校验有限诊断交付

日期：2026-11-09。Executor按`docs/executor-instruction-D3-M1-page-check-20261109.md`完成，等待Commander独立验收。**本轮没有实网重试，LIVE仍未通过。**

## 依据与本轮结论

已完整阅读当前bridge/runner/新D3测试、人工登录续作报告和 `outputs/D3-M1/commander-20261109/live-attempt.json`。真实任务 `cfa66c28293144208cd9b1ad241266c0` 约7秒exit1，无材料；已有诊断只能确认人工登录入口首次官方页面校验未通过（RuntimeError / navigating_platform），不能确定页面实际是哪类，也不能据此判断账号未登录或已经跳到外域。

本轮只让未来校验失败可区分固定原因，不改变主机白名单、不跳过检查、不创建新的平台请求。普通Chrome已登录的用户信息保持有效，不索取Cookie或扩大Chrome调试权限。

## 变更与接口

修改 `scripts/run_mediacrawler_task.py`：增加返回固定枚举的 `_official_xhs_page_reason` 和固定异常类型，保留 `_official_xhs_page` 的布尔契约；人工等待前、确认成功后都用 `_require_official_xhs_page` 执行同一严格检查。失败仍在读取会话/进入人工等待前中止；确认返回非True仍按原逻辑失败。B站/微博不经过该检查，仍调用原登录入口。

复用现有有限诊断的 `exception_type`，`category`仍为`runtime_error`；不增加任意字符串字段，不需要修改runner的严格schema或API。

| 固定内部原因 | diagnostic.exception_type | 含义 |
| --- | --- | --- |
| about_blank | XHSPageAboutBlankError | 当前页为about:blank |
| browser_error_page | XHSPageBrowserError | 当前页为浏览器错误页 |
| non_https | XHSPageNonHTTPSError | URL使用非HTTPS方案 |
| host_not_allowed | XHSPageHostNotAllowedError | 主机不在原有固定白名单 |
| port_or_credentials_not_allowed | XHSPagePortOrCredentialsError | 端口不是默认/443，或含URL用户信息 |
| invalid_url | XHSPageInvalidURLError | URL缺失、无效，或URL属性不可用 |

允许主机仍严格只有`www.xiaohongshu.com`、`xiaohongshu.com`，端口仍仅默认/443。不接受主机后缀匹配或新增域名。对URL解析会静默剔除的首尾空白/控制字符明确判无效；显式空用户信息也按凭据字段拒绝。这两点是严格校验的确定性收紧，**没有证据表明它们是cfa66任务的真实原因**。

异常实例不携带消息或URL参数（`args == ()`）；已有最多4096字节、最多5个仓库相对栈帧的诊断边界不变。不会输出实际主机、完整URL、query、页面正文、Cookie、模型/知乎密钥、截图或原始日志。stdout/stderr仍DEVNULL，TLS/代理/TMPDIR/上游checkout/主Chrome不变。

## 验证与实际命令

新增18项OFFLINE测试。原新D3页面拒绝测试按固定异常类型加强断言，保留不调用原入口、不读会话、不进入等待、不泄露来源的断言；36个历史测试文件未修改。新增样例覆盖六类原因、敏感query/主机/路径/凭据、非数字端口、错误URL类型、空用户信息、控制字符、URL属性异常，以及通过既有runner有限读取与终态回执证明不泄露敏感原文。官方HTTPS成功路径、False/异常不成功、取消传播、B站微博原逻辑保留。

```sh
.venv/bin/pytest -o addopts='' -q tests/test_mediacrawler_D3.py
```

exit0：**126 passed，1.84s**。

```sh
.venv/bin/pytest -o addopts='' -q tests/test_mediacrawler_D3.py tests/test_mediacrawler_frontend.py tests/test_community_preview_frontend.py tests/test_d1_source_frontend.py tests/test_source_evidence_D1.py tests/test_auth.py tests/test_source_acquisition_contract.py tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_zhihu_search_preparation.py
```

exit0：**377 passed**（原359项加新增18项），1个既有Starlette/httpx弃用warning。

```sh
node --test tests/mediacrawler_frontend.test.cjs tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs
node --check frontend/static/app.js
.venv/bin/ruff check scripts/run_mediacrawler_task.py tests/test_mediacrawler_D3.py
.venv/bin/python -m compileall -q scripts/run_mediacrawler_task.py
```

各exit0：**Node26/26**；JS语法通过；Ruff **All checks passed**；编译通过。按 `outputs/D3-M1/existing-tests-sha256-20261106.json` 逐个重算SHA-256，**36/36历史测试文件一致，changed=[]**。

## 精确交付文件与剩余边界

只修改/新增以下3个文件：

- `scripts/run_mediacrawler_task.py`
- `tests/test_mediacrawler_D3.py`
- 本报告 `docs/delivery-D3-M1-page-check-20261109.md`

没有修改runner、API、前端、上游、D1/O2核心、历史测试、数据库、密钥或运行时设置；未重装依赖，未提交Git。没有读取/保存页面内容或登录凭据，没有自行启动目标平台请求。

交付后由Commander独立验收，再决定是否启动一次真实任务取得固定原因。已有cfa66诊断不包含原URL，不能回填新的原因结论；不预写LIVE通过，也不把有限诊断版当作已完成平台实采。
