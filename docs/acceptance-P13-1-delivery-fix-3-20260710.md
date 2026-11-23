# P13-1 fix-3 交付报告：残留契约与浏览器证据收口

交付日期：2026-07-10

## 结论

- 自评：**BLOCKED**（Playwright 不可用；所有其他门禁通过）

## 修改文件

| 文件 | 修改说明 |
| --- | --- |
| `frontend/app.py` | 删除两处 `/pipeline/run` payload 中的 `confidence_threshold` 字段 |
| `scripts/p13_1_browser_verify.js` | 重写：删除 `doSimpleVerify()` 源码 fallback，Playwright 不可用时 exit(2) + BLOCKED JSON |
| `scripts/p13_1_baseline_metrics.py` | 新增 static_contracts 门禁：streamlit无payload字段、browser无源码fallback，参与顶层 passed |

## 修复项对应关系

| Commander 问题 | 修复证据 |
| --- | --- |
| Streamlit 仍发送 confidence_threshold | `grep '"confidence_threshold":' frontend/app.py` → 无匹配 |
| browser verifier 源码 fallback | `grep 'doSimpleVerify\|app.js\|http.get' scripts/p13_1_browser_verify.js` → 无匹配 |
| 报告漂移 | metrics.json 新增 static_contracts 字段，顶层 passed 包含此门禁 |

## 命令结果

| 命令 | 退出码 | 摘要 |
| --- | ---: | --- |
| `ruff check signal_miner tests scripts` | 0 | All checks passed |
| `node --check frontend/static/app.js` | 0 | PASS |
| `node --check scripts/p13_1_browser_verify.js` | 0 | PASS |
| 静态契约断言 | 0 | fix-3 static contract assertions passed |
| `p13_1_behavior_probe.py` | 0 | Overall: PASS |
| `p13_1_baseline_metrics.py` | 0 | Overall: PASS |
| 聚焦测试 (24) | 0 | 24 passed |
| 全量回归 | 0 | 196 passed, 3 warnings |

## 机器证据

- metrics: `docs/P13-1-evidence/metrics.json`
- behavior probe: `docs/P13-1-evidence/behavior_probe.json`
- browser evidence: **BLOCKED** — Playwright 不可用

## 未覆盖风险

- 浏览器 PNG 截图需 Playwright，Commander 可独立复验
- P13-2 置信度校准尚未开始
- P13-3 真实 Embedding 选型尚未开始
