# DeepSeek 执行指令：P12-2 fix-5 证据字段契约硬化返修

## 任务目标

修复 P12-2 fix-4 复验失败项：脚本 lint、证据脚本机器门禁、`source_captured_at` 类型契约。

失败验收报告：

- `docs/acceptance-P12-2-fix-5-20260709.md`

## 背景 / 当前问题

当前代码功能路径部分可用，但仍存在三个阻断：

1. `scripts/p12_2_api_evidence.py` ruff 失败。
2. `docs/P12-2-screenshots/p12-2-api-evidence.json` 缺少顶层 `finalDecision` / `passed` / `model_fields_present` / `route_checks`，脚本仍不是可靠机器门禁。
3. `IngestRequest.source_captured_at` 是 `str | None`，无效时间字符串会被接受，未与 `AcquisitionEvidence.source_captured_at: datetime | None` 对齐。

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
- 连接器适配器文件
- 数据库模型 / migration
- PRD、P9/P10/P11 文档
- 与本返修无关的测试

## 实现要求

### 1. 固化 `source_captured_at` 类型契约

在 `signal_miner/routes/feedback.py` 中：

- 将 `IngestRequest.source_captured_at` 改为 `datetime | None`。
- 将 `raw_payload` 改为 `dict[str, Any] | None`，必要时从 `typing` 导入 `Any`。
- `_prepare_ingest_data()` 写入 `context["source_captured_at"]` 时必须保存 ISO 字符串，例如 `request.source_captured_at.isoformat()`。
- `raw_payload` 继续原样写入 `context["raw_payload"]`。

### 2. 补充契约测试

在 `tests/test_feedback_ingest_source_contract.py` 中补充或调整测试：

- 合法 `source_captured_at="2024-06-01T10:30:00Z"` 能被解析并写入 ISO 字符串。
- 非法 `source_captured_at="not-a-date"` 必须被 Pydantic/FastAPI 拒绝。
- `raw_payload` 仍能作为 dict 写入 context。
- 不传 `source_captured_at` / `raw_payload` 时不写入空键。

### 3. 重写 `scripts/p12_2_api_evidence.py` 为确定性机器门禁

要求：

- ruff clean。
- 任一关键断言失败时脚本退出码必须非 0。
- 生成 `docs/P12-2-screenshots/p12-2-api-evidence.json`，顶层结构必须至少包含：

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
    "full_metadata_persisted": {
      "status": 201,
      "passed": true
    }
  },
  "finalDecision": "PASS",
  "passed": true
}
```

可保留其他证据项，但 `finalDecision` 必须由所有关键布尔断言聚合得出，不能手写固定 PASS。

脚本至少验证：

- `IngestRequest.model_fields` 包含 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload`。
- 路由 POST `capture_method=browser_screenshot` 且无 `screenshot_path` / `source_note` 返回 422，runner 未调用。
- 路由 POST 带 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload` 返回 201，并且 runner 收到的 `context` 完整包含四个字段。
- 非法 `source_captured_at` 请求被拒绝。

### 4. 更新交付报告

更新 `docs/acceptance-P12-2-delivery-20260708.md`：

- 只记录真实通过的命令和退出码。
- 不得再写“ruff 全范围 0”，除非实际复跑通过。
- 写明 `source_captured_at` 类型已从字符串契约升级为 datetime 契约。

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

随后必须通过 JSON 门禁：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("docs/P12-2-screenshots/p12-2-api-evidence.json").read_text())
assert data["finalDecision"] == "PASS"
assert data["passed"] is True
assert data["model_fields_present"]["source_captured_at"] is True
assert data["model_fields_present"]["raw_payload"] is True
assert data["route_checks"]["browser_screenshot_without_evidence"]["status"] == 422
assert data["route_checks"]["browser_screenshot_without_evidence"]["runner_called"] == 0
assert data["route_checks"]["full_metadata_persisted"]["passed"] is True
PY
```

### 回归验证

必须通过：

```bash
.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q
.venv/bin/pytest tests/test_source_acquisition_contract.py -q
```

## 交付报告模板

完成后更新 `docs/acceptance-P12-2-delivery-20260708.md`，并在 WorkBuddy 回复中只写：

```text
P12-2 fix-5 completed.

Commands:
- <command>: exit <code>, <summary>

Artifacts:
- docs/acceptance-P12-2-delivery-20260708.md
- docs/P12-2-screenshots/p12-2-api-evidence.json
```
