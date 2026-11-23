# Phase 5: 前端升级与交互体验 (Frontend Upgrade) — 执行指令

> **致执行者 (Executor AI)**:
> Phase 4（多源连接器）已一次通过验收。欢迎进入 Phase 5。
> **你的边界：仅修改 `frontend/` 目录下的前端文件和 `main.py` 中的静态文件挂载，不得修改任何后端业务逻辑。**

---

## 🎯 阶段目标

将当前的 Streamlit 轮询式 UI（`frontend/app.py`，314 行）替换为一个**现代化的纯前端单页应用（SPA）**，具备：

1. **SSE 实时进度流** — 用原生 `EventSource` API 消费 `/api/v1/pipeline/stream/{run_id}`
2. **完整的证据链可视化** — 用户可交互追溯 Requirement → Opportunity → PainPoint → Theme → Signal → RawFeedback
3. **专业级视觉体验** — 暗色主题、渐变动画、glassmorphism、响应式布局

---

## 📐 技术架构约束

### 前端技术栈（严格遵守）
- **零构建工具**：纯 HTML + CSS + Vanilla JavaScript，无 React/Vue/Vite/Webpack
- **文件结构**：
  ```
  frontend/
  ├── app.py           ← 保留不删除（旧版备份）
  └── static/
      ├── index.html   ← SPA 入口
      ├── style.css    ← 完整设计系统
      └── app.js       ← 路由 + API + 组件 + SSE
  ```
- **字体**：通过 CDN 引入 `Inter`（Google Fonts）
- **图标**：使用 Unicode Emoji（与原 Streamlit 一致）

### 后端对接（只读，不得修改）
- **API Base**: `http://localhost:8000/api/v1`
- **SSE 端点**: `GET /api/v1/pipeline/stream/{run_id}`（已存在，见 [pipeline.py#L112-131](./signal_miner/routes/pipeline.py#L112-L131)）
- **所有现有 API 端点不做修改**

---

## 📝 任务清单

### 任务 1: FastAPI 静态文件挂载

**修改文件** [main.py](./signal_miner/main.py)

在 `create_app` 函数的路由注册之后、`return app` 之前，添加：

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

> **⚠️ 重要**: `app.mount("/", ...)` 必须在所有 `include_router` 之后，否则会拦截 API 路由。`html=True` 使 `/` 自动返回 `index.html`。

#### 验收标准
- 访问 `http://localhost:8000/` 返回 `index.html` 页面
- 访问 `http://localhost:8000/api/v1/connectors` 仍正常返回 JSON

---

### 任务 2: 设计系统 (style.css)

**创建文件** `frontend/static/style.css`

#### 2.1 CSS 变量体系（暗色主题）
```css
:root {
  /* 色板 */
  --bg-primary: #0f0f1a;         /* 主背景 */
  --bg-secondary: #1a1a2e;       /* 卡片/面板背景 */
  --bg-tertiary: #16213e;        /* 悬停/选中态 */
  --bg-glass: rgba(26, 26, 46, 0.7); /* 毛玻璃效果 */
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent-primary: #6366f1;     /* 靛蓝紫 */
  --accent-secondary: #8b5cf6;   /* 紫色 */
  --accent-gradient: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --info: #3b82f6;

  /* 间距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 16px;

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-glow: 0 0 20px rgba(99, 102, 241, 0.15);

  /* 字体 */
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* 过渡 */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
}
```

#### 2.2 核心组件样式
你必须实现以下 CSS 组件类：

| 类名 | 用途 | 关键特性 |
|------|------|----------|
| `.sidebar` | 左侧导航栏 | 固定宽度 260px，`backdrop-filter: blur(10px)` |
| `.sidebar-nav-item` | 导航项 | 悬停渐变高亮，活跃态左边框 accent |
| `.content-area` | 主内容区 | `margin-left: 260px`，滚动 |
| `.card` | 通用卡片 | `bg-secondary` + `radius-md` + `shadow-md` + 悬停升起动画 |
| `.card-expandable` | 可展开卡片 | 点击展开/收起，`max-height` 过渡动画 |
| `.badge` | 状态标签 | 圆角 pill，5 种颜色变体（success/warning/danger/info/default） |
| `.progress-bar` | 进度条 | 渐变填充 + 条纹动画 + 百分比文字 |
| `.table` | 数据表格 | 斑马纹，悬停行高亮 |
| `.form-input` / `.form-textarea` | 表单输入 | 暗色输入框，焦点发光 border |
| `.btn` / `.btn-primary` | 按钮 | 渐变背景，悬停发光，点击缩放 |
| `.toast` | 通知 toast | 右上角，滑入/滑出动画 |
| `.evidence-chain` | 证据链可视化 | 垂直时间线，连接线 + 节点 |
| `.skeleton` | 加载骨架屏 | 渐变闪烁动画占位 |
| `.empty-state` | 空状态 | 居中 emoji + 引导文案 |

#### 2.3 动画
```css
@keyframes shimmer { ... }       /* 骨架屏闪烁 */
@keyframes slideIn { ... }       /* Toast 滑入 */
@keyframes progressStripe { ... } /* 进度条条纹 */
@keyframes fadeIn { ... }        /* 页面切换淡入 */
@keyframes pulse { ... }         /* 活跃态脉冲 */
```

#### 2.4 响应式
- `≤768px`：Sidebar 隐藏为汉堡菜单
- 卡片网格：桌面 2-3 列，移动 1 列

---

### 任务 3: SPA 核心框架 (app.js)

**创建文件** `frontend/static/app.js`

#### 3.1 简易路由
```javascript
const ROUTES = {
  'import':     { title: '📥 导入反馈',  render: renderImportPage },
  'feedback':   { title: '📋 原始反馈',  render: renderFeedbackPage },
  'signals':    { title: '🔬 提取信号',  render: renderSignalsPage },
  'themes':     { title: '🏷️ 主题聚类', render: renderThemesPage },
  'painpoints': { title: '😣 痛点',     render: renderPainPointsPage },
  'opportunities': { title: '💡 机会卡片', render: renderOpportunitiesPage },
  'requirements':  { title: '📝 需求候选', render: renderRequirementsPage },
  'pipeline':   { title: '⚙️ 运行管线', render: renderPipelinePage },
  'connectors': { title: '🔌 数据源',   render: renderConnectorsPage },
};
```

使用 `location.hash` 路由（如 `#import`、`#pipeline`），监听 `hashchange` 事件切换页面。

#### 3.2 API 客户端
```javascript
const API_BASE = '/api/v1';

async function apiGet(path, params = {}) { ... }
async function apiPost(path, body) { ... }
```

错误处理：网络错误时显示 Toast 通知。

#### 3.3 组件工具函数
```javascript
function showToast(message, type = 'info') { ... }
function showSkeleton(container, count = 3) { ... }
function createBadge(text, variant = 'default') { ... }
function createExpandableCard(header, content) { ... }
```

---

### 任务 4: 页面视图实现

#### 4.1 📥 导入反馈 (`renderImportPage`)
- 手动输入表单：来源选择 + 用户名 + 标题 + 正文
- JSON 批量导入：文件拖拽区域
- 调用 `POST /feedback/ingest` 和 `POST /feedback/batch`

#### 4.2 📋 原始反馈 (`renderFeedbackPage`)
- 调用 `GET /feedback?limit=100`
- 可展开卡片列表，状态 emoji badge
- 显示 `text_preview` + 信号计数

#### 4.3 🔬 提取信号 (`renderSignalsPage`)
- 筛选：信号类型下拉 + 置信度滑块
- 调用 `GET /signals?signal_type=&min_confidence=`
- 每个信号显示 summary + evidence 引用 + implicit_need

#### 4.4 🏷️ 主题聚类 (`renderThemesPage`)
- 调用 `GET /themes`
- 卡片显示 name + description + signal_count + representative_quotes

#### 4.5 😣 痛点 (`renderPainPointsPage`)
- 调用 `GET /pain-points`
- 严重度 badge（🟢🟡🟠🔴）+ evidence_quotes

#### 4.6 💡 机会卡片 (`renderOpportunitiesPage`)
- 调用 `GET /opportunities`
- JTBD statement + assumptions + supporting_evidence 链
- 点击展开后调用 `GET /opportunities/{id}` 获取完整证据

#### 4.7 📝 需求候选 (`renderRequirementsPage`)
- 调用 `GET /requirements`
- 用户故事表格 + 验收标准清单 + 决策推理
- **🔑 关键功能：证据链可视化** — 见任务 6

#### 4.8 🔌 数据源 (`renderConnectorsPage`)（新增页面）
- 调用 `GET /connectors` 显示已注册连接器列表
- GitHub 拉取表单：repo + labels + state → `POST /connectors/github/fetch`
- Webhook 状态显示

---

### 任务 5: SSE 实时管线进度 (`renderPipelinePage`)

这是本阶段的**核心升级点**，替换 Streamlit 的 `time.sleep(2)` 轮询。

#### 5.1 流程
```
用户点击"启动管线"
  → POST /pipeline/run → 获取 run_id
  → new EventSource(`/api/v1/pipeline/stream/${runId}`)
  → onmessage: 更新进度条 + 状态文本 + 步骤日志
  → 收到 status=completed/failed → 关闭 EventSource
```

#### 5.2 UI 组件
```
┌─────────────────────────────────────────────┐
│  ⚙️ 运行管线                                │
│                                             │
│  [每条反馈信号数: ▰▰▰▰▱ 5]                   │
│  [最低置信度: ▰▰▰▱▱ 0.50]                    │
│                                             │
│  [🚀 启动管线]                               │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │  ████████████░░░░░░░░░ 62%              ││
│  │  ⏳ 正在聚类信号... (Step 5/7)            ││
│  └─────────────────────────────────────────┘│
│                                             │
│  步骤日志:                                    │
│  ✅ quality_gate — 3 items passed (0.5s)     │
│  ✅ extraction — 12 signals extracted (3.2s) │
│  ✅ embedding — 12 vectors generated (1.1s)  │
│  ✅ deduplication — 2 duplicates removed     │
│  ⏳ clustering — in progress...              │
│  ○ pain_point                                │
│  ○ opportunity                               │
│  ○ requirement                               │
└─────────────────────────────────────────────┘
```

#### 5.3 关键代码逻辑
```javascript
function startSSEStream(runId) {
  const source = new EventSource(`${API_BASE}/pipeline/stream/${runId}`);
  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgress(data.progress);
    updateStepLog(data.step, data.status, data.message, data.stats);
    if (data.status === 'completed' || data.status === 'failed') {
      source.close();
      showFinalResult(data);
    }
  };
  source.onerror = () => {
    source.close();
    showToast('SSE 连接中断', 'warning');
  };
}
```

#### 5.4 验收标准
- 启动管线后立即建立 SSE 连接
- 进度条实时更新（不再使用 `setInterval` 轮询）
- 每个 Pipeline 步骤完成后日志区域实时追加
- 管线完成后自动断开 SSE

---

### 任务 6: 证据链追溯可视化

在**需求候选页面**中，每个需求展开后显示完整的证据链追溯视图。

#### 6.1 垂直时间线布局
```
📝 需求: "优化 PDF 导出功能"
 │
 ├── 💡 机会: "文档导出能力提升"
 │    │
 │    ├── 😣 痛点: "PDF 导出频繁失败"
 │    │    │
 │    │    ├── 🏷️ 主题: "导出功能问题" (5 个信号)
 │    │    │    │
 │    │    │    ├── 🔬 信号: "PDF 导出按钮无响应" (置信度: 92%)
 │    │    │    │    └── 📥 原始反馈: "点了好几次导出都没反应..."
 │    │    │    │         └── 来源: bilibili · 用户: @test_user
 │    │    │    │
 │    │    │    └── 🔬 信号: "导出的 PDF 格式错乱" (置信度: 87%)
 │    │    │         └── 📥 原始反馈: "导出的内容排版全乱了..."
 │    │    │              └── 来源: manual · 用户: 匿名
```

#### 6.2 实现方式
- 调用 `GET /requirements/{req_id}/evidence-trail` 获取完整证据链
- 每个层级使用不同颜色的连接线和图标
- 引用原文使用 blockquote 样式高亮
- 置信度使用渐变色 badge（低→红，高→绿）
- 外部链接（`external_url`）可点击跳转

#### 6.3 验收标准
- 展开需求后可看到完整的 6 层追溯链
- 每层节点有对应的颜色和图标
- 信号置信度颜色可视化
- 用户原话引用清晰可辨

---

## ⚖️ 验收标准 (The Golden Rules)

### 1. 代码规范验证
```bash
ruff check signal_miner/
```
必须 0 警告。（仅检查 Python 文件，前端 HTML/CSS/JS 不需要 Ruff）

### 2. 全量测试验证
```bash
pytest tests/ -v --ignore=tests/test_evidence_chain.py
```
必须全部通过。**虽然本阶段主要是前端开发，但不能破坏后端。**

### 3. 功能验证（人工）
在交付报告中描述以下验证结果：
- `http://localhost:8000/` 是否正确返回 SPA 页面
- API 路由（如 `/api/v1/connectors`）是否仍正常工作
- 页面导航是否正常切换
- 至少截取 2-3 个关键页面的描述（说明布局和功能）

### 4. 变更文件清单
报告中必须列出所有新增和修改的文件。

---

## 📂 文件清单速查

| 操作 | 文件路径 |
|------|----------|
| [NEW] | `frontend/static/index.html` |
| [NEW] | `frontend/static/style.css` |
| [NEW] | `frontend/static/app.js` |
| [MODIFY] | `signal_miner/main.py`（添加 StaticFiles 挂载） |
| [KEEP] | `frontend/app.py`（保留不删除，作为旧版备份） |

---

## ⚠️ 特别注意

1. **不要删除 `frontend/app.py`** — 保留 Streamlit 版本作为备份
2. **`app.mount("/", ...)` 必须在所有 API 路由注册之后** — 否则会拦截 `/api/v1/*` 请求
3. **SSE 使用原生 `EventSource`** — 不要引入 polyfill 或第三方库
4. **所有文本使用中文** — 与原 Streamlit UI 保持一致
5. **CORS 已配置** — 由于前端和后端同源（同端口 8000），不需要额外 CORS 配置

---

**执行者，收到此指令后，请立即开始执行。完成后请按规范提交交付报告。**
