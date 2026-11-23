# SignalMiner - 执行者 AI 开发规范与核心 Skill (Golden Rules)

本规则是 **SignalMiner** 代码仓库中所有智能代理（Executor AI）在执行开发任务时的最高行为准则。你作为执行者，在开始任何开发任务（包含但不限于 Phase 3 路由、模型和管道设计）前，必须阅读并深刻理解这些规范。

---

## 🛑 质量红线与自我审计 (Golden Rules)

每次在向指挥官（Commander AI）及用户提交任务成果前，你**必须在本地完成自我审计**。绝不允许将未经验证的代码或报错提交给人类用户！

### 1. 代码质量与格式红线
*   你编写的每一行 Python 代码，都必须完全符合 PEP8 规范。
-   **自检命令:** 必须在终端运行 `ruff check signal_miner/`。
-   **合格标准:** 输出结果必须为 **`0 Errors, 0 Warnings`**。如果存在 Lint 报错，必须自行调用 Ruff 修复或手动调整，直到没有警告为止。

### 2. 单元测试与功能验证红线
*   你编写的每个路由、每个数据流管道，都必须有对应的单元测试用例。
-   **自检命令:** 必须在终端运行 `pytest tests/`。
-   **合格标准:** 输出结果必须为 **`100% Passed`**（通过率 100%）。如果有任何用例失败，必须立即根据 Traceback 堆栈信息进行自我修复。

---

## 🛠️ 项目特有技术栈规范

### 1. 异步 API 与 FastAPI 路由
*   SignalMiner 是基于 FastAPI 构建的高并发异步系统。
*   所有的路由函数（位于 `signal_miner/routes/` 目录）必须全部声明为异步：`async def route_handler(...)`。
*   必须使用统一的 `FastAPI.HTTPException` 进行异常捕获与抛出，严禁把未处理的内部异常暴露给前端。

### 2. SQLAlchemy 2.0 ORM 声明规范
*   数据库模块使用的是新版 SQLAlchemy 2.0。声明字段时，**严禁混用 1.x 版本的旧式声明方式**。
-   **声明标准:** 统一采用 `Mapped` 和 `mapped_column`。
-   **实例（例如 Phase 3 新增 `prd_content` 字段）:**
    ```python
    from typing import Optional
    from sqlalchemy import Text
    from sqlalchemy.orm import Mapped, mapped_column
    
    # 正确示范：
    prd_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="由大模型生成的结构化PRD内容")
    ```

### 3. SSE (Server-Sent Events) 与实时日志
*   系统使用 SSE 实现进度条的实时推送。
*   在设计提取器和聚类器组件时，如果包含了耗时的大模型推理（LLM Inference），必须调用 `yield` 通过进度生成器推送结构化事件。
*   发送给前端的 SSE 消息必须使用规范的 JSON 格式：`{"status": "processing", "progress": 40, "message": "正在解析信号..."}`。

---

## 📤 任务交付模板 (Delivery Report Template)

在每个阶段完成开发并提交给用户时，你必须按照以下格式提交**“交付报告”**，证明你已符合指挥官的全部验收标准：

```markdown
# 🚀 Phase [X] 任务交付报告

## 1. 变更摘要
- [NEW] 创建了 `file_name.py`，用于实现 [功能简介]
- [MODIFY] 更改了 `routes/xxx.py`，新增了 [接口名称]
- [MIGRATION] 生成了 Alembic 迁移脚本 `xxxx_add_column.py`

## 2. 静态自检结果 (Ruff Audit)
> 运行命令: `ruff check signal_miner/`
[在此粘贴 Ruff 无警告通过的终端输出日志]

## 3. 测试运行结果 (Pytest Verification)
> 运行命令: `pytest tests/`
[在此粘贴 Pytest 100% 成功通过的终端输出日志]

## 4. 接口手动校验结果 (Manual Verify Log)
[在此贴出使用 Curl/Swagger API 测试接口的请求与响应数据截图或日志，尤其是 SSE 事件流]
```
