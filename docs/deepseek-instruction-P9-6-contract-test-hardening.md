# DeepSeek 执行指令：P9-6 契约测试硬化

## 任务目标

整理 P9 系列新增测试，减少脆弱的源码级字符串断言，优先使用 response model、路由级和 DOM/源码最小必要断言，提升后续维护稳定性。

## 背景 / 当前问题

P9-1 到 P9-5 已完成：

- 数据来源 URL 点击链路。
- 批量导入字段契约。
- 连接器响应字段契约。
- 连接器 response model。
- GitHub fetch 成功路径路由测试。

当前仍有一些测试通过读取源码字符串判断实现细节，例如：

- `tests/test_source_clickthrough_contract.py`

这类测试能防止快速回归，但对格式、注释、局部重构较敏感。P9-6 目标是保留有价值的契约保护，同时把能替换的源码级断言迁移为更稳定的行为级测试。

## 允许修改范围

- `tests/test_source_clickthrough_contract.py`
- `tests/test_connector_response_models.py`
- 如需要，可新增聚焦测试文件
- 不修改业务代码，除非测试暴露真实 bug

## 禁止修改范围

- 不要修改前端或后端业务实现。
- 不要真实启动外部服务。
- 不要访问真实 GitHub 网络。
- 不要做无关 ruff 清理。

## 实现要求

1. 审查 `tests/test_source_clickthrough_contract.py` 中源码级字符串断言。
2. 对以下类别保留或替换：
   - 前端静态 SPA 请求体形状可保留源码级最小断言，因为没有前端测试框架。
   - 后端 response model / route 字段应优先迁移到模型或 ASGI route 测试。
   - Streamlit HTML escaping helper 可保留最小源码断言，或抽出 helper 后做直接单元测试。
3. 删除重复或被 P9-4/P9-5 行为测试覆盖的源码级断言。
4. 保证测试语义仍覆盖：
   - `/feedback/batch` 前端发送数组并读取 `result.ingested`。
   - `/connectors/github/fetch` 返回 `ingested_count`。
   - `/connectors` 返回 `connectors`。
   - evidence trail 返回 `source_url`。
5. 不降低 P9 已覆盖的核心保护。

## 验收标准

```bash
ruff check tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py
.venv/bin/python -m pytest tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

通过条件：

- 测试全部通过。
- 删除或替换的源码级断言在交付报告中逐项说明。
- 没有业务代码改动。

## 交付报告模板

```markdown
# P9-6 交付报告：契约测试硬化

## 1. 调整摘要

| 测试/断言 | 处理方式 | 原因 |
|---|---|---|

## 2. 覆盖保持情况

| 契约 | 覆盖测试 |
|---|---|

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|

## 4. 业务代码改动确认

- 应为“无”。

## 5. 遗留风险

- 如无，写“无”。
```

