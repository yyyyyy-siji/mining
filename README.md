# SignalMiner ⛏️

> AI-powered agentic system that mines multi-source user signals and viral video trends into traceable, actionable product requirement assets.

---

## 📖 项目简介
`SignalMiner` 是一款智能化产品需求与爆款视频分析挖矿系统。它支持双模驱动：
1. **用户反馈挖矿 (Product Feedback Mining)**：将多渠道原始用户反馈（Support 工单、应用商店评论、用户访谈、问卷、GitHub Issues 等）自动解析为原子级信号，聚类并产出需求资产。
2. **AIGC 视频爆款挖掘 (AIGC Video Viral Mining)**：解析热门短视频平台内容，提炼出包括开头钩子（viral_hook）、内容模式（content_pattern）、平台算法（platform_algorithm）等爆款信号，分析转化为潜在的视频创作灵感与机会卡片。

整个系统完全保证**数据追溯链（Evidence Traceability Chain）**：所有生成的痛点、机会和需求，都可以精确回溯到最底层的原始反馈数据与原文引用。

---

## 🛠️ 系统架构与技术栈
*   **后端 API**: FastAPI (异步支持) + SQLAlchemy 2.0 (Async)
*   **Web 前端**: 内置原生暗色 SPA（挂载于 FastAPI 根路径，零构建开箱即用；另保留 `frontend/app.py`）
*   **LLM 与多模态适配层**: 模块化插件式设计，支持 DeepSeek（含 `deepseek-flash` 多模态）、OpenAI / 兼容接口、Google Gemini、通义千问、MiniMax，并提供 **「🎛️ 模型设置」** 可视化配置与一键连通性测试
*   **解耦 Embedding 语义向量**: 支持 **本机免费中文向量（`FastEmbed` + `BAAI/bge-small-zh-v1.5`）** 及 **云端 OpenAI 兼容向量（硅基流动 / 阿里云百炼 / 智谱 / OpenAI）**
*   **多平台普通 Chrome 直采**: 通过 Chrome Remote Debugging 复用已登录普通 Chrome 会话，支持 **小红书 / B 站（含自动 CC/AI 字幕逐字稿）/ 微博 / 知乎 / 抖音** 5 大平台受控并发同时采集 + 单平台失败重试
*   **全链路数据集版本管理**: 内置 `dataset_versions`，原始反馈、信号、主题、痛点、机会卡片、需求候选与管线运行按版本彻底隔离，支持跨版本独立复采、版本切换与汇总查看
*   **数据库**:
    *   **开发环境**: SQLite（内置，启动自动建表并平滑迁库）
    *   **生产环境**: PostgreSQL（支持 `pgvector`）
*   **流式进度**: SSE (Server-Sent Events) 实时推送每个阶段进度（含全局持久化运行状态条）

---

## ✨ 核心功能模块
```
Multi-Platform Collect (小红书/B站/微博/知乎/抖音 + 社区/GitHub/JSON)
        │  (按 Version 隔离入库)
        ▼
Raw Feedback (原始反馈) ──> Atomic Signals (原子信号) ──> Themes (语义向量聚类)
                                                               │
   PRD (需求文档) <── Requirements (需求候选) <── Opportunities (机会卡片) <── Pain Points (用户痛点)
```

1.  **🗂️ 版本管理**：按课题/轮次创建独立版本，不同版本间数据与资产完全隔离，侧边栏一键切换或跨版本汇总。
2.  **📥 统一采集与导入**：普通 Chrome 5 平台受控并发同时采（B 站自动提取 CC/AI 字幕逐字稿，单平台遇验证码/失败可单独重试）、预览区按平台筛选并一键导入目标版本；同时提供公开社区（Hacker News / V2EX）、GitHub Issues、Webhook、JSON 批量导入及手动补录折叠入口。
3.  **🎛️ 模型设置中心**：网页内可视化配置主大模型、多模态模型与本机/云端 Embedding 向量模型，支持一键连通性测试并持久化到本地 `.env`。
4.  **🔬 信号提取与真实向量聚类**：支持 **用户反馈挖矿 (`product_feedback`)** 与 **AIGC 视频爆款挖掘 (`aigc_video`)** 双视角提示词隔离，配合真实 Embedding 完成语义去重与层次聚类。
5.  **💡 机会卡片 → 📝 需求候选 → PRD 生成**：链式生成 JTBD 机会卡片（含严格证据准入评估）、含 Given/When/Then 验收标准的需求规格，以及可一键导出的 Markdown PRD，全程保留可点击原始证据溯源链。

---

## 🚀 快速启动指南

### 方式一：本地虚拟环境启动（推荐）

#### 1. 克隆与环境安装
确保已安装 Python 3.10+，并执行：
```bash
git clone https://github.com/yyyyyy-siji/mining.git
cd mining

python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装核心依赖（如需本机免费向量和普通 Chrome 直采，一并安装 fastembed 与 websockets）
pip install -e ".[dev,browser]"
pip install fastembed
```

#### 2. 配置模型密钥（任选其一）
- **方式 A（推荐）**：直接启动服务后，打开网页左侧 **「🎛️ 模型设置」** 页面填写 API Key 并点击保存与测试；
- **方式 B**：复制 `.env.example` 为 `.env` 后手动编辑：
```bash
cp .env.example .env
```

#### 3. 启动服务
```bash
uvicorn signal_miner.main:app --host 127.0.0.1 --port 8000
```
打开浏览器访问 `http://127.0.0.1:8000` 即可使用全部功能。

#### 4. 连接普通 Chrome 采集 5 大平台（可选）
1. 在已运行的普通 Chrome 打开 `chrome://inspect/#remote-debugging` 并开启远程调试；
2. 在 Chrome 中打开并登录小红书 / B 站 / 微博 / 知乎 / 抖音任意页面；
3. 回到 SignalMiner **「📥 采集与导入」** 点击 **「连接当前 Chrome」** 并在弹窗允许，即可勾选多平台同时采集。

---

### 方式二：Docker 容器一键部署（推荐生产部署）
项目已提供完整的容器化配置，包含主程序、PostgreSQL (带 pgvector 插件) 以及 Redis 服务。

```bash
# 一键编译并后台启动所有服务
docker-compose up --build -d

# 停止容器
docker-compose down
```
应用服务默认对外暴露端口为 `8000` (后端 API)，且会自动与配置的 DB、Redis 进行状态联通。

---

## 🗃️ 数据库迁移与版本控制 (Alembic)
如需修改数据库表结构，请遵循以下开发规范：
```bash
# 1. 自动生成迁移文件
alembic revision --autogenerate -m "describe_your_changes"

# 2. 应用迁移到本地数据库
alembic upgrade head

# 3. 回滚上一次迁移
alembic downgrade -1
```
*注：本项目迁移配置已针对 SQLite/PostgreSQL 进行了兼容适配（如在 SQLite 下自动使用 batch 模式执行 alter_table 操作）。*

---

## 🧪 自动化测试与代码审查
```bash
# 运行全部 90 项单元与集成测试
pytest

# 前端模块化源码构建与一致性校验（修改 frontend/src/*.js 后运行）
node scripts/build_frontend.mjs
node scripts/build_frontend.mjs --check

# 代码格式化与 Lint 检查 (使用 Ruff 进行极致的代码整洁度保障)
ruff check --fix
ruff format
```

---

## 🌐 上传至 GitHub 步骤指引
如需将该项目提交并同步至 GitHub，可参考以下步骤：

1.  **创建 GitHub 仓库**：在 GitHub 上新建一个仓库（不要勾选 Initialize this repository with README/.gitignore）。
2.  **本地 Git 初始化**：
    ```bash
    cd signal-miner
    git init
    git branch -M main
    ```
3.  **暂存并提交代码**：
    ```bash
    git add .
    git commit -m "feat: init SignalMiner with dual-mode feedback & AIGC video mining"
    ```
4.  **关联远程并推送**：
    ```bash
    git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
    git push -u origin main
    ```

---

## 📄 开源协议
本项目采用 **MIT License** 授权。独立运行的 MediaCrawler 组件采用其原有 **NON-COMMERCIAL LEARNING LICENSE 1.1**，不属于本项目MIT许可范围；见[第三方说明](docs/third-party-mediacrawler.md)。

国内平台本机登录态采集的安装、首次登录、限量预览与来源追溯，见[操作说明](docs/mediacrawler-local-runtime.md)。本机运行器与离线接入已完成，平台账号实采须单独验证。
