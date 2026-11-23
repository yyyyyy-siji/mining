# P10-1 交付报告：PRD 路由回归修复

验收日期：2026-06-25

结论：通过。

## 1. 根因

`test_post_generate_prd_success` 返回 500，错误详情：

```
PRD generation failed: Database not initialized. Call init_db() first.
```

**根因分析：**

| 调用层 | `get_session_factory` 来源 | 是否被 mock |
|---|---|---|
| `assets.py:generate_prd` (route validator) | `from signal_miner.db import get_session_factory` → `signal_miner.routes.assets.get_session_factory` | ✅ 已 patch |
| `prd_generator.py:generate_prd_for_requirement` | `from signal_miner.db import get_session_factory` → `signal_miner.pipeline.prd_generator.get_session_factory` | ❌ 未 patch |
| `audit.py:log_pipeline_event` | `from signal_miner.db import get_session_factory` → `signal_miner.services.audit.get_session_factory` | ❌ 未 patch |

`generate_prd_for_requirement` 和 `log_pipeline_event` 各自通过 `from signal_miner.db import get_session_factory` 获得了独立的模块级绑定，测试仅 patch 了 `signal_miner.routes.assets.get_session_factory`。进入 `generate_prd_for_requirement` 后调用的是未 patch 的原始函数，触发 `RuntimeError("Database not initialized.")`，被路由 handler 的 `except RuntimeError` 捕获后返回 500。

## 2. 修改内容

| 文件 | 修改 | 原因 |
|---|---|---|
| `tests/test_prd_routes.py:test_post_generate_prd_success` | 新增 patch `signal_miner.pipeline.prd_generator.generate_prd_for_requirement`（AsyncMock） | 测试目标是路由契约（200 + 响应字段），不是内部 generator pipeline。无需逐层 mock `get_session_factory` + `log_pipeline_event` |

业务代码零改动。

## 3. 验证结果

| 命令 | 结果 | 关键输出 |
|---|---|---|
| `.venv/bin/python -m pytest tests/test_prd_routes.py -q` | ✅ 6/6 通过 | 全部 PRD route 测试 |
| `ruff check signal_miner/routes/assets.py signal_miner/pipeline/prd_generator.py tests/test_prd_routes.py` | ✅ 通过 | All checks passed |
| `.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q` | ✅ 41/41 通过 | 6 PRD + 10 contract + 10 model/route + 9 GitHub + 6 evidence chain |

## 4. P9 回归确认

P9 全部 35 个测试通过（+ 本次修复的 6 个 PRD route 测试 = 41 passed）。数据来源点击链路、连接器契约、response model、成功路径测试均未受影响。

## 5. 遗留风险

- 无。
- 如需端到端测试 PRD 生成 pipeline（LLM + DB + audit log），应在 `test_prd_generator.py` 中补充集成测试。
