# SignalMiner Agent Skills Hub

欢迎使用 **SignalMiner** 智能代理技能库（Agent Skills Hub）。本目录由指挥官（Commander AI）精心设计，专门为您（执行者 AI / Executor AI）在本项目中的自主开发、质量保证及数据库操作提供所需的全部硬核技能与软性工程军规。

---

## 📂 技能库目录结构

- [mcp_config.json](./agent_skills/mcp_config.json): **MCP（Model Context Protocol）配置文件模板**。包含 SQLite 直连、文件检索、实时网页抓取等技能插槽，可直接导入到主流 IDE（如 Cursor, Windsurf, Claude Desktop 或 Cline 插件）中。
- [setup_skills.sh](./agent_skills/setup_skills.sh): **一键技能环境初始化脚本**。用于检测并安装 MCP 服务所需的系统依赖（Node.js, npm 等）。
- [clinerules.md](./agent_skills/clinerules.md): **执行者 AI 核心开发军规（软性 Skill）**。定义了代码静态检查（Ruff）、单元测试（Pytest）、异步 API 设计、数据库迁移等黄金准则。

---

## 🛠️ 如何激活并使用这些 Skills

### 1. 软性军规注入
请将 [clinerules.md](./agent_skills/clinerules.md) 的内容复制并重命名为项目根目录下的 **`.clinerules`** 或 **`.cursorrules`** 文件。
这样，执行者 AI 在启动时即可自动加载这些开发规范，并把它们作为最高行为准则。

### 2. 硬件工具链配置 (MCP 激活)
您可以根据您使用的 AI 开发客户端，将 [mcp_config.json](./agent_skills/mcp_config.json) 导入：

#### A. 如果使用 Cline (VS Code 插件)
把 `mcp_config.json` 的内容合并到以下路径的文件中：
`~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

#### B. 如果使用 Cursor IDE
在 Cursor 的 `Settings -> Features -> MCP` 中，依次添加以下服务：
1. **SQLite 技能:**
   - Name: `sqlite`
   - Type: `command`
   - Command: `npx -y @modelcontextprotocol/server-sqlite --db /path/to/signal-miner/signal_miner.db`
2. **Fetch 网页抓取技能:**
   - Name: `fetch`
   - Type: `command`
   - Command: `npx -y @modelcontextprotocol/server-fetch`
3. **Git 库管理技能:**
   - Name: `git`
   - Type: `command`
   - Command: `npx -y @modelcontextprotocol/server-git`

---

## 🎯 核心技能价值

1. **数据库洞察 (`sqlite`):** 允许执行者 AI 直连 SQLite，实时查询和校验 `signal_miner.db` 的 Schema 结构。在 Phase 3 新增 `prd_content` 字段时，能自动验证迁移是否无误。
2. **官方文档抓取 (`fetch`):** 执行者 AI 可实时拉取 FastAPI/SQLAlchemy 最新的 API 规范，100% 杜绝过时的写法。
3. **开发红线规范 (`clinerules`):** 强制执行者在完成任务前必须运行 `ruff check` 与 `pytest tests/`，实现自动化自我审计与自我纠正，确保交付的代码毫无瑕疵。
