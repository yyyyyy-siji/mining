# MediaCrawler 接入的一手契约核对

日期：2026-11-06。用户已明确非商业用途。本文是Commander只读代码核对记录，不是平台实网采集报告。

固定上游：`54a3d92412f4b20c06b45f1d542b78dd92049d6d`，来源为Git远程main ref。保留[上游许可证](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/LICENSE)，不将其视为MINING的MIT授权。

## 导出结构

| 平台 | 正文与来源 | 评论与父级 | 时间语义 |
| --- | --- | --- | --- |
| 小红书 | note_id、desc、note_url；URL可含必要xsec访问参数 | comment_id、content、note_id、parent_comment_id | time/last_update_time为源时间；create_time为评论时间；last_modify_ts为采集端记录时间 |
| B站 | video_id为aid；video_url通常为av链接；desc在上游截至500字符，不能当作完整视频内容 | comment_id为rpid、content、video_id、parent_comment_id；0表示无父评论 | create_time为源Unix秒；last_modify_ts为采集端记录时间 |
| 微博 | note_id、去HTML后的content、m.weibo.cn/detail链接 | comment_id、content、note_id、parent_comment_id（rootid） | create_time为源Unix秒；create_date_time是带格式的派生时间，不能自行假定无时区文本的时区 |

一手源码：[小红书store](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/store/xhs/__init__.py)、[B站store](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/store/bilibili/__init__.py)、[微博store](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/store/weibo/__init__.py)。适配时仍需按各字段确认秒/毫秒，不将本表当作运行时推断全部数值单位的依据。

三个store中的nickname已经脱敏，creator_hash不是原始用户ID；不能据此声称保留了原始作者身份，也不能直接统计独立真人数量。视频简介和帖子正文分开；B站500字符边界应保留覆盖范围说明。

`tools/time_util.py:get_current_timestamp()`返回13位毫秒。store的last_modify_ts是采集程序生成的记录时间，不是用户修改原帖的时间。[时间工具](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/tools/time_util.py)

MINING应保存整条上游规范化导出记录及pin/任务/输入/范围，不能将其命名为“原始平台HTTP响应”。未知作者、时间、评论直达链接保持未知；评论借助已取得的父帖链接时明确父页面定位。

## 小批量与任务输出

上游搜索会把过小的篇数提升至页大小（小红书/B站20、微博10）；限制预览展示数量不能限制后续详情和评论请求。桥接需在搜索结果进入后续处理前限制参与对象，并区分搜索页返回量和真正处理篇数。

微博一级评论在callback前按max_count裁剪；其子评论仅对返回附带内容处理。M1关闭子评论，不承诺全楼中楼。微博full_text选项会额外取详情；即使启用也只能表述为上游取得的正文，不能凭开关宣称完整性已获实网验证。

JSONL文件默认按平台、任务类型和日期追加，直接读取共享data目录容易混入历史任务。每次任务必须设置独立save_data_path。[文件写入](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/tools/async_file_writer.py)、[微博core](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/media_platform/weibo/core.py)

## 本机登录与调用边界

上游支持CDP复用和独立浏览器。M1可使用独立可见持久浏览器；普通Chrome或App已登录不等于该profile已登录。不自动开启主浏览器调试权限，不把登录态文件、Cookie或上游原始日志送到网页/API/导出。

上游API的启动器会记录命令；Cookie模式可能将Cookie放进命令参数，不宜原样桥接。M1选择受控本地进程、二维码/持久登录态、不提供Cookie输入框、限制环境变量并屏蔽跨目录dotenv加载。[启动器](https://github.com/NanmiCoder/MediaCrawler/blob/54a3d92412f4b20c06b45f1d542b78dd92049d6d/api/services/crawler_manager.py)
