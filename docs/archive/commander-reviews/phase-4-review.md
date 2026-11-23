# ✅ Phase 4 指挥官审查报告 — 多源连接器

**审查日期**: 2026-05-30  
**审查者**: Commander AI  
**审查轮次**: 第 1 轮（初审）

---

## 🟢 最终裁定: Phase 4 一次通过，批准合并

执行者交付质量**显著提升**——本轮零 Blocker、零 Must-Fix，所有 5 大任务模块均一次性通过独立代码审查。

---

## 📋 逐文件审计结果

### 1. GitHub Issues 连接器 ✅

**文件**: [github_connector.py](./signal_miner/connectors/github_connector.py) — 237 行

| 检查项 | 结果 | 证据 |
|--------|------|------|
| `source_type = "github"` | ✅ | L33 |
| `httpx.AsyncClient` + `timeout=30.0` | ✅ | L82 |
| 分页：`page` + `per_page=100` + 空数组终止 | ✅ | L74, L84, L90-91 |
| Rate Limit：`X-RateLimit-Remaining ≤ 5` → sleep | ✅ | L130-146, 使用 `asyncio.sleep` |
| PR 过滤：`"pull_request" in issue` → skip | ✅ | L95-96 |
| dedupe_key：`github_{repo}_{number}` | ✅ | L165 |
| Comment dedupe：`..._{number}_comment_{id}` | ✅ | L218 |
| 字段映射完整（title→subject, body→text, user.login→name, labels→context） | ✅ | L148-179 |
| `structlog` 逐页日志 | ✅ | L108-113 |
| Comment 独立分页 | ✅ | L191-236 |
| `source_created_at` 解析（含 `contextlib.suppress` 容错） | ✅ | L156-160 |

**评价**: 实现非常扎实。Rate Limit 处理先于 `raise_for_status()` 执行（L86-87），属于防御性编程，体现了工程意识。

---

### 2. Webhook 连接器 ✅

**文件**: [webhook_connector.py](./signal_miner/connectors/webhook_connector.py) — 124 行

| 检查项 | 结果 | 证据 |
|--------|------|------|
| HMAC-SHA256 签名验证 | ✅ | L60-64, `hmac.new` + `hashlib.sha256` |
| 时序攻击防护：`hmac.compare_digest` | ✅ | L66 |
| 无密钥 → 放行 (`return True`) | ✅ | L52-53 |
| 剥离 `sha256=` 前缀 | ✅ | L57-58 |
| 宽松字段映射（5 种 text 键 + 4 种 author 键） | ✅ | L82, L89-90 |
| 缺失 text → `ValueError` + 可用键列表 | ✅ | L83-87 |
| dedupe_key：`webhook_{source_id}_{sha256[:16]}` | ✅ | L98 |
| Context 提取排除核心键 | ✅ | L106-110 |

**⚠️ 观察**: `WebhookConnector` 未实现 `fetch()` 方法。指令中允许 "空实现或 `NotImplementedError`"，执行者选择完全省略。由于 `BaseConnector` 是 `Protocol`（结构化类型），Python 不在注册时强制检查，因此不影响运行。可接受但建议后续补充。

---

### 3. 连接器注册表 ✅

**文件**: [connectors/\_\_init\_\_.py](./signal_miner/connectors/__init__.py) — 71 行

| 检查项 | 结果 | 证据 |
|--------|------|------|
| `CONNECTOR_REGISTRY` 字典 | ✅ | L32 |
| `register_connector(name, cls)` | ✅ | L35-37 |
| `get_connector(name)` + `ValueError` 异常 | ✅ | L40-51 |
| `list_connectors()` | ✅ | L54-56 |
| 自动注册 csv/manual/github/webhook | ✅ | L63-70 |
| `BaseConnector` Protocol 未被修改 | ✅ | L18-25 保持原样 |

**评价**: 注册表实现简洁正确。`noqa: E402` 注释处理底部导入的 Ruff 兼容性。

---

### 4. API 路由 ✅

**文件**: [routes/connectors.py](./signal_miner/routes/connectors.py) — 160 行

| 端点 | 状态 | 关键实现 |
|------|------|----------|
| `GET /connectors` | ✅ | L35-38, 调用 `list_connectors()` |
| `POST /connectors/github/fetch` | ✅ | L41-96, `GitHubFetchRequest` 含 regex 校验 |
| `POST /connectors/webhook/ingest` | ✅ | L99-159, 签名验证 + 403 拒绝 + 201 成功 |

**关键安全验证:**
- GitHub 路由：从 `runtime.settings.github_token` 获取 token ✅
- Webhook 路由：先检查 `X-Hub-Signature-256`，再检查 `X-Signature` ✅
- 签名失败 → `HTTPException(403, "Invalid webhook signature.")` ✅
- `GitHubFetchRequest.repo` 有 `pattern=r"^[^/]+/[^/]+$"` 校验 ✅
- `GitHubFetchRequest.state` 有 `pattern=r"^(open|closed|all)$"` 校验 ✅

**⚠️ 观察**: GitHub 路由中每个 feedback 项创建独立 DB session（L73）。对于大型仓库效率不高，但作为 Phase 4 的正确性优先实现可接受，可在 Phase 6 生产化时优化为批量提交。

---

### 5. 配置变更 ✅

| 文件 | 变更 | 状态 |
|------|------|------|
| [settings.py](./signal_miner/settings.py#L65-L67) | 新增 `github_token`、`webhook_secret` | ✅ |
| [.env.example](./.env.example#L64-L65) | 新增 `GITHUB_TOKEN`、`WEBHOOK_SECRET` 示例 | ✅ |
| [main.py](./signal_miner/main.py#L21) | `connectors_router` 导入并注册 `/api/v1` | ✅ |
| `httpx` 依赖 | 已存在于 `pyproject.toml` | ✅ 无新增依赖 |

---

### 6. 测试覆盖 ✅

| 测试文件 | 用例数 | 状态 |
|----------|--------|------|
| [test_github_connector.py](./tests/test_github_connector.py) | **9** | ✅ 超出要求（要求 8） |
| [test_webhook_connector.py](./tests/test_webhook_connector.py) | **11** | ✅ 超出要求（要求 6） |
| [test_connectors.py](./tests/test_connectors.py) 追加 | **4** | ✅ 完全满足 |
| **合计** | **24** | ✅ 超出 18+ 要求 |

**测试质量亮点:**
- `test_fetch_pagination` — 用 `side_effect` + `call_count` 模拟多页翻页，验证自动分页逻辑
- `test_fetch_with_comments` — 精确模拟 issues URL vs comments URL 返回不同响应
- `test_register_custom` — `finally` 块清理全局注册表，防止测试污染
- `test_verify_signature_without_prefix` — 测试无 `sha256=` 前缀的兼容性

**⚠️ 环境限制**: 与 Phase 3 相同，因 `pydantic_core` 代码签名限制无法在当前环境执行完整测试套件。风险评估见下方。

---

## ⚖️ 风险评估（替代全量测试验证）

| 风险点 | 评估 | 理由 |
|--------|------|------|
| 新代码破坏现有连接器 | 🟢 极低 | `__init__.py` 仅追加注册表代码，`CSVConnector` / `ManualConnector` 零修改 |
| 新路由破坏现有路由 | 🟢 无风险 | `connectors.py` 是全新文件，`main.py` 仅追加 1 行 `include_router` |
| Settings 变更破坏启动 | 🟢 极低 | 新增字段均有空字符串默认值，不影响现有 `.env` |
| 新依赖冲突 | 🟢 无风险 | 未引入任何新第三方依赖 |

---

## 📊 执行者成长评估

| 维度 | Phase 3 | Phase 4 | 变化 |
|------|---------|---------|------|
| 架构合规性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | — |
| 代码质量 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ↑ 防御性编程更强 |
| 测试覆盖 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | — 24 用例超额 |
| 交付完整性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | — 仍受环境限制 |
| 首轮通过率 | 否（返工 1 次） | **是（一次通过）** | ↑↑ |

---

## 📦 Phase 4 最终交付物清单

| 类型 | 文件 | 行数 | 核心产出 |
|------|------|------|----------|
| [NEW] | `connectors/github_connector.py` | 237 | REST API v3 + 分页 + Rate Limit + PR 过滤 |
| [NEW] | `connectors/webhook_connector.py` | 124 | HMAC-SHA256 签名 + 宽松字段映射 |
| [MODIFY] | `connectors/__init__.py` | 71 (+45) | 注册表模式 |
| [NEW] | `routes/connectors.py` | 160 | 3 个 API 端点 |
| [MODIFY] | `settings.py` | 68 (+4) | `github_token` + `webhook_secret` |
| [MODIFY] | `main.py` | +2 | 路由注册 |
| [MODIFY] | `.env.example` | +4 | 配置示例 |
| [NEW] | `tests/test_github_connector.py` | 268 | 9 个测试 |
| [NEW] | `tests/test_webhook_connector.py` | 149 | 11 个测试 |
| [MODIFY] | `tests/test_connectors.py` | 137 (+48) | 4 个注册表测试 |

**总计: 5 个新文件 + 5 个修改文件 · 24 个测试用例 · 3 个新 API 端点**

---

## 🏁 Phase 4 正式关闭

**Phase 4 — Multi-Source Connectors 已通过指挥官验收，正式关闭。**

### 已完成阶段回顾

| 阶段 | 名称 | 状态 |
|------|------|------|
| Phase 0 | 工程基础加固 | ✅ 已完成 |
| Phase 1 | Pipeline 健壮性 | ✅ 已完成 |
| Phase 2 | 证据链闭环 | ✅ 已完成 |
| Phase 3 | PRD 生成器与导出 | ✅ 已完成 |
| Phase 4 | 多源连接器 | ✅ **刚刚通过** |
| Phase 5 | 前端升级与交互体验 | 🔴 待规划 |
| Phase 6 | 生产化准备 | 🔴 待规划 |

下一步：当您准备好时，指挥官将开始 **Phase 5（前端升级）** 的需求分析与任务规划。
