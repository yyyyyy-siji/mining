# P12-2 fix-5 验收报告：证据字段契约硬化返修

验收日期：2026-07-09

结论：不通过，需要返修。

## 已通过项

1. WorkBuddy 界面显示本轮任务完成，但本报告只按本地代码事实验收。
2. 静态检查通过：

```bash
.venv/bin/ruff check signal_miner/connectors signal_miner/models/feedback.py signal_miner/utils/source_platforms.py signal_miner/routes/feedback.py tests/test_source_acquisition_contract.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py scripts/p12_2_api_evidence.py
# exit 0, All checks passed!
```

3. 证据脚本当前可运行并输出顶层 PASS：

```bash
.venv/bin/python scripts/p12_2_api_evidence.py
# exit 0, finalDecision=PASS passed=True
```

4. 现有测试回归通过：

```bash
.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q
# 9 passed

.venv/bin/pytest tests/test_source_acquisition_contract.py -q
# 34 passed

.venv/bin/pytest tests/test_source_clickthrough_contract.py -q
# 22 passed

.venv/bin/pytest tests -q
# exit 0, 168 passed with warnings
```

5. 运行态无效时间戳行为正确：`source_captured_at="not-a-date"` 被 Pydantic/FastAPI 拒绝，路由返回 422，runner 未调用。

## 阻断问题

### P1-1：证据 JSON 的关键子项缺少 required `passed` 门禁

位置：

- `scripts/p12_2_api_evidence.py`
- `docs/P12-2-screenshots/p12-2-api-evidence.json`

问题：

`finalDecision` 顶层为 `PASS`，但 `route_checks.browser_screenshot_without_evidence` 只写入 `status` 和 `runner_called`，缺少本阶段要求的 `passed: true`。这会导致子断言没有被稳定纳入机器证据契约。

证据：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("docs/P12-2-screenshots/p12-2-api-evidence.json")
data = json.loads(p.read_text(encoding="utf-8"))
checks = {
    "top_level_pass": data.get("finalDecision") == "PASS" and data.get("passed") is True,
    "browser_screenshot_has_passed": data.get("route_checks", {}).get("browser_screenshot_without_evidence", {}).get("passed") is True,
    "invalid_source_captured_at_check_present": "invalid_source_captured_at" in data.get("route_checks", {}),
}
print(checks)
if not all(checks.values()):
    raise SystemExit(1)
PY
```

输出：

```text
{'top_level_pass': True, 'browser_screenshot_has_passed': False, 'invalid_source_captured_at_check_present': False}
```

影响：

本轮修复目标是“证据字段契约硬化”。顶层 PASS 不能替代每个关键路由断言的结构化 `passed` 字段，否则后续验收脚本仍可能出现假阳性。

验收要求：

`docs/P12-2-screenshots/p12-2-api-evidence.json` 必须包含：

```json
"browser_screenshot_without_evidence": {
  "status": 422,
  "runner_called": 0,
  "passed": true
}
```

并且 `finalDecision` / `passed` 必须由该字段参与聚合。

### P1-2：非法 `source_captured_at` 负例没有固化到测试和证据脚本

位置：

- `tests/test_feedback_ingest_source_contract.py`
- `scripts/p12_2_api_evidence.py`

问题：

运行态手工复核显示非法时间戳会被拒绝，但现有测试文件没有包含 `not-a-date` 负例；证据脚本也没有写出 `route_checks.invalid_source_captured_at`。

证据：

```bash
rg -n "not-a-date|invalid_source_captured_at" tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py
# no matches
```

影响：

当前正确行为没有被契约测试保护，后续把 `source_captured_at` 误改回字符串时，现有 168 个测试仍可能全绿。

验收要求：

补充路由级或模型级负例测试，至少断言：

- 请求 `source_captured_at="not-a-date"` 返回 422 或触发 `ValidationError`。
- runner 未调用。
- 证据 JSON 包含 `route_checks.invalid_source_captured_at`，其中 `status: 422`、`runner_called: 0`、`passed: true`。

### P1-3：`raw_payload` 类型没有按返修指令收敛为 `dict[str, Any] | None`

位置：

- `signal_miner/routes/feedback.py`

问题：

当前代码为：

```python
raw_payload: dict | None = Field(...)
```

但 fix-5 指令要求：

```python
raw_payload: dict[str, Any] | None
```

证据：

```bash
nl -ba signal_miner/routes/feedback.py | sed -n '124,130p'
```

关键输出：

```text
128 source_captured_at: datetime | None = Field(...)
129 raw_payload: dict | None = Field(...)
```

影响：

这不是当前运行态主路径故障，但属于明确交付契约未完成。该字段用于保存原始来源适配器响应，类型契约应避免裸 `dict` 漂移。

验收要求：

按指令改为 `dict[str, Any] | None`，并保证 ruff 通过。

### P1-4：交付报告未更新到 fix-5 事实，仍包含过期结论

位置：

- `docs/acceptance-P12-2-delivery-20260708.md`

问题：

交付报告没有记录 fix-5，本地检索仍显示过期类型描述 `source_captured_at: str | None`，与当前代码事实不一致。

证据：

```bash
rg -n "fix-5|source_captured_at: str|source_captured_at: datetime|raw_payload: dict" docs/acceptance-P12-2-delivery-20260708.md
```

输出包含：

```text
docs/acceptance-P12-2-delivery-20260708.md:21:| `IngestRequest` | 新增 `source_captured_at: str | None`、`raw_payload: dict | None` |
docs/acceptance-P12-2-delivery-20260708.md:81:| `IngestRequest` | 新增 `source_captured_at: str | None`、`raw_payload: dict | None` |
```

影响：

报告会误导后续阶段，以为字符串时间戳仍是已接受契约，也无法追踪 fix-5 实际命令与证据。

验收要求：

更新该交付报告，写明 fix-5 / fix-6 的真实命令、退出码、证据 JSON 路径和最终类型契约；不得保留 `source_captured_at: str | None` 作为当前事实。

## 非阻断观察项

1. 全量测试通过说明主回归面没有明显破坏。
2. `source_captured_at` 当前运行态已是 `datetime | None`，核心行为正确；阻断点集中在契约证据固化与报告同步。
3. 现有测试输出有 Starlette/httpx deprecation warning 和一个 AsyncMock RuntimeWarning，本轮不阻断 P12-2。

## 复验要求

返修后必须全部通过：

```bash
.venv/bin/ruff check signal_miner/routes/feedback.py tests/test_feedback_ingest_source_contract.py scripts/p12_2_api_evidence.py
.venv/bin/python scripts/p12_2_api_evidence.py
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
.venv/bin/pytest tests/test_feedback_ingest_source_contract.py -q
.venv/bin/pytest tests/test_source_acquisition_contract.py -q
.venv/bin/pytest tests/test_source_clickthrough_contract.py -q
.venv/bin/pytest tests -q
```

## 问题统计归类

- 验证脚本假阳性 / 缺少关键 `passed` 子门禁：重复出现。
- 交付报告与代码事实不一致：重复出现。
- 契约测试缺少负例：本轮新增。
