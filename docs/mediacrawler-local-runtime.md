# 本机登录态采集

这是固定版本 MediaCrawler 的本地进程桥接，适用于用户已明确的非商业学习研究。上游许可证与版权保留在独立checkout内，见 [第三方说明](third-party-mediacrawler.md)。本轮完成真实运行环境、三个平台导出适配与网页交接；**还没有把三个平台的账号实采标记为通过**。

## 安装与校验

在 signal-miner 项目目录执行，须有 Git、uv、Node.js：

```sh
.venv/bin/python scripts/install_mediacrawler_runtime.py
.venv/bin/python scripts/install_mediacrawler_runtime.py --verify-only
```

安装目录为 `tools/mediacrawler-runtime/`，已被Git忽略，权限700。它包含原样上游checkout、独立Python3.12虚拟环境、冻结锁导出的hash依赖清单、独立Playwright Chromium、专用profiles及每任务输出。安装仅下载与校验，不打开平台或浏览器。上游锁的TUNA镜像首次安装TLS失败，因此安装脚本保留原锁的依赖版本与hash，经官方PyPI校验安装，不更改上游锁或MINING虚拟环境。

服务器设置 `MEDIACRAWLER_RUNTIME_DIR` 可指定同样布局的本地受管目录；为空时只检查本项目默认目录。无需改`.env`。运行时必须满足固定pin、干净checkout、独立解释器、Node、浏览器文件、实际help校验marker；失败时界面诚实显示未就绪。运行目录不得放在公开的 `frontend/static/` 中。

启动现有MINING服务时使用单worker及本机绑定，例如 `.venv/bin/python -m signal_miner.main --host 127.0.0.1 --port 8000 --no-reload`。本功能的活动任务锁为单服务进程内锁，首版不要同时启动多个服务实例对同一运行目录采集。

## 首次使用

1. 打开“数据源”→“本机登录态采集”。先选择小红书，关键词或一个正文链接；首轮建议1篇、每篇3条一级评论。
2. 点击“开始本次采集”才会打开专用可见浏览器。对于小红书，请在专用页面**手动点击登录**、扫码或完成验证（程序仅等待登录状态，不依赖上游硬编码登录按钮点击，二维码是否出现以专用窗口实际内容为准）；现有普通Chrome、App登录不会自动复制到专用profile。不接收/复制Cookie，不开启主Chrome调试，不自动处理验证码或账号条款。
3. 手动点击“刷新环境 / 任务”。登录等待与采集共享10分钟总时限；需要中止时点击“停止本任务”。离开页面不会自动停止；重新进入可恢复查看仍在运行的任务。服务重启后内存任务回执不保留，任务输出仍仅存本地私有目录。
4. 完成后核对正文、来源和覆盖范围，勾选材料，点击“导入所选材料”。预览不写反馈/资产，不调用模型；只有显式导入才走现有D1契约。
5. 导入后按实际唯一反馈ID回读旧/新材料，可查看或下载D1来源快照；点击“用本批材料发现机会”，在机会页手动发现。处理数不等于新增数，重复材料可能复用旧ID与旧来源。

如需重新登录，先停止活动任务，再在专用浏览器里退出账号重新登录。也可在服务停止且确认无活动任务后，将 `tools/mediacrawler-runtime/profiles/xhs`（或bili/wb）目录改名留备份，下一次显式开始会建立空profile；不要操作普通Chrome用户目录。不要分享profiles、会话文件或任务目录中的访问参数。

国内小红书任务若首次专用页面被跳到已识别的Rednote国际站，会显示 `waiting_for_domestic_page`，保持窗口供用户处理国内访问。请让**同一个专用标签页**停留在国内小红书（www.xiaohongshu.com），不要在国际页登录；此时程序尚未创建平台client或读取会话基线。等待循环每2秒只观察本地页面URL，不自动导航/重试，也不修改网络、代理、TLS或普通Chrome。回到国内官方HTTPS页后才放行原client与既有人工登录流程；任务仍受10分钟总时限和“停止本任务”约束。跳到其他外域、错误页或关闭受控标签页会安全失败。恢复后或登录确认后再次跳离国内页不会重新进入暂停。此状态不是国际采集能力，国内采集白名单保持不变。

## 采集范围与溯源

- 小红书：笔记描述正文，一级评论；不识别图片文字、不下载媒体。指定链接保留必要xsec访问参数；幂等身份只在XHS正文路径忽略xsec_token/xsec_source，原URL及快照完整保存。
- B站：规范化导出的简介最多500字符，是简介片段，**不是视频口播**。空简介可单独保留有效父对象的真实评论。AV/BV输入均可，实际规范化导出使用AV页。
- 微博：上游尝试展开长文，不能保证完整正文或全部楼中楼。
- 通用：最多3个父对象、每个最多8条一级评论，总预览上限30。搜索请求的页大小仍为上游10/20个对象；桥接先截取参与后续正文/评论处理的列表，不用事后截断冒充小批采集。同一任务同一父对象只保留首条有效正文。

作者昵称在上游已遮蔽，creator_hash为匿名化标识，不是原用户ID，因此原作者留空。source_created_at按平台真实秒/毫秒转换；source_captured_at取上游last_modify_ts或add_ts（采集端毫秒时间），缺失留空；任务起止另存，不补造逐条时间。评论没有专属URL时明确仅定位父页，有自身评论ID则保存，无ID留空；缺父对象、正文或合规URL会排除并显示计数。

raw_payload保存的是**上游规范化导出记录**，不是平台原始HTTP响应；另有任务ID、pin、平台、关键词/链接、限量与起止时间。真实性始终未认证，D1哈希只证明本地留存完整性。拒绝含会话/请求凭据字段的导出；必要内容访问URL参数可以保留。

## 接口

以下路径均挂在 `/api/v1`，使用MINING既有API Key鉴权：

| 方法与路径 | 用途 |
| --- | --- |
| GET `/mediacrawler/status` | 环境预检与当前活动任务；不启动浏览器 |
| POST `/mediacrawler/tasks` | 显式启动，返回202与任务ID |
| GET `/mediacrawler/tasks/{id}` | 有限状态、上限与安全提示 |
| POST `/mediacrawler/tasks/{id}/stop` | 停止本任务 |
| GET `/mediacrawler/tasks/{id}/results` | 仅completed/empty可读本任务材料 |

开始请求：`{"platform":"xhs","mode":"search","query":"工作流","url":"","max_posts":1,"max_comments":3}`。平台只允许xhs/bili/wb；detail模式须空query及对应平台单个HTTPS正文页，强制1篇。拒绝逗号多关键词/多链接、任意命令、未知字段和超上限值。

状态包含running、waiting_for_login、collecting、completed、empty、failed、cancelled、timed_out。非0退出、取消、超时或不安全输出不开放部分材料；exit0但没有有效材料为empty，不表示采集成功。每任务独立输出，仅接受本任务精确JSON/JSONL结构，限制单文件2MB、总8MB、200导出行；拒绝旧文件、符号链接、陌生路径与非有限JSON数值。

上游stdout/stderr直接丢弃，不经API或日志回传；只存有限状态。子进程环境使用白名单，不继承MINING模型/知乎/数据库/代理密钥。停止会发任务进程组SIGTERM，并给予专用浏览器上下文清理时间，随后只清理本任务组；不会查杀用户Chrome。上游或平台失败的详细原始日志不会暴露；可用安全错误码、登录窗口和链接排查。

启动失败时，任务回执可附有限 `diagnostic`：固定阶段、异常类名、固定错误类别、最多5个仓库相对文件/函数/行号。它不含异常消息、代码行、局部变量、绝对路径或原始日志；文件最多4096字节且严格白名单读取，格式错误继续显示通用失败。已知网络错误只映射certificate_error、connection_error或timeout，已知socket错误只映射browser_socket_path_limit；这些类别用于定位，不关闭TLS或浏览器安全检查。第一次失败优先，清理异常不会覆盖其位置。

小红书受控上下文的首个新页面，仅第一次导航到精确官方首页 `https://www.xiaohongshu.com`（可带末尾斜杠）、且使用默认等待条件时，改为等待DOMContentLoaded，仍最多30秒，已有更短正超时保留。其他URL、后续导航、其他页面/平台和显式等待条件保持原调用，不增加重试或改TLS。该调整针对已定位的首页等待超时，实网效果尚待验证；若仍超时，停止重复尝试，由人工判断本机网络。

## 验证边界

真实执行了独立安装、Chromium下载、上游help、无浏览器预检。三个平台字段与本地子进程、API及网页交接用明确OFFLINE fixture验证；这些数据不是平台实采。已有Chrome已登录小红书的用户回答也不等于专用profile已经登录。下一步需要在专用窗口完成一次人工登录，再验证真实1篇/3评论与D1快照。
