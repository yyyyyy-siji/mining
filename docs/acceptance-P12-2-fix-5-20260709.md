# P12-2 fix-4 验收报告：运行态证据字段契约返修

验收日期：2026-07-09

结论：不通过，需要返修。

## 已通过项

1. `IngestRequest` 已新增 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload` 字段。
2. 路由层 `browser_screenshot` 缺少 `screenshot_path` 且缺少 `source_note` 时返回 422，未调用 runner。
3. 路由层完整 payload 可把 `screenshot_path`、`ocr_text`、`source_captured_at`、`raw_payload` 写入 `context`。
4. 聚焦测试通过：
   - `.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q`：9 passed
   - `.venv/bin/pytest tests/test_source_acquisition_contract.py -q`：34 passed

## 阻断问题

### P1-1：证据脚本仍然 ruff 失败

位置：

- `scripts/p12_2_api_evidence.py`

问题：

WorkBuddy 交付报告声称 `ruff 全范围: All checks passed!`，但本地复验失败。

证据：

```bash
.venv/bin/ruff check signal_miner/routes/feedback.py tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py
```

输出：

```text
I001 Import block is un-sorted or un-formatted
F541 f-string without any placeholders
Found 2 errors.
```

影响：

交付报告与代码事实不一致，且质量门禁未通过。

验收要求：

上述 ruff 命令必须退出码为 0。

### P1-2：证据脚本仍不是可靠机器门禁

位置：

- `scripts/p12_2_api_evidence.py`
- `docs/P12-2-screenshots/p12-2-api-evidence.json`

问题：

脚本输出仍是分散 `verdict`，缺少顶层 `finalDecision`、`passed`、`model_fields_present`、路由级关键断言聚合；脚本没有把关键字段失败绑定到进程退出码。

证据：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("docs/P12-2-screenshots/p12-2-api-evidence.json").read_text())
print("has_finalDecision", "finalDecision" in data)
print("has_model_fields_present", "model_fields_present" in data)
PY
```

输出：

```text
has_finalDecision False
has_model_fields_present False
```

影响：

这是重复出现的高频问题：验证脚本可打印“5/5 通过”，但没有确定性机器门禁字段，后续仍可能假阳性。

验收要求：

证据脚本必须生成带顶层 `finalDecision: "PASS"`、`passed: true`、`model_fields_present`、`route_checks` 的 JSON，并在任一关键断言失败时非零退出。

### P1-3：`source_captured_at` 类型契约未与证据包模型对齐

位置：

- `signal_miner/routes/feedback.py`

问题：

`AcquisitionEvidence.source_captured_at` 是 `datetime | None`，但 `IngestRequest.source_captured_at` 当前是 `str | None`，因此无效时间字符串会被接受。

证据：

```bash
.venv/bin/python - <<'PY'
from signal_miner.routes.feedback import IngestRequest
req = IngestRequest(
    source_type="github",
    text="x",
    external_url="https://github.com/a/b/issues/1",
    source_captured_at="not-a-date",
)
print(req.source_captured_at)
PY
```

输出：

```text
not-a-date
```

影响：

API 响应模型契约未固化，后续入库的采集时间不可信。

验收要求：

`IngestRequest.source_captured_at` 必须改为 `datetime | None`，无效时间应被 Pydantic/FastAPI 拒绝；写入 `context` 时保存 ISO 字符串。

## 非阻断观察项

1. 本地缺少 `docs/deepseek-instruction-P12-2-fix-4.md` 与 `docs/acceptance-P12-2-fix-4-20260709.md`。本次验收按 WorkBuddy 实际代码改动和交付报告复验。
2. `scripts/p12_2_api_evidence.py` 的 browser_screenshot 负例主要验证 `AcquisitionEvidence.validate()`，下一轮应补路由 POST 负例，防止只在适配器层通过。

## 复验要求

必须全部通过：

```bash
.venv/bin/ruff check signal_miner/routes/feedback.py tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py
.venv/bin/python scripts/p12_2_api_evidence.py
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
.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q
.venv/bin/pytest tests/test_source_acquisition_contract.py -q
```

## 问题统计归类

- 验证脚本假阳性 / 机器门禁缺失：2 次重复。
- 交付报告与命令事实不一致：1 次。
- API 字段契约类型未固化：1 次。
