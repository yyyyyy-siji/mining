# D4 + D5 最终验收报告：项目内连接现有 Chrome 自动采集与严格机会判断闭环

日期：2026-11-16。

结论：**通过（PASS）**。已在不启动独立登录浏览器、不读取 Cookie、不关闭用户标签的前提下，通过 MINING 自身的 `/api/v1/existing-chrome` 连接用户已授权的普通 Chrome，完整跑通小红书三种采集模式（`current` 当前笔记、`search` 关键词搜索自动进笔记、`detail` 指定笔记链接）、批量导入、重复去重、D1 来源快照校验、严格未满足需求（`require_unmet_evidence=true`）三角色证据分析，以及安全断开连接。

---

## 1. 根因定位与导航交接最终窄修

在复验 `search` 与 `detail` 模式时，发现任务在 `Page.navigate` 刚返回的首帧轮询（约 0.28–0.35 秒）稳定报 `invalid_target_url`（`phase=navigate_search` / `phase=navigate_note`）。

通过独立 Chromium 实测复现确认：
- Chromium 在 `Page.navigate` 刚返回的 `step 0` 帧中，`Target.getTargetInfo` 会短暂返回空字符串 `targetInfo.url == ""`，约 50ms 后在 `step 1` 更新为目标 URL（如 `https://www.xiaohongshu.com/search_result/?keyword=...&type=51`）。
- 原 `_navigation_handoff` 对首帧空字符串直接调用 `validate_url("")`，导致在目标文档尚未完成 `TargetInfo` 同步前被误判为非法地址。
- **修复（`signal_miner/connectors/existing_chrome.py`）**：仅在自发导航交接窗口 `_navigation_handoff` 内调用 `_target_url(target, allow_pending_empty=True)`，将 `raw_url == ""` 视为尚未完成目标匹配的过渡态（`target_matches = False`），继续有界等待 `targetInfo.url` 与 `NAVIGATION_DOM_SCRIPT` 同时命中目标且 `ready_state in {"interactive", "complete"}`；超时仍报 `navigation_document_timeout`，交接窗口之外的空地址及任何非空非法地址仍立即拒绝。

冻结文件 SHA-256：
- `signal_miner/connectors/existing_chrome.py`: `f3dcac9dc952755fca2aa817062b4484f0617a6652c73e7903e2b3e61d847b30`
- `tests/test_existing_chrome_D4.py`: `6cfad15e874b389589f944de6147cb014294baec4b4b1dd18ba0cf49384d2896`

---

## 2. 真实环境端到端验收证据（`outputs/D4/commander-20261112/`）

1. **当前笔记模式（`mode="current"`）**
   - 任务 `c8034f984c3c4b5c9a189bf05ef91e8e`：`status="completed"`，提取 1 篇正文 + 3 条已加载一级评论（见 `live-current-task.json`、`live-current-result.json`）。
2. **关键词搜索自动寻址与正文提取（`mode="search"`, `query="记账软件 求推荐"`）**
   - 任务 `f3fcb3a2056c4226826e8763cbfd4f10`：经历 `navigate_search` → `read_search_results` → `navigate_note` → `read_note` → `complete`，自动从搜索结果页提取首个笔记链接并导航读取 1 篇笔记正文（`6a8bfcff000000000b026c41`）与 3 条已加载一级评论（`6a8c2cc00000000001008f8b`、`6a8c4891000000000202812d`、`6ad4865f000000000b0010d1`），保留 `search_result_href` 与 `navigated_note_url`（见 `live-search-task.json`、`live-search-result.json`）。
3. **指定链接模式（`mode="detail"`）**
   - 任务 `22cb91a6...`（保存于 `live-detail-task.json`、`live-detail-result.json`）：`status="completed"`，`phase="complete"`，提取同一笔记 1 篇正文 + 3 条评论。
4. **批量入库、去重与 D1 来源快照核验**
   - 首次导入 `search` 批次（`live-search-batch-import-receipt.json`）后，再次提交 `search` 批次（`live-search_repeat-receipt.json`）与 `detail` 批次（`live-detail_batch-receipt.json`）均返回 `{"total": 4, "ingested": 0, "duplicates": 4}`，完全复用实际反馈 ID `["rfb_875ac8cbc223458d81b1", "rfb_c1e0ec2a553e485aa10b", "rfb_24ae4f4549ef4f53a1da", "rfb_7e1c94f2064247a3a859"]`。
   - 4 个反馈 ID 的 `/api/v1/feedback/{id}/source-snapshot` 均返回 `status="verified"`、`body_sha256_matches=true`、`snapshot_sha256_matches=true`。
5. **严格未满足需求机会判断（`require_unmet_evidence=true`）**
   - 对 Qoder 推广材料批次（`live-promo-strict-result.json`）返回 **0 个候选**，并给出明确排除原因（正面推广/功能复述缺少未解决缺口原文证据）。
   - 对真实搜索入库的记账材料批次（`live-search-opportunity-result.json`）返回 **1 个待验证候选**（`记账时备注不打断的轻量记账工具`），`need_assessment` 完整区分：
     - `current_difficulty`：引用主帖原话（`rfb_875ac8cbc223458d81b1`，`snapshot_status="verified"`）；
     - `current_solution`：引用评论提及的替代方案（`rfb_24ae4f4549ef4f53a1da` `"鲨鱼 或者icost"`、`rfb_7e1c94f2064247a3a859` `"我一直用的是百事AA"`，均标注 `locator_level="parent_page"`）；
     - `remaining_gap`：引用主帖明确表述的二次补录摩擦（`rfb_875ac8cbc223458d81b1`）。
6. **安全断开连接**
   - 调用 `POST /api/v1/existing-chrome/disconnect` 返回 `status="disconnected"`，用户普通 Chrome 进程（`PID 8851`）与所选小红书标签保持打开未受影响。

---

## 3. 回归与静态检查

- 定向与关联回归：`.venv/bin/pytest -o addopts='' -q tests/test_existing_chrome_D4.py tests/test_existing_chrome_frontend.py tests/test_opportunity_admission.py tests/test_opportunity_discovery.py tests/test_source_evidence_D1.py tests/test_mediacrawler_D3.py` → **368 passed**（exit 0；此前全量 pytest **921 passed**）。
- 前端测试：`node --check frontend/static/app.js`（exit 0），`node --test ...` 五组共 **51/51 passed**（exit 0）。
- 静态检查：`ruff check` 与 `py_compile` 全部通过（exit 0），36 个历史测试文件 SHA-256 零改动（`legacy_36_changed=[]`）。
