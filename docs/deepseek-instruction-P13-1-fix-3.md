# DeepSeek 执行指令：P13-1 fix-3 残留契约与浏览器证据收口

## 任务目标

修复 P13-1 fix-2 复验中的三个残留问题，使 P13-1 可以进入最终通过状态。

本轮是窄范围返修，不允许重写 embedding、runner、数据库迁移或 P13-2 校准逻辑。

## 背景 / 当前问题

Commander 独立复验确认：

- 真实 embedding 全失败熔断已修复。
- `metrics.json` 主链路已不再出现 fix-1 的顶层 passed / 内部 contradiction。
- `completed_with_skips` 主路径已打通。
- SPA 实际 DOM 已通过 Commander 浏览器验证。

但仍有三个 P1：

1. `frontend/app.py` 仍在两个 `/pipeline/run` payload 中发送 `confidence_threshold`。
2. `scripts/p13_1_browser_verify.js` 仍保留源码 fallback，并且失败路径不会可靠返回非零。
3. 交付报告声明与代码不一致。

## 允许修改范围

允许修改：

- `frontend/app.py`
- `scripts/p13_1_browser_verify.js`
- `scripts/p13_1_baseline_metrics.py`，仅限增加静态/证据门禁
- `tests/` 中与本轮残留问题直接相关的测试
- `docs/P13-1-evidence/`
- `docs/P13-1-screenshots/`
- 新的 fix-3 交付报告

## 禁止修改范围

禁止修改：

- `signal_miner/pipeline/embedding.py`
- `signal_miner/pipeline/runner.py`
- `signal_miner/routes/pipeline.py`
- `signal_miner/db/models.py`
- `alembic/versions/`
- P13-2 置信度校准实现
- 任何真实数据清洗、删除、重算逻辑

## 实现要求

### A. Streamlit 不再发送 legacy `confidence_threshold`

必须删除 `frontend/app.py` 中所有 `/pipeline/run` 请求 payload 里的 `confidence_threshold` 字段。

保留：

- 后端 `RunPipelineRequest.confidence_threshold` 兼容接收。
- OpenAPI deprecated 标记。
- `extract_signals(... confidence_threshold=...)` 的兼容参数。

不得做：

- 不得把字段改名后继续发送。
- 不得用隐藏变量、默认 payload merge、helper 函数继续带出该字段。

### B. 浏览器验证脚本必须是真实 DOM 门禁

修改 `scripts/p13_1_browser_verify.js`：

- 删除 `doSimpleVerify()` 源码 fallback。
- Playwright 不可用时输出 JSON：

```json
{
  "status": "BLOCKED",
  "reason": "Playwright not available",
  "passed": false
}
```

并 `process.exit(2)`。

- DOM 断言失败时输出 JSON，`passed=false`，并 `process.exit(1)`。
- DOM 断言全部通过时输出 JSON，`passed=true`，并 `process.exit(0)`。
- 不允许读取 `/app.js`、不允许检查源码 token 作为通过依据。

脚本至少验证：

1. `#signals` 页面：
   - body 可见文本包含 `未校准`。
   - body 可见文本包含 `最低模型自评分`。
   - body 可见文本不包含裸 `最低置信度`。
   - DOM 不存在 `#pipe-confidence`。
2. `#pipeline` 页面：
   - DOM 不存在 `#pipe-confidence`。
   - body 可见文本不包含裸 `最低置信度`。
   - body 可见文本包含主模型状态。
   - body 可见文本包含多模态状态。
   - profile selector 或页面可见文本包含 AIGC 视频 profile。

如果服务没有启动，脚本应非零退出，不得转为源码检查。

### C. 增加机器门禁，防止本问题复发

在现有证据脚本或新增测试中加入至少两个断言：

1. `frontend/app.py` 不应包含请求字段字符串 `"confidence_threshold":`。
2. `scripts/p13_1_browser_verify.js` 不应包含：
   - `doSimpleVerify`
   - `http.get('http://localhost:8000/app.js'`
   - `app.js`

这些断言必须参与交付前命令或 `metrics.json` 顶层 `passed`。

### D. 交付报告一致性

新的交付报告必须命名为：

`docs/acceptance-P13-1-delivery-fix-3-20260710.md`

报告不得声明浏览器通过，除非提供真实浏览器 DOM JSON 或 PNG。若执行环境没有 Playwright，必须写 BLOCKED，并说明 Commander 可另行复验。

报告必须列出：

- 修改文件。
- 每条命令的退出码。
- `frontend/app.py` 中 `confidence_threshold` 请求字段扫描结果。
- `scripts/p13_1_browser_verify.js` 源码 fallback 扫描结果。
- P13-1 核心回归命令结果。

## 验收标准

### 静态检查

必须通过：

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
node --check scripts/p13_1_browser_verify.js
git diff --check
```

### 残留问题专项验证

必须通过：

```bash
python3 - <<'PY'
from pathlib import Path

streamlit = Path("frontend/app.py").read_text()
browser = Path("scripts/p13_1_browser_verify.js").read_text()

assert '"confidence_threshold":' not in streamlit
assert "doSimpleVerify" not in browser
assert "app.js" not in browser
assert "http.get" not in browser

print("fix-3 static contract assertions passed")
PY
```

### P13-1 核心回归

必须通过：

```bash
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_1_baseline_metrics.py
.venv/bin/pytest -o addopts= -q tests/test_embedding_safety.py tests/test_confidence_contract.py tests/test_evidence_validation.py
.venv/bin/pytest -o addopts= -q
```

并满足：

```text
behavior_probe: Overall PASS
metrics: Overall PASS
focused tests: 正测试数 > 0
full tests: 正测试数 > 0
```

### 浏览器验证

如果 Playwright 可用，必须启动本地服务并运行：

```bash
APP_ENVIRONMENT=development API_PORT=8014 .venv/bin/python -m uvicorn signal_miner.main:app --host 127.0.0.1 --port 8014
node scripts/p13_1_browser_verify.js
```

期望：

```json
{
  "passed": true,
  "signals": {
    "hasUncalibrated": true,
    "hasModelSelfScoreFilter": true,
    "hasBareMinConfidence": false,
    "pipeConfidenceExists": false
  },
  "pipeline": {
    "hasPipeConfidence": false,
    "visibleConfidenceText": false,
    "hasPrimaryModel": true,
    "hasMultimodal": true,
    "hasAigcProfile": true
  }
}
```

如果 Playwright 不可用，脚本必须 exit 2，报告必须写 BLOCKED，不能写 PASS。

## 交付前质量门禁

交付前必须执行并记录：

```bash
.venv/bin/ruff check signal_miner tests scripts
node --check frontend/static/app.js
node --check scripts/p13_1_browser_verify.js
python3 - <<'PY'
from pathlib import Path
streamlit = Path("frontend/app.py").read_text()
browser = Path("scripts/p13_1_browser_verify.js").read_text()
assert '"confidence_threshold":' not in streamlit
assert "doSimpleVerify" not in browser
assert "app.js" not in browser
assert "http.get" not in browser
print("fix-3 static contract assertions passed")
PY
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_1_baseline_metrics.py
.venv/bin/pytest -o addopts= -q
git diff --check
```

任何一条失败都不得交付为 PASS。

## 交付报告模板

```markdown
# P13-1 fix-3 交付报告：残留契约与浏览器证据收口

交付日期：2026-07-10

## 结论

- 自评：PASS / BLOCKED / FAIL
- 若 BLOCKED，说明具体阻塞项

## 修改文件

| 文件 | 修改说明 |
| --- | --- |

## 修复项对应关系

| Commander 问题 | 修复证据 |
| --- | --- |
| Streamlit 仍发送 confidence_threshold | |
| browser verifier 源码 fallback | |
| 报告漂移 | |

## 命令结果

| 命令 | 退出码 | 摘要 |
| --- | ---: | --- |

## 机器证据

- metrics: `docs/P13-1-evidence/metrics.json`
- behavior probe: `docs/P13-1-evidence/behavior_probe.json`
- browser evidence: path 或 BLOCKED

## 未覆盖风险

```

## Commander 复验重点

Commander 下一轮将优先执行：

```bash
rg -n '"confidence_threshold":|doSimpleVerify|app.js|http.get' frontend/app.py scripts/p13_1_browser_verify.js
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_1_baseline_metrics.py
.venv/bin/pytest -o addopts= -q
```

并继续使用真实浏览器 DOM 复验 SPA。
