# D1 收尾修正：人工录入的采集方式默认值

日期：2026-11-06。范围仅 `frontend/static/app.js`、新 D1 前端行为测试及交付报告补充，不改接口、来源核心或旧测试。

Commander 浏览器复现：打开产品反馈的“导入反馈”，来源默认微博，数据获得方法却默认“合规公开页面爬取”。知乎线索跳转补原文也会继承 crawler。用户在该页手工提供正文，默认记录为程序爬取会使来源元数据失真。

请让该人工录入入口初次呈现时默认 `manual_browser`；知乎“补原文”也明确选择 `manual_browser`。后续用户主动选择的采集方式，在切换来源且仍受新来源支持时应保留；不支持时优先人工浏览，而不是把“方法数组第一项”当成实际采集方式。不禁用 crawler/official_api，也不改变其真实导入能力。

新增最小行为断言：普通页面初始 default=manual_browser、知乎线索补原文=manual_browser，显式选择其他合法方式不会被无故改写。保留旧 O2/D1 异步及字段测试。运行 D1/O2 Node、对应 pytest wrapper、node --check。不得为了通过而修改旧测试。

完成后更新原交付报告的修正说明与实际测试结果，发消息通知 Commander 重载最终 JS。无需新增功能或执行真实网络。

## 浏览器缓存收尾

Commander 已在新 origin `localhost:18815` 看到正确人工默认，但原 `127.0.0.1:18815` 普通重载仍使用旧 JS；HTTP 返回的 JS 与新磁盘哈希一致。额外允许仅修改 `frontend/static/index.html` 的 JS/CSS 版本 query，使用户重载时取得 D1 资源。旧 JS query 为 `20260710-multimodal-status`。不引入缓存框架、不改后端。
