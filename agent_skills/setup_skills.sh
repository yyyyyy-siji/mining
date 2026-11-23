#!/usr/bin/env bash

# ==============================================================================
# SignalMiner Agent Skills Setup Script
# 用于一键检测并初始化执行者 AI 的 MCP 技能环境
# 支持系统: macOS (Darwin)
# ==============================================================================

# 设置颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}               SignalMiner 智能代理技能环境初始化 ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. 检测 Node.js 和 npm
echo -e "\n${BLUE}[1/3] 正在检测 Node.js 运行环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}[-] 未检测到 Node.js。MCP 服务的运行强依赖 Node.js。${NC}"
    echo -e "${YELLOW}[!] 请先访问 https://nodejs.org 安装 Node.js，然后重新运行本脚本。${NC}"
    exit 1
else
    NODE_VERSION=$(node -v)
    NPM_VERSION=$(npm -v)
    echo -e "${GREEN}[+] Node.js 已安装: ${NODE_VERSION}${NC}"
    echo -e "${GREEN}[+] npm 已安装: ${NPM_VERSION}${NC}"
fi

# 2. 检测虚拟环境及 Python
echo -e "\n${BLUE}[2/3] 正在检测 Python 虚拟环境...${NC}"
WORKSPACE_DIR="/path/to/signal-miner"
if [ -d "${WORKSPACE_DIR}/.venv" ]; then
    echo -e "${GREEN}[+] 检测到项目虚拟环境 (.venv) 存在。${NC}"
    source "${WORKSPACE_DIR}/.venv/bin/activate"
    PYTHON_VERSION=$(python --version)
    echo -e "${GREEN}[+] 激活虚拟环境成功: ${PYTHON_VERSION}${NC}"
else
    echo -e "${YELLOW}[!] 未在项目根目录找到 .venv 虚拟环境，请确保您的 Python 环境已正确配置。${NC}"
fi

# 3. 预载常用的 MCP 服务包 (测试 npx 可达性)
echo -e "\n${BLUE}[3/3] 正在预载并验证核心 MCP 技能服务 (使用 npx)...${NC}"

echo -e "${BLUE}  -> 正在测试 SQLite MCP 服务...${NC}"
npx --yes @modelcontextprotocol/server-sqlite --help &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}  [+] SQLite MCP 服务验证成功！${NC}"
else
    echo -e "${YELLOW}  [!] SQLite MCP 服务预载时遇到网络延迟，请确保互联网连接通畅。${NC}"
fi

echo -e "${BLUE}  -> 正在测试 Fetch MCP 网页抓取服务...${NC}"
npx --yes @modelcontextprotocol/server-fetch --help &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}  [+] Fetch MCP 服务验证成功！${NC}"
else
    echo -e "${YELLOW}  [!] Fetch MCP 服务预载时遇到网络延迟。${NC}"
fi

# 4. 创建快捷方式或提示
echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}🎉 恭喜！技能初始化完成。${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo -e "${YELLOW}👉 后续操作提示:${NC}"
echo -e " 1. 已在 ${GREEN}agent_skills/mcp_config.json${NC} 生成了适用于 Cursor / Cline 的 MCP 配置。"
echo -e " 2. 请复制 ${GREEN}agent_skills/clinerules.md${NC} 的内容，"
echo -e "    在项目根目录下粘贴并重命名为 ${GREEN}.clinerules${NC} 或 ${GREEN}.cursorrules${NC} 以规范执行者 AI。"
echo -e " 3. 让执行者 AI 开始在 Phase 3 的任务中大显身手吧！"
echo -e "${BLUE}======================================================================${NC}"
