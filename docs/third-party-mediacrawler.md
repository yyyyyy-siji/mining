# MediaCrawler 第三方说明

本项目通过独立本机进程调用 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)，固定提交 `54a3d92412f4b20c06b45f1d542b78dd92049d6d`（2026-11-06核实）。原仓库、版权头与LICENSE在 `tools/mediacrawler-runtime/upstream/` 原样保留；不自动pull、不修改上游主源码。

上游为 **NON-COMMERCIAL LEARNING LICENSE 1.1**，版权所有者标记 `relakkes@gmail.com`。它与MINING自身的MIT标记独立，不能把该组件重新标成MIT。本接入仅用于用户已明确的非商业学习研究，使用时仍需遵守原LICENSE与平台条件。完整文本见固定版本的 [LICENSE](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/LICENSE)。

实际安装LICENSE SHA-256：`aeff21de8609bec9d6e939bbbba7c2914ae0a6e7c9470ea7945c03f7d17a2a33`。

独立环境使用上游冻结 `uv.lock` 的版本和hash导出安装依赖；原锁SHA-256：`16034a88f3981a63f9667b202e348372b4f1571cbd5aeb03530c7027622d22d6`。首次TUNA镜像TLS失败后改从官方PyPI下载同hash包，未改原锁。Chromium由Playwright下载到独立browser目录。

MINING新增的桥接只限制任务配置、参与后续处理的搜索列表和安全状态回传，三平台适配读取该固定版本的规范化导出结构。导出不是原平台HTTP原始响应，匿名化作者、简介截断和内容覆盖限制在预览、快照与操作说明中保留。
