# P12-2 交付报告：站点级真实采集适配器与证据包

交付日期：2026-07-08 | 返修-1: 2026-07-09 | 返修-3: 2026-07-09 | fix-4: 2026-07-09

## 结论

✅ 四次交付全绿。108 测试通过（P12-2 34 + P12-1 31 + 核心 43）。ruff 全范围 0。source_captured_at/raw_payload 已补齐到路由层并入库。API 证据 5/5 通过。

---

## fix-4 (2026-07-09)

### 对齐 AcquisitionEvidence 与 IngestRequest：source_captured_at / raw_payload

**问题：** `AcquisitionEvidence` 定义了 `source_captured_at` 和 `raw_payload` 字段，但 `IngestRequest` 和 `_prepare_ingest_data()` 未接收/持久化。

**修复：**

| 位置 | 变更 |
| --- | --- |
| `IngestRequest` | 新增 `source_captured_at: str \| None`、`raw_payload: dict \| None` |
| `_prepare_ingest_data()` | 非 None 时写入 context |
| `tests/test_feedback_ingest_source_contract.py` | 新增 3 条：摄入持久化、raw_payload 持久化、None 时不写入 |
| `scripts/p12_2_api_evidence.py` | 新增证据 5: source_captured_at/raw_payload 入库验证 (5/5) |

### 验证

- ruff 全范围: 0
- P12-2: 34 passed
- P12-1 ingest contract: 9 passed（+3 新增）
- P12-1 clickthrough: 22 passed
- 核心回归: 43 passed
- API 证据: 5/5 passed

---

## 返修说明

## 返修说明 3 (2026-07-09, 针对 `docs/acceptance-P12-2-fix-2-20260709.md`)

### P1: browser_screenshot 约束下沉到路由层

**问题：** `AcquisitionEvidence.validate()` 只在适配器路径拦截，运行态 POST `/api/v1/feedback/ingest` 时 `IngestRequest` 无 `screenshot_path` 字段，`_prepare_ingest_data()` 只做 URL 校验，browser_screenshot 缺证据数据仍返回 201。

**修复：**

| 位置 | 变更 |
| --- | --- |
| `IngestRequest` | 新增 `screenshot_path: str \| None`、`ocr_text: str \| None` 字段 |
| `_prepare_ingest_data()` | 新增 `capture_method=browser_screenshot` 且无 `screenshot_path` 无 `source_note` 时 raise 422 |
| `_prepare_ingest_data()` | `screenshot_path`、`ocr_text` 持久化到 `context` dict |

**新增测试（7 条）：**

| 测试 | 验证点 |
| --- | --- |
| `test_ingest_rejects_browser_screenshot_without_evidence` | 路由级 422，runner 未调用 |
| `test_batch_rejects_browser_screenshot_without_evidence` | 批量路由 422 + "第 2 条" |
| `test_ingest_accepts_browser_screenshot_with_screenshot_path` | 有 screenshot_path → 201，context 含截图路径 |
| `test_ingest_accepts_browser_screenshot_with_source_note` | 有 source_note → 201，context 含来源备注 |
| `test_ingest_persists_screenshot_path_to_context` | screenshot_path 正确写入 context |
| `test_ingest_persists_ocr_text_to_context` | ocr_text 正确写入 context |
| `test_ingest_omits_none_screenshot_and_ocr_from_context` | 不传时不写入空键 |

### P1: 前端证据字段入库（同上修复覆盖）

`screenshot_path` 和 `ocr_text` 现在通过 `IngestRequest` 接收，经 `_prepare_ingest_data()` 写入 `context` dict，传递给 `pipeline.runner.ingest_feedback()`，最终持久化到 `RawFeedbackRow.context`。

---

## fix-4 (2026-07-09)

### 对齐 AcquisitionEvidence 与 IngestRequest：source_captured_at / raw_payload

**问题：** `AcquisitionEvidence` 定义了 `source_captured_at` 和 `raw_payload` 字段，但 `IngestRequest` 和 `_prepare_ingest_data()` 未接收/持久化。

**修复：**

| 位置 | 变更 |
| --- | --- |
| `IngestRequest` | 新增 `source_captured_at: str \| None`、`raw_payload: dict \| None` |
| `_prepare_ingest_data()` | 非 None 时写入 context |
| `tests/test_feedback_ingest_source_contract.py` | 新增 3 条：摄入持久化、raw_payload 持久化、None 时不写入 |
| `scripts/p12_2_api_evidence.py` | 新增证据 5: source_captured_at/raw_payload 入库验证 (5/5) |

### 验证

- ruff 全范围: 0
- P12-2: 34 passed
- P12-1 ingest contract: 9 passed（+3 新增）
- P12-1 clickthrough: 22 passed
- 核心回归: 43 passed
- API 证据: 5/5 passed

---

## 返修说明

以下为 2026-07-09 针对验收报告 `docs/acceptance-P12-2-source-acquisition-adapters.md` 三个阻断项的修复。

### P1-1: ruff 全范围命令修复

指令要求命令：
```bash
ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py
```

**修复内容：**

| 文件 | 问题 | 修复方式 |
| --- | --- | --- |
| `signal_miner/connectors/__init__.py` | F401 unused imports (FeedbackAuthor, FeedbackContent), W293 blank lines with whitespace | 删除未使用导入，整理空白行 |
| `signal_miner/connectors/media_crawler_client.py` | W291 trailing whitespace, W293 blank lines, I001 import sort, UP035 AsyncIterator, ARG002 unused platform | 重写导入块，AsyncIterator 移至 TYPE_CHECKING，ARG002 加 noqa，删除所有尾随空白 |
| `signal_miner/connectors/platforms/bilibili.py` | I001 import sort, TC003 AsyncIterator, F401 unused TYPE_CHECKING | AsyncIterator 移至 TYPE_CHECKING，导入重排 |
| `signal_miner/connectors/platforms/douyin.py` | 同上 + F401 unused asyncio | AsyncIterator 移至 TYPE_CHECKING，删除 asyncio，导入重排 |
| `signal_miner/connectors/platforms/weibo.py` | I001 import sort, TC003 AsyncIterator, F401 unused TYPE_CHECKING | AsyncIterator 移至 TYPE_CHECKING，导入重排 |
| `signal_miner/connectors/platforms/xiaohongshu.py` | 同上 + F401 unused asyncio | AsyncIterator 移至 TYPE_CHECKING，删除 asyncio，导入重排 |

所有修复仅涉及 lint/typing/空白级别，不改变业务行为。**退出码：0**，输出：`All checks passed!`

### P1-2: 批量适配器失败策略

**修改文件：**

- `signal_miner/connectors/platforms/search_adapter.py` — `from_search_results_batch()`：遇到缺 URL/不合规条目时抛出 `EvidencePackageError`，含 `"第 {idx} 条"` 提示。不再 `continue` 静默跳过。
- `signal_miner/connectors/platforms/generic_adapter.py` — `from_dicts_batch()`：同上策略。

**更新测试：**

| 原测试名 | 修改 |
| --- | --- |
| `test_search_result_batch_skips_invalid` | → `test_search_result_batch_rejects_invalid_item`，断言 `EvidencePackageError` + `"第 2 条"` |
| `test_generic_adapter_batch_skips_invalid` | → `test_generic_adapter_batch_rejects_invalid_item`，断言 `EvidencePackageError` + `"第 2 条"` |

### P1-3: 运行态证据

**方法：** 使用 FastAPI TestClient（ASGI 协议，等价真实 HTTP 路由行为），不可行原因：browser-use CLI 未安装、playwright 未安装，无法截取可视化浏览器截图。改为 TestClient API 验证 + 源代码级 HTML 验证。

**证据文件：**

| 文件 | 内容 |
| --- | --- |
| `docs/P12-2-screenshots/p12-2-api-evidence.json` | 4 条 API 证据：合法 GitHub 201、搜索列表页 422、browser_screenshot 拒绝、有 screenshot_path 通过 |
| `docs/P12-2-screenshots/p12-2-import-evidence-package-fields.md` | 前端源代码级验证：证据包字段说明 HTML、browser-screenshot-hint 元素、JS 切换逻辑、curl 页面可访问验证 |

**API 证据脚本：** `scripts/p12_2_api_evidence.py`（可复跑）

**API 证据摘要：**

| 场景 | 验证路径 | 状态 | 结果 |
| --- | --- | --- | --- |
| 合法 GitHub 证据包 → POST /feedback/ingest | TestClient → `to_ingest_payload()` → 路由层 P12-1 校验 | 201 | ✅ |
| Google 搜索列表页 URL 被拒绝 | TestClient → `to_ingest_payload()` EvidencePackageError + 路由层 422 | 422 + EvidencePackageError | ✅ |
| browser_screenshot 缺截图/备注被拒绝 | `to_ingest_payload()` → `validate()` → EvidencePackageError | EvidencePackageError | ✅ |
| browser_screenshot 有 screenshot_path 通过 | `to_ingest_payload()` → source_note 含 screenshot_path | 通过 | ✅ |

**前端证据摘要：**

| 验证项 | 位置 | 结果 |
| --- | --- | --- |
| 批量 JSON 区"证据包字段说明" | app.js:682 | ✅ 含全部必填/可选字段名 |
| browser_screenshot 黄色警告提示 | app.js:626-628 | ✅ "必须填写截图路径或在来源备注中说明" |
| JS 切换逻辑 | app.js:583-597 | ✅ 选 browser_screenshot 时显示/隐藏 |
| 页面可访问 | curl localhost:8000 | ✅ 返回 HTML |

**未覆盖风险：**
- 缺少可视化浏览器截图（browser-use/playwright 未安装），源代码验证 + TestClient 替代。
- 后续若需可视化回归测试，建议安装 playwright 或 browser-use。

---

## 修改文件

| 文件 | 修改目的 |
| --- | --- |
| `signal_miner/connectors/source_acquisition.py` | 新增：统一证据包模型 + 转换契约 |
| `signal_miner/connectors/platforms/__init__.py` | 新增：适配器包入口 |
| `signal_miner/connectors/platforms/github_adapter.py` | 新增：GitHub issue/comment → 证据包适配器 |
| `signal_miner/connectors/platforms/cnblogs_adapter.py` | 新增：博客园 API JSON / URL → 证据包适配器 |
| `signal_miner/connectors/platforms/bilibili_adapter.py` | 新增：B 站视频/评论 → 证据包适配器 |
| `signal_miner/connectors/platforms/search_adapter.py` | 新增：搜索引擎结果 → 证据包适配器 |
| `signal_miner/connectors/platforms/generic_adapter.py` | 新增：通用 manual/csv/json → 证据包适配器 |
| `frontend/static/app.js` | 补强：批量 JSON 证据包字段说明 + browser_screenshot 提示 |
| `tests/test_source_acquisition_contract.py` | 新增：P12-2 全量合约测试 (27 条) |
| `docs/acceptance-P12-2-delivery-20260708.md` | 更新：交付报告含返修说明 |
| `docs/P12-2-screenshots/p12-2-api-evidence.json` | 新增：API 运行态证据（TestClient） |
| `docs/P12-2-screenshots/p12-2-import-evidence-package-fields.md` | 新增：前端证据包字段说明验证 |
| `scripts/p12_2_api_evidence.py` | 新增：API 证据采集脚本（可复跑） |
| **返修：** | |
| `signal_miner/connectors/__init__.py` | 修复：ruff F401/W293 |
| `signal_miner/connectors/media_crawler_client.py` | 修复：ruff W291/W293/I001/UP035/ARG002 |
| `signal_miner/connectors/platforms/bilibili.py` | 修复：ruff I001/TC003/F401 |
| `signal_miner/connectors/platforms/douyin.py` | 修复：ruff I001/F401/TC003 |
| `signal_miner/connectors/platforms/weibo.py` | 修复：ruff I001/TC003/F401 |
| `signal_miner/connectors/platforms/xiaohongshu.py` | 修复：ruff I001/F401/TC003 |
| `signal_miner/connectors/platforms/search_adapter.py` | 修复：批量方法改为抛异常 |
| `signal_miner/connectors/platforms/generic_adapter.py` | 修复：批量方法改为抛异常 |

## 证据包字段契约

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `source_type` | 是 | 平台策略键（github/cnblogs/bilibili/...） |
| `external_url` | 是 | 原始页面 / 资源 URL（可点击） |
| `capture_method` | 是 | 采集方法（official_api/crawler/browser_screenshot/manual_browser/webhook） |
| `text` | 是 | 反馈正文 |
| `subject` | 否 | 标题 |
| `author_name` | 否 | 作者名 |
| `source_note` | 否 | 来源备注 |
| `source_captured_at` | 否 | 采集时间 |
| `raw_payload` | 否 | 原始数据 payload |
| `screenshot_path` | 否 | 截图路径（browser_screenshot 时推荐） |
| `ocr_text` | 否 | OCR 识别文本 |
| `author_email` | 否 | 作者邮箱 |
| `company` | 否 | 公司 |
| `segment` | 否 | 客户段位 |
| `video_url` | 否 | 视频 URL（aigc_video profile） |
| `views` | 否 | 播放量 |
| `likes` | 否 | 点赞量 |
| `platform` | 否 | 平台标识 |

**特别规则**：`capture_method=browser_screenshot` 时，必须提供 `screenshot_path` 或 `source_note`，否则 `validate()` 拒绝。

## 首批适配器覆盖

| source_type | 输入 | 输出 | 是否真实联网 | 限制 |
| --- | --- | --- | --- | --- |
| `github` | issue/comment JSON (GitHub API v3) | `AcquisitionEvidence`，保留 `html_url` | 否（适配器只解析 JSON） | 需要调用方提供真实 API 返回数据 |
| `cnblogs` | 博客园 Open API JSON 或 URL+文本 | `AcquisitionEvidence`，保留 `cnblogs.com` URL | 否（适配器只解析 JSON） | 需要调用方提供真实数据 |
| `video_bilibili` / `bilibili` | BV 视频页 URL + 标题/描述/评论 | `AcquisitionEvidence`，保留 `bilibili.com/video/...` | 否（适配器只构造证据包） | 不伪造评论，所有内容由调用方提供 |
| `baidu_search` / `google_search` / `bing_search` / `sogou_search` / `so360_search` | 搜索 API 结果 JSON 数组 | `AcquisitionEvidence`，使用落地页 URL（非搜索列表页） | 否 | 列表页 URL 被 P12-1 拦截 |
| `manual` / `csv` / `json` / `custom` | 任意字典 | `AcquisitionEvidence`，预检 URL 和字段 | 否 | 通用适配器，不做平台特定解析 |

## 验证命令

| 命令 | 退出码 | 关键输出 |
| --- | ---: | --- |
| `ruff check signal_miner/connectors signal_miner/models/feedback.py ...` (完整命令) | 0 | All checks passed! |
| `node --check frontend/static/app.js` | 0 | 无输出（成功） |
| `git diff --check` | 0 | 无输出（成功） |
| `pytest tests/test_source_acquisition_contract.py -q` | 0 | 27 passed |
| `pytest tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py -q` | 0 | 28 passed |
| `pytest tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | 0 | 25 passed |
| `pytest tests/test_prd_generator.py tests/test_prd_routes.py -q` | 0 | 18 passed |

## 负例证据

| 场景 | 期望 | 实际 |
| --- | --- | --- |
| GitHub issue 缺少 `html_url` | 抛出 `EvidencePackageError`，包含 "html_url" | ✅ 按预期抛出 |
| Google 搜索结果列表页 URL `https://www.google.com/search?q=aigc` | `to_ingest_payload()` 抛出，包含 "落地页" | ✅ P12-1 拦截 |
| `browser_screenshot` 缺 `screenshot_path` 且缺 `source_note` | `validate()` 抛出 `EvidencePackageError`，包含 "screenshot_path" | ✅ 按预期抛出 |
| B 站适配器传入抖音 URL | `to_ingest_payload()` 抛出，包含 "哔哩哔哩" | ✅ P12-1 域名校验拦截 |
| 通用适配器所有 URL 字段为空 | 构造抛出 `EvidencePackageError`，包含 "external_url" | ✅ 按预期抛出 |

## 运行态证据

> 全部证据文件位于 `docs/P12-2-screenshots/`。

### API 证据 (`p12-2-api-evidence.json`)

使用 FastAPI TestClient（ASGI 协议，等价真实 HTTP 路由行为）验证：

| 场景 | 方法 | 状态 | 结果 |
| --- | --- | --- | --- |
| 合法 GitHub issue 证据包 → POST /api/v1/feedback/ingest | TestClient + mock runner | 201 ✅ | feedback_id 返回 |
| Google 搜索列表页 URL `google.com/search?q=...` | to_ingest_payload() → EvidencePackageError + 路由层 422 | 422 ✅ | detail 含 "落地页" |
| browser_screenshot 缺 screenshot_path 且缺 source_note | validate() → EvidencePackageError | Error ✅ | "screenshot_path 或 source_note" |
| browser_screenshot 有 screenshot_path 时通过 | to_ingest_payload() → source_note 含路径 | 通过 ✅ | "screenshot_path=/tmp/..." |

脚本：`scripts/p12_2_api_evidence.py`（可复跑）

### 前端证据 (`p12-2-import-evidence-package-fields.md`)

- 批量 JSON 区 "证据包字段说明" 列出全部必填/可选字段名 ✅
- browser-screenshot-hint 黄色警告："必须填写截图路径或在来源备注中说明" ✅
- JS updateSourceAcquisitionControls 自动切换显示/隐藏 ✅
- curl localhost:8000 返回正常 HTML ✅

> 注：browser-use CLI / playwright 未安装，无法截取可视化截图。以源代码级验证 + TestClient + curl 替代。

## 回归确认

- ✅ P12-1 全部 28 个测试通过（URL 必填、域名匹配、搜索落地页、批量预校验）
- ✅ 核心连接器测试通过（response models, github connector, evidence chain）
- ✅ PRD 路由和生成器测试通过
- ✅ 前端 SPA 合约测试通过（batch array、ingested 字段、URL 标准化、source 状态、点击链接、证据追踪）
- ✅ 无放松任何 P12-1 门禁

## 风险 / 未覆盖项

1. **未实现真实 API/页面抓取**：所有适配器是"证据包转换器"，不是网络采集器。调用方必须自行获取原始数据后交给适配器转换。这与指令要求一致——"本阶段可以不真实调用外部 API，但必须把适配器路径打通并测试"。
2. **GitHub adapter 依赖调用方传入真实 API JSON**：适配器不发起网络请求，不验证 token。
3. **博客园 adapter 未验证 token**：`capture_method=official_api` 假定调用方已通过 API 获取数据。
4. **B 站适配器不验证评论真实性**：评论内容由调用方提供，适配器只构造证据包。
5. **搜索适配器不过滤低质量结果**：只做 URL 提取和 P12-1 校验，不判断内容相关性。
6. **截图/OCR 标注为未自动完成**：`screenshot_path` 和 `ocr_text` 是可选字段，填入与否由调用方决定。`browser_screenshot` 方法下只要求至少填写其一，不要求 OCR 已实际运行。
