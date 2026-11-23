# Phase 4: 多源连接器 (Multi-Source Connectors) — 执行指令

> **致执行者 (Executor AI)**:
> 我是本项目的指挥官。Phase 3（PRD 生成器）已通过验收并正式关闭。欢迎进入 Phase 4。
> **你的边界：仅执行本阶段任务，不得修改与本阶段无关的底层架构。**

---

## 🎯 阶段目标

摆脱单一的 CSV 文件导入模式，建立**可扩展的连接器体系**，接入 **GitHub Issues** 和 **通用 Webhook** 两种实时反馈源。用户通过新增的 API 端点即可触发从 GitHub 仓库拉取 Issues，或通过 Webhook 接收第三方推送。

---

## 📐 现有架构约束（必读）

在编码前，你必须理解以下已定型的接口契约，**不得修改它们**：

### 1. BaseConnector Protocol（[connectors/\_\_init\_\_.py](./signal_miner/connectors/__init__.py)）
```python
class BaseConnector(Protocol):
    source_type: str
    async def fetch(self) -> AsyncIterator[RawFeedback]: ...
```

### 2. RawFeedback 模型（[models/feedback.py](./signal_miner/models/feedback.py#L50-L72)）
```python
class RawFeedback(BaseModel):
    source_type: str          # "csv", "manual", "github", "webhook"
    source_id: str            # 标识来源配置
    dedupe_key: str           # 幂等去重键
    external_id: str | None   # 外部系统原始 ID
    external_url: str | None  # 回链
    author: FeedbackAuthor
    content: FeedbackContent  # subject + text
    context: dict             # 任意元数据
```

### 3. 现有 CSVConnector 参考实现（[csv_connector.py](./signal_miner/connectors/csv_connector.py)）
你的新连接器必须与它保持相同的设计模式：实现 `BaseConnector` Protocol，通过 `async def fetch()` 生成 `RawFeedback` 迭代器。

---

## 📝 任务清单

### 任务 1: GitHub Issues 连接器

**创建文件** `signal_miner/connectors/github_connector.py`

#### 1.1 类签名
```python
class GitHubConnector:
    source_type: str = "github"

    def __init__(
        self,
        repo: str,                     # "owner/repo" 格式
        token: str | None = None,      # GitHub Personal Access Token（可选，用于私有仓库和提升 Rate Limit）
        labels: list[str] | None = None,  # 可选标签过滤，如 ["bug", "feature-request"]
        state: str = "all",            # "open" | "closed" | "all"
        since: str | None = None,      # ISO8601 时间过滤，如 "2026-01-01T00:00:00Z"
        source_id: str | None = None,  # 默认为 "github_{owner}_{repo}"
        include_comments: bool = True, # 是否将 Issue 的评论也作为独立反馈项
    ) -> None: ...

    async def fetch(self) -> AsyncIterator[RawFeedback]: ...
```

#### 1.2 核心逻辑要求
- **HTTP 请求**：使用 `httpx.AsyncClient` 调用 GitHub REST API v3
  - Issues 端点: `GET https://api.github.com/repos/{owner}/{repo}/issues`
  - Comments 端点: `GET https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments`
- **分页处理**：GitHub API 默认每页 30 条，最多 100。必须通过 `Link` 响应头或 `?page=N&per_page=100` 参数实现自动翻页，直到没有更多结果
- **Rate Limit 处理**：检查响应头 `X-RateLimit-Remaining`，当剩余次数 ≤ 5 时，读取 `X-RateLimit-Reset` 并 `await asyncio.sleep()` 等待重置
- **去重键（dedupe_key）**：`github_{repo}_{issue_number}`（Issue 本体）或 `github_{repo}_{issue_number}_comment_{comment_id}`（评论）
- **字段映射**：

  | GitHub API 字段 | RawFeedback 字段 |
  |---|---|
  | `issue.number` | `external_id` |
  | `issue.html_url` | `external_url` |
  | `issue.title` | `content.subject` |
  | `issue.body` | `content.text` |
  | `issue.user.login` | `author.name` |
  | `issue.labels[].name` | `context.labels` |
  | `issue.state` | `context.state` |
  | `issue.created_at` | `source_created_at`（需解析为 datetime） |

- **过滤 Pull Requests**：GitHub Issues API 会返回 PR，必须通过检查 `"pull_request" not in issue` 来跳过 PR
- **日志记录**：使用 `structlog` 记录拉取进度（每页完成后 log 一次）

#### 1.3 验收标准
- `GitHubConnector("owner/repo")` 实例化不报错
- `async for item in connector.fetch()` 能生成合规的 `RawFeedback` 对象
- Issue 评论（当 `include_comments=True`）也作为独立 `RawFeedback` 被 yield
- PR 被正确过滤
- `dedupe_key` 在 Issue 和 Comment 之间唯一且稳定

---

### 任务 2: 通用 Webhook 连接器

**创建文件** `signal_miner/connectors/webhook_connector.py`

#### 2.1 类签名
```python
class WebhookConnector:
    source_type: str = "webhook"

    def __init__(
        self,
        source_id: str = "webhook_default",
        secret: str | None = None,  # HMAC-SHA256 签名验证密钥
    ) -> None: ...

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """验证 Webhook 签名（X-Hub-Signature-256 或 X-Signature 头）。"""
        ...

    def parse_payload(self, payload: dict) -> RawFeedback:
        """将 Webhook JSON payload 转换为 RawFeedback。"""
        ...
```

#### 2.2 核心逻辑要求
- **签名验证**：使用 `hmac.new(secret, payload, hashlib.sha256).hexdigest()` 进行 HMAC-SHA256 校验。比较时使用 `hmac.compare_digest()` 防止时序攻击
- **Payload 解析**：Webhook 的 JSON 格式不确定，需做**宽松字段映射**（与 CSVConnector 的 `_first_nonempty` 模式一致）：
  - `text` / `content` / `body` / `message` / `feedback` → `content.text`
  - `title` / `subject` / `summary` → `content.subject`
  - `author` / `user` / `sender` / `name` → `author.name`
  - `email` → `author.email`
- **去重键**：`webhook_{source_id}_{sha256(payload_text)[:16]}`
- **`fetch()` 方法**：对于 Webhook 这种推送型连接器，`fetch()` 方法不适用（它是拉取模式）。保留为空实现或 raise `NotImplementedError("Webhook is push-based. Use parse_payload() instead.")`

#### 2.3 验收标准
- 正确的签名验证通过/拒绝测试
- 各种格式的 payload 都能解析出 `RawFeedback`
- 缺少 `text` 字段的 payload 抛出明确的 `ValueError`

---

### 任务 3: 连接器注册表

**修改文件** `signal_miner/connectors/__init__.py`

#### 3.1 新增内容
在现有 `BaseConnector` Protocol 之后，添加一个连接器工厂/注册表：

```python
# 连接器类型注册表
CONNECTOR_REGISTRY: dict[str, type] = {}

def register_connector(name: str, connector_class: type) -> None:
    """注册一个连接器类型。"""
    CONNECTOR_REGISTRY[name] = connector_class

def get_connector(name: str) -> type:
    """获取已注册的连接器类型。"""
    if name not in CONNECTOR_REGISTRY:
        raise ValueError(f"Unknown connector type: '{name}'. Available: {list(CONNECTOR_REGISTRY.keys())}")
    return CONNECTOR_REGISTRY[name]

def list_connectors() -> list[str]:
    """列出所有已注册的连接器类型名称。"""
    return list(CONNECTOR_REGISTRY.keys())
```

#### 3.2 自动注册
在 `__init__.py` 的底部，导入并注册所有已有连接器：
```python
from signal_miner.connectors.csv_connector import CSVConnector, ManualConnector
from signal_miner.connectors.github_connector import GitHubConnector
from signal_miner.connectors.webhook_connector import WebhookConnector

register_connector("csv", CSVConnector)
register_connector("manual", ManualConnector)
register_connector("github", GitHubConnector)
register_connector("webhook", WebhookConnector)
```

#### 3.3 验收标准
- `list_connectors()` 返回 `["csv", "manual", "github", "webhook"]`
- `get_connector("github")` 返回 `GitHubConnector` 类
- `get_connector("unknown")` 抛出 `ValueError`

---

### 任务 4: 配置与 API 路由扩展

#### 4.1 Settings 扩展
**修改文件** [settings.py](./signal_miner/settings.py)

在 `AppSettings` 类末尾的 `# --- Pipeline ---` 区块之后新增：
```python
# --- Connectors ---
github_token: str = ""
webhook_secret: str = ""
```

同时在 [.env.example](./.env.example) 末尾追加：
```
# --- Connectors ---
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WEBHOOK_SECRET=your_webhook_signing_secret
```

#### 4.2 新增 API 路由
**创建文件** `signal_miner/routes/connectors.py`

新增以下 3 个端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/connectors` | 列出所有已注册的连接器类型 |
| `POST` | `/api/v1/connectors/github/fetch` | 触发 GitHub Issues 拉取并写入 `raw_feedback_items` 表 |
| `POST` | `/api/v1/connectors/webhook/ingest` | 接收 Webhook 推送 payload 并写入 `raw_feedback_items` 表 |

##### 4.2.1 `GET /api/v1/connectors`
```python
@router.get("/connectors", summary="List available connector types")
async def list_available_connectors() -> dict:
    from signal_miner.connectors import list_connectors
    return {"connectors": list_connectors()}
```

##### 4.2.2 `POST /api/v1/connectors/github/fetch`
请求体 Schema:
```python
class GitHubFetchRequest(BaseModel):
    repo: str = Field(..., description="GitHub repo in 'owner/repo' format", pattern=r"^[^/]+/[^/]+$")
    labels: list[str] | None = None
    state: str = Field("all", pattern=r"^(open|closed|all)$")
    since: str | None = Field(None, description="ISO8601 datetime filter")
    include_comments: bool = True
```

逻辑：
1. 从 `http_request.app.state.runtime.settings.github_token` 获取 token
2. 创建 `GitHubConnector(repo=req.repo, token=token, ...)`
3. `async for feedback in connector.fetch():` 逐条调用 `ingest_feedback(data)` 写入数据库
4. 返回 `{"repo": repo, "ingested_count": N, "source_type": "github"}`

##### 4.2.3 `POST /api/v1/connectors/webhook/ingest`
逻辑：
1. 从请求头获取签名：`X-Hub-Signature-256` 或 `X-Signature`
2. 从 `settings.webhook_secret` 获取密钥
3. 如果密钥已配置且签名存在，调用 `connector.verify_signature()` 校验；校验失败返回 `403 Forbidden`
4. 调用 `connector.parse_payload(payload)` 解析为 `RawFeedback`
5. 调用 `ingest_feedback(data)` 写入数据库
6. 返回 `201 Created` + `{"feedback_id": id, "source_type": "webhook"}`

##### 4.2.4 路由注册
**修改文件** [main.py](./signal_miner/main.py) — 在现有路由注册区域追加：
```python
from signal_miner.routes.connectors import router as connectors_router
app.include_router(connectors_router, prefix="/api/v1", tags=["connectors"])
```

#### 4.3 验收标准
- `GET /api/v1/connectors` 返回包含 4 种连接器的列表
- `POST /api/v1/connectors/github/fetch` 在 Mock 环境下能返回 ingested_count
- `POST /api/v1/connectors/webhook/ingest` 能接收 payload 并写入 DB
- Webhook 签名验证失败时返回 403

---

### 任务 5: 测试覆盖

**创建文件** `tests/test_github_connector.py` 和 `tests/test_webhook_connector.py`

#### 5.1 GitHub 连接器测试（至少 8 个用例）

| 用例 | 类型 | 覆盖点 |
|------|------|--------|
| `test_init_default` | 单元 | 默认参数初始化，`source_id` 自动生成为 `github_owner_repo` |
| `test_init_custom_params` | 单元 | 自定义 labels / state / since 参数 |
| `test_fetch_issues_basic` | 集成 | Mock GitHub API 返回 2 个 Issue，验证生成 2 个 `RawFeedback` |
| `test_fetch_skips_pull_requests` | 集成 | Mock 返回含 `pull_request` 键的 item，验证被跳过 |
| `test_fetch_with_comments` | 集成 | Mock 返回 1 个 Issue + 2 个 Comment，验证生成 3 个 `RawFeedback` |
| `test_fetch_without_comments` | 集成 | `include_comments=False`，验证只返回 Issue 本体 |
| `test_dedupe_key_stability` | 单元 | 同一个 Issue 多次拉取，`dedupe_key` 相同 |
| `test_field_mapping` | 单元 | 验证 GitHub API 字段到 `RawFeedback` 的映射正确性 |

**Mock 方式**：使用 `unittest.mock.patch` Mock `httpx.AsyncClient.get` 返回预定义的 JSON 响应。

#### 5.2 Webhook 连接器测试（至少 6 个用例）

| 用例 | 类型 | 覆盖点 |
|------|------|--------|
| `test_verify_signature_valid` | 单元 | 正确签名 → `True` |
| `test_verify_signature_invalid` | 单元 | 错误签名 → `False` |
| `test_verify_signature_no_secret` | 单元 | 未配置密钥 → 始终 `True`（放行） |
| `test_parse_payload_standard` | 单元 | 标准 payload `{"text": "...", "author": "..."}` → `RawFeedback` |
| `test_parse_payload_alternative_keys` | 单元 | 替代键 `{"body": "...", "sender": "..."}` → 正确映射 |
| `test_parse_payload_missing_text` | 单元 | 缺少文本字段 → `ValueError` |

#### 5.3 连接器注册表测试（至少 4 个用例）

可添加在 `tests/test_connectors.py` 现有测试之后：

| 用例 | 类型 | 覆盖点 |
|------|------|--------|
| `test_list_connectors` | 单元 | 返回至少 4 种连接器名称 |
| `test_get_connector_github` | 单元 | `get_connector("github")` → `GitHubConnector` |
| `test_get_connector_unknown` | 单元 | `get_connector("unknown")` → `ValueError` |
| `test_register_custom` | 单元 | 注册自定义连接器后可被 get |

---

## ⚖️ 验收标准 (The Golden Rules)

完成开发后，你必须向用户提交**阶段交付报告**，报告中必须包含以下内容：

### 1. 代码规范验证
```bash
ruff check signal_miner/
```
必须输出 0 警告 / All clear。

### 2. 全量测试验证
```bash
pytest tests/ -v --ignore=tests/test_evidence_chain.py
```
必须全部通过。**注意：不能只跑新测试文件，必须跑全量套件。**

### 3. 变更文件清单
报告中必须列出所有新增和修改的文件路径，以及每个新增 API 端点的路径和方法。

### 4. 新增依赖声明
如果引入了新的第三方依赖（如 `httpx`），必须确认它已在 [pyproject.toml](./pyproject.toml) 的 `dependencies` 中声明。如已存在则标注"已有"。

---

## 📂 文件清单速查

| 操作 | 文件路径 |
|------|----------|
| [NEW] | `signal_miner/connectors/github_connector.py` |
| [NEW] | `signal_miner/connectors/webhook_connector.py` |
| [MODIFY] | `signal_miner/connectors/__init__.py` |
| [MODIFY] | `signal_miner/settings.py` |
| [MODIFY] | `.env.example` |
| [NEW] | `signal_miner/routes/connectors.py` |
| [MODIFY] | `signal_miner/main.py` |
| [NEW] | `tests/test_github_connector.py` |
| [NEW] | `tests/test_webhook_connector.py` |
| [MODIFY] | `tests/test_connectors.py`（追加注册表测试） |

---

**执行者，收到此指令后，请立即开始执行。完成后请按规范提交交付报告，包含上述全部验证输出。**
