# DeepSeek 执行指令：P12-2 fix-6 证据字段契约收口返修

## 任务目标

只修复 P12-2 fix-5 复验中的契约证据缺口，不做功能重写。

失败验收报告：

- `docs/acceptance-P12-2-fix-6-20260709.md`

## 背景 / 当前问题

本地复验确认主功能和全量测试基本通过，但还有四个阻断：

1. `docs/P12-2-screenshots/p12-2-api-evidence.json` 中 `route_checks.browser_screenshot_without_evidence` 缺少 `passed: true`。
2. 无效 `source_captured_at="not-a-date"` 虽然运行态会 422，但没有固化到测试与证据 JSON。
3. `IngestRequest.raw_payload` 仍是裸 `dict | None`，未按指令收敛为 `dict[str, Any] | None`。
4. `docs/acceptance-P12-2-delivery-20260708.md` 未更新 fix-5/fix-6 事实，仍有 `source_captured_at: str | None` 的过期描述。

## 允许修改范围

只允许修改：

- `signal_miner/routes/feedback.py`
- `tests/test_feedback_ingest_source_contract.py`
- `scripts/p12_2_api_evidence.py`
- `docs/P12-2-screenshots/p12-2-api-evidence.json`
- `docs/acceptance-P12-2-delivery-20260708.md`

## 禁止修改范围

禁止修改：

- 前端文件
- 连接器适配器实现
- 数据库模型 / migration
- P9/P10/P11 文档
- 与本返修无关的测试
- 路由成功路径以外的业务逻辑重写

## 实现要求

### 1. 收敛 `raw_payload` 类型

在 `signal_miner/routes/feedback.py` 中：

- 将 `raw_payload` 改为 `dict[str, Any] | None`。
- 如需导入 `Any`，保持 ruff clean。
- 不改变 `source_captured_at: datetime | None` 当前正确契约。
- `_prepare_ingest_data()` 继续把 `source_captured_at` 用 `.isoformat()` 写入 context，把 `raw_payload` 原样写入 context。

### 2. 补齐非法时间戳负例测试

在 `tests/test_feedback_ingest_source_contract.py` 中补充测试，必须覆盖：

- `source_captured_at="not-a-date"` 被拒绝。
- 如果用路由级 TestClient，断言响应为 422 且 runner 未调用。
- 如果用 Pydantic 模型级测试，断言抛出 `ValidationError` 且错误定位包含 `source_captured_at`。

建议优先使用路由级 TestClient，因为本阶段验收关注 API 契约。

### 3. 加强 `scripts/p12_2_api_evidence.py`

脚本必须：

- 保持 ruff clean。
- 生成 `docs/P12-2-screenshots/p12-2-api-evidence.json`。
- 任一关键断言失败时进程退出码非 0。
- `finalDecision` 和 `passed` 必须由所有关键布尔断言聚合得出，不能固定写 PASS。

证据 JSON 至少必须包含：

```json
{
  "model_fields_present": {
    "screenshot_path": true,
    "ocr_text": true,
    "source_captured_at": true,
    "raw_payload": true
  },
  "route_checks": {
    "browser_screenshot_without_evidence": {
      "status": 422,
      "runner_called": 0,
      "passed": true
    },
    "invalid_source_captured_at": {
      "status": 422,
      "runner_called": 0,
      "passed": true
    },
    "full_metadata_persisted": {
      "status": 201,
      "passed": true
    }
  },
  "finalDecision": "PASS",
  "passed": true
}
```

### 4. 更新交付报告

更新 `docs/acceptance-P12-2-delivery-20260708.md`：

- 增加 fix-6 小节。
- 记录真实执行命令、退出码和摘要。
- 删除或更正当前事实中的 `source_captured_at: str | None`。
- 写明当前契约为 `source_captured_at: datetime | None`、`raw_payload: dict[str, Any] | None`。
- 写明证据 JSON 路径：`docs/P12-2-screenshots/p12-2-api-evidence.json`。

## 验收标准

### 语法 / 静态检查

必须通过：

```bash
.venv/bin/ruff check signal_miner/routes/feedback.py tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py
```

### 功能验证

必须通过：

```bash
.venv/bin/python scripts/p12_2_api_evidence.py
```

随后必须通过严格 JSON 门禁：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("docs/P12-2-screenshots/p12-2-api-evidence.json").read_text(encoding="utf-8"))
assert data["finalDecision"] == "PASS"
assert data["passed"] is True
assert data["model_fields_present"]["source_captured_at"] is True
assert data["model_fields_present"]["raw_payload"] is True
assert data["route_checks"]["browser_screenshot_without_evidence"]["status"] == 422
assert data["route_checks"]["browser_screenshot_without_evidence"]["runner_called"] == 0
assert data["route_checks"]["browser_screenshot_without_evidence"]["passed"] is True
assert data["route_checks"]["invalid_source_captured_at"]["status"] == 422
assert data["route_checks"]["invalid_source_captured_at"]["runner_called"] == 0
assert data["route_checks"]["invalid_source_captured_at"]["passed"] is True
assert data["route_checks"]["full_metadata_persisted"]["passed"] is True
PY
```

### 回归验证

必须通过：

```bash
.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q
.venv/bin/pytest tests/test_source_acquisition_contract.py -q
.venv/bin/pytest tests/test_source_clickthrough_contract.py -q
```

如时间允许，补跑：

```bash
.venv/bin/pytest tests -q
```

### 交付前质量门禁

交付前必须自查：

- `rg -n "source_captured_at: str|raw_payload: dict \\| None" docs/acceptance-P12-2-delivery-20260708.md signal_miner/routes/feedback.py` 不应再命中过期当前事实。
- `rg -n "not-a-date|invalid_source_captured_at" tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py` 必须命中。
- 交付报告中的命令结果必须来自实际运行，不能只引用旧报告。

## 交付报告模板

完成后更新 `docs/acceptance-P12-2-delivery-20260708.md`，并在 WorkBuddy 回复中只写：

```text
P12-2 fix-6 completed.

Changed:
- <file>: <summary>

Commands:
- <command>: exit <code>, <summary>

Artifacts:
- docs/acceptance-P12-2-delivery-20260708.md
- docs/P12-2-screenshots/p12-2-api-evidence.json

Remaining blockers:
- None, or list exact blocker.
```
