# Phase 6: 生产化准备 (Production Readiness) — 执行指令

> **致执行者 (Executor AI)**:
> Phase 5（前端升级）已通过验收。这是 SignalMiner 的**最终阶段**。
> 完成后，整个项目将进入可交付状态。
>
> **核心原则：零破坏现有开发流程。** 所有变更必须是条件化/可选的——
> `DATABASE_URL=sqlite+aiosqlite:///./signal_miner.db` 必须继续正常工作。

---

## 🎯 阶段目标

根据 [SIGNALMINER_MASTER_REQUIREMENTS.md](./SIGNALMINER_MASTER_REQUIREMENTS.md#L55-L56) 定义：

> **阶段 6：生产化准备 (Production Readiness)**
> 目标：容器化（Docker），接入 PostgreSQL + pgvector 原生向量存储，添加简单的 API 鉴权。

拆解为 5 个任务：

| # | 任务 | 核心产出 |
|---|------|----------|
| 1 | Docker 容器化 | `Dockerfile` + `docker-compose.yml` + `.dockerignore` |
| 2 | PostgreSQL + pgvector | DB 层条件化驱动 + Vector 列 + Alembic 迁移 |
| 3 | API 鉴权中间件 | X-API-Key 头部验证 + FastAPI Depends |
| 4 | 生产设置加固 | 环境感知配置 + CORS + 日志 |
| 5 | 测试套件 | 鉴权 + DB + Docker 验证 |

---

## 📐 技术架构约束

### 零破坏原则
- `DATABASE_URL=sqlite+aiosqlite:///./signal_miner.db` **必须继续工作**
- `API_KEY` 未设置时 → 无鉴权（开发模式）
- 不使用 Docker 时 → 直接 `python -m signal_miner.main` 正常启动
- 现有测试套件必须全部通过

### 已有依赖（无需新增核心依赖）
- `asyncpg>=0.29.0` — 已在 `[project.optional-dependencies] postgres` 中
- `pgvector>=0.3.0` — 已在 `[project.optional-dependencies] postgres` 中
- `sqlalchemy[asyncio]>=2.0.0` — 已有
- `structlog` — 已有

---

## 📝 任务清单

### 任务 1: Docker 容器化

#### 1.1 创建 `Dockerfile`

**新建文件** `Dockerfile`（项目根目录 `signal-miner/`）

```dockerfile
# ---- Build Stage ----
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[postgres]"

# ---- Runtime Stage ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY signal_miner/ signal_miner/
COPY frontend/ frontend/
COPY alembic/ alembic/
COPY alembic.ini .

# Environment defaults
ENV ENVIRONMENT=production
ENV DEBUG=false
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["python", "-m", "signal_miner.main", "--no-reload"]
```

> **注意**: 多阶段构建减小镜像体积。`.[postgres]` 安装含 `asyncpg` + `pgvector` 的完整依赖。

#### 1.2 创建 `.dockerignore`

**新建文件** `.dockerignore`

```
.venv/
__pycache__/
*.pyc
*.pyo
.git/
.env
*.db
.ruff_cache/
.mypy_cache/
.pytest_cache/
tests/
delivery-reports/
*.md
!README.md
```

#### 1.3 创建 `docker-compose.yml`

**新建文件** `docker-compose.yml`

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: signalminer
      POSTGRES_PASSWORD: signalminer_dev
      POSTGRES_DB: signalminer
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U signalminer"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://signalminer:signalminer_dev@db:5432/signalminer"
      REDIS_URL: "redis://redis:6379/0"
      STATE_BACKEND: "redis"
      ENVIRONMENT: "production"
      DEBUG: "false"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  pgdata:
```

#### 验收标准
- `docker compose build` 成功构建
- `docker compose up` 启动 3 个服务（db + redis + app）
- `curl http://localhost:8000/health` 返回 200

---

### 任务 2: PostgreSQL + pgvector 原生向量存储

#### 2.1 修改 `db/__init__.py` — 条件化驱动

**修改文件** [db/__init__.py](./signal_miner/db/__init__.py)

在 `init_db()` 函数中增加 PostgreSQL 驱动感知：

```python
async def init_db(database_url: str) -> None:
    global _engine, _session_factory

    connect_args = {}
    pool_kwargs = {}

    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False
    elif "postgresql" in database_url:
        # Enable pgvector extension on first connect
        pool_kwargs["pool_size"] = 5
        pool_kwargs["max_overflow"] = 10

    _engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        **pool_kwargs,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Create tables
    from signal_miner.db.models import Base
    async with _engine.begin() as conn:
        # Enable pgvector extension for PostgreSQL
        if "postgresql" in database_url:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_initialized", url=database_url.split("@")[-1])
```

> 需要新增 `from sqlalchemy import text` 导入。

#### 2.2 修改 `db/models.py` — 条件化 Vector 列

**修改文件** [db/models.py](./signal_miner/db/models.py)

在文件顶部增加 pgvector 条件导入：

```python
# Conditional pgvector support
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
```

修改 `SignalRow.embedding` 列（当前在 [L71](./signal_miner/db/models.py#L71)）：

```python
# 在 SignalRow 类中，替换 embedding 列定义
if HAS_PGVECTOR:
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
else:
    embedding: Mapped[list | None] = mapped_column(JSON)  # JSON fallback for SQLite
```

> **⚠️ 重要**: 不要用类外的 `if` 语句。使用类变量赋值方式，在类定义体内进行条件判断。一种可行的方式是定义一个辅助函数：

```python
def _embedding_column():
    """Return the appropriate column type for embeddings."""
    if HAS_PGVECTOR:
        return mapped_column(Vector(1536), nullable=True)
    return mapped_column(JSON)

# 在 SignalRow 中：
embedding: Mapped[list | None] = _embedding_column()
```

#### 2.3 Alembic 迁移脚本

**新建文件** `alembic/versions/xxxx_add_pgvector_support.py`

创建一个新的 Alembic 迁移，当检测到 PostgreSQL 后端时：
1. `CREATE EXTENSION IF NOT EXISTS vector`
2. 将 `feedback_signals.embedding` 列从 `JSON` 改为 `vector(1536)`

```python
"""Add pgvector support for PostgreSQL backend.

Revision ID: <auto-generate>
"""

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Convert embedding column from JSON to vector
        op.execute(
            "ALTER TABLE feedback_signals "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)"
        )

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE feedback_signals "
            "ALTER COLUMN embedding TYPE json "
            "USING embedding::text::json"
        )
```

#### 验收标准
- SQLite 模式：`embedding` 列为 JSON 类型，正常工作
- PostgreSQL 模式：`embedding` 列为 `vector(1536)` 类型
- 迁移脚本在两种后端上均不报错

---

### 任务 3: API 鉴权中间件

#### 3.1 创建鉴权模块

**新建文件** `signal_miner/auth.py`

```python
"""Simple API key authentication.

When API_KEY is configured in settings, all API routes require
the X-API-Key header to match. Health and static routes are exempt.
"""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from signal_miner.settings import AppSettings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key_dependency(settings: AppSettings):
    """Create an API key verification dependency.

    If settings.api_key is empty, returns a no-op dependency
    (all requests pass through without authentication).
    """
    required_key = settings.api_key

    async def verify_api_key(
        api_key: str | None = Security(_api_key_header),
    ) -> str | None:
        if not required_key:
            return None  # No auth configured — pass through
        if api_key != required_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key.",
            )
        return api_key

    return verify_api_key
```

#### 3.2 修改 `settings.py`

**修改文件** [settings.py](./signal_miner/settings.py)

在 `# --- Connectors ---` 部分之前添加：

```python
    # --- Authentication ---
    api_key: str = ""  # Empty = no auth (development mode)
```

在 `.env.example` 中追加：

```
# --- Authentication ---
API_KEY=your_api_key_here
```

#### 3.3 修改 `main.py` — 注入鉴权依赖

**修改文件** [main.py](./signal_miner/main.py)

在 `create_app` 函数中，为所有 API 路由添加全局鉴权依赖：

```python
from signal_miner.auth import get_api_key_dependency

def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or AppSettings()
    api_key_dep = get_api_key_dependency(app_settings)

    # ... lifespan and FastAPI creation ...

    # Mount routes (with auth dependency on API routes)
    app.include_router(health_router, prefix="", tags=["health"])  # NO auth
    app.include_router(feedback_router, prefix="/api/v1", tags=["feedback"], dependencies=[Depends(api_key_dep)])
    app.include_router(pipeline_router, prefix="/api/v1", tags=["pipeline"], dependencies=[Depends(api_key_dep)])
    app.include_router(signals_router, prefix="/api/v1", tags=["signals"], dependencies=[Depends(api_key_dep)])
    app.include_router(assets_router, prefix="/api/v1", tags=["assets"], dependencies=[Depends(api_key_dep)])
    app.include_router(connectors_router, prefix="/api/v1", tags=["connectors"], dependencies=[Depends(api_key_dep)])
```

需要添加 `from fastapi import Depends` 导入。

> **关键设计决策**:
> - `/health` 路由 **不需要** 鉴权（容器健康检查需要无密访问）
> - `/`（静态文件）**不需要** 鉴权（前端页面需要公开访问）
> - 所有 `/api/v1/*` 路由在 `API_KEY` 配置后需要鉴权

#### 3.4 修改前端 API 客户端

**修改文件** [frontend/static/app.js](./frontend/static/app.js)

在 `apiGet` 和 `apiPost` 函数中增加可选的 API Key 头部：

```javascript
// 在文件顶部增加：
function getApiKey() {
  return localStorage.getItem('signalminer_api_key') || '';
}

function getAuthHeaders() {
  const key = getApiKey();
  return key ? { 'X-API-Key': key } : {};
}

// 修改 apiGet：
async function apiGet(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = `${API_BASE}${path}${qs ? '?' + qs : ''}`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

// 修改 apiPost：
async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  // ... rest unchanged
}

// API Key 设置弹窗
function promptApiKey() {
  const key = prompt('请输入 API Key:');
  if (key) {
    localStorage.setItem('signalminer_api_key', key);
    showToast('API Key 已保存，正在刷新…', 'info');
    setTimeout(() => location.reload(), 500);
  }
}
```

#### 验收标准
- `API_KEY` 未设置 → 所有 API 正常访问（开发模式）
- `API_KEY=mykey` 已设置 → 无头部请求返回 401 → 带 `X-API-Key: mykey` 头部正常访问
- `/health` 始终无需鉴权
- 前端检测到 401 后弹出 API Key 输入框

---

### 任务 4: 生产设置加固

#### 4.1 环境感知配置

**修改文件** [settings.py](./signal_miner/settings.py)

当 `ENVIRONMENT=production` 时的推荐默认值：

```python
    # --- Application ---
    environment: str = "development"
    debug: bool = True  # auto-set to False when environment=production
```

**修改文件** [runtime.py](./signal_miner/runtime.py)

在 `build_runtime` 中增加生产模式警告：

```python
async def build_runtime(settings: AppSettings) -> AppRuntime:
    # Production mode overrides
    if settings.environment == "production":
        if settings.debug:
            logger.warning("production_debug_override", msg="Forcing debug=False in production")
            settings.debug = False
        if "sqlite" in settings.database_url:
            logger.warning("production_sqlite_warning", msg="SQLite is not recommended for production")
        if not settings.api_key:
            logger.warning("production_no_auth", msg="No API_KEY set — API is unauthenticated")

    _configure_logging(settings.debug)
    # ... rest unchanged
```

---

### 任务 5: 测试套件

#### 5.1 鉴权测试

**新建文件** `tests/test_auth.py`

| 用例 | 覆盖点 |
|------|--------|
| `test_no_api_key_configured_allows_all` | `API_KEY=""` → 无头部也能访问 |
| `test_api_key_required_missing_header` | `API_KEY="secret"` → 无头部 → 401 |
| `test_api_key_required_wrong_key` | `API_KEY="secret"` → 错误 key → 401 |
| `test_api_key_required_correct_key` | `API_KEY="secret"` → 正确 key → 200 |
| `test_health_no_auth_required` | `/health` 始终无需鉴权 |

> 使用 `from signal_miner.auth import get_api_key_dependency` 进行单元测试，
> 不需要启动完整的 FastAPI 应用。

#### 5.2 数据库驱动测试

**新建文件** `tests/test_db_config.py`

| 用例 | 覆盖点 |
|------|--------|
| `test_sqlite_connect_args` | SQLite URL → `check_same_thread=False` |
| `test_postgresql_pool_config` | PostgreSQL URL → `pool_size` + `max_overflow` 设置 |
| `test_pgvector_import_flag` | `HAS_PGVECTOR` 标志正确反映导入状态 |

#### 5.3 Docker 构建验证

在交付报告中提供 `docker compose build` 的成功输出日志（或因无 Docker 环境的详细说明）。

---

## ⚖️ 验收标准 (The Golden Rules)

### 1. 代码规范
```bash
ruff check signal_miner/
```
必须 0 警告。

### 2. 全量测试
```bash
pytest tests/ -v
```
必须全部通过。**不能破坏任何现有功能。**

### 3. 向后兼容性验证
在报告中必须说明：
- 不设置任何新环境变量时，应用正常启动并可访问
- SQLite 模式下所有页面正常工作

### 4. 变更文件清单
完整列出所有新建和修改的文件。

---

## 📂 文件清单速查

| 操作 | 文件路径 |
|------|----------|
| [NEW] | `Dockerfile` |
| [NEW] | `.dockerignore` |
| [NEW] | `docker-compose.yml` |
| [NEW] | `signal_miner/auth.py` |
| [NEW] | `alembic/versions/xxxx_add_pgvector_support.py` |
| [NEW] | `tests/test_auth.py` |
| [NEW] | `tests/test_db_config.py` |
| [MODIFY] | `signal_miner/db/__init__.py` — PostgreSQL 连接池 + pgvector 扩展 |
| [MODIFY] | `signal_miner/db/models.py` — 条件化 Vector 列 |
| [MODIFY] | `signal_miner/settings.py` — `api_key` 字段 |
| [MODIFY] | `signal_miner/main.py` — 鉴权依赖注入 |
| [MODIFY] | `signal_miner/runtime.py` — 生产模式警告 |
| [MODIFY] | `frontend/static/app.js` — API Key 头部 + 401 处理 |
| [MODIFY] | `.env.example` — `API_KEY` 示例 |

---

## ⚠️ 特别注意

1. **Vector 列的条件化是关键难点** — 必须在 SQLite 和 PostgreSQL 两种后端上都能正常建表
2. **鉴权是可选的** — `API_KEY=""` 时必须完全透明通过
3. **Dockerfile 中使用 `.[postgres]`** — 安装完整依赖含 pgvector
4. **健康检查路由不能加鉴权** — Docker HEALTHCHECK 需要无密访问
5. **Alembic 迁移必须是方言感知的** — 只在 PostgreSQL 上执行 `CREATE EXTENSION vector`

---

**执行者，这是最终阶段。完成后请提交交付报告。交由我进行最终验收，验收通过后 SignalMiner 项目将正式关闭。**
