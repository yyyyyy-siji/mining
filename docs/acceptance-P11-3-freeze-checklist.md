# P11-3 验收报告：发布冻结前最终检查单

验收日期：2026-06-28

结论：不通过，需要返修。

## 已通过项

除 `git diff --check` 外，其余质量门禁本地复验通过：

```bash
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
```

结果：All checks passed。

```bash
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
```

结果：18 passed。

```bash
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
```

结果：43 passed，1 个 `StarletteDeprecationWarning`，非阻塞。

```bash
.venv/bin/python -m compileall signal_miner frontend/app.py
```

结果：通过。

```bash
node --check frontend/static/app.js
```

结果：通过。

## 阻断问题

### P1-1：`git diff --check` 失败，但检查单标为通过/非阻塞

位置：

- `tests/test_prd_routes.py:366`
- `docs/release-candidate-P11-3-freeze-checklist-20260628.md:18`
- `docs/release-candidate-P11-3-freeze-checklist-20260628.md:72`
- `docs/release-candidate-P11-3-freeze-checklist-20260628.md:102`

问题：

P11-3 指令明确要求：如 `git diff --check` 发现 whitespace 或 conflict marker 问题，只记录问题并停止为不通过。实际命令返回退出码 2：

```bash
git diff --check
```

输出：

```text
tests/test_prd_routes.py:366: new blank line at EOF.
```

但交付物将该问题写成“通过*”和“非阻塞”，这与 P11-3 验收标准不一致。

影响：

发布冻结检查单会误导人工认为可继续冻结，而实际仍存在 `git diff --check` 阻断项。

验收要求：

移除 `tests/test_prd_routes.py` 文件末尾多余空行，确保 `git diff --check` 退出码为 0 且无输出；随后更新冻结检查单，将 `git diff --check` 记录为通过。

### P1-2：工作树快照不是验收时点最新状态

位置：`docs/release-candidate-P11-3-freeze-checklist-20260628.md:13` 至 `docs/release-candidate-P11-3-freeze-checklist-20260628.md:16`

问题：

交付物记录：

```text
modified=9
untracked=62
total=71
docs=59
```

验收时点实际为：

```text
modified=9
untracked=63
total=72
docs=60
signal_miner=1
tests=2
```

影响：

发布冻结检查单的核心用途是冻结前最后状态核对，状态计数不准确会影响人工暂存范围判断。

验收要求：

返修时重新运行 `git status --short`，用最新结果更新工作树摘要、验证结果和人工提交顺序中的文档数量。注意：本验收报告和返修指令会新增文档条目，因此返修时计数会继续变化，必须以返修时最新命令结果为准。

## 非阻断观察项

P9/P10 代码与测试保护集仍通过。问题集中在 freeze checklist 的 `git diff --check` 阻断处理和状态计数刷新。

## 复验要求

返修后复验：

```bash
git status --short
git diff --stat
git diff --check
ruff check signal_miner/pipeline/prd_generator.py signal_miner/routes/assets.py tests/test_prd_generator.py tests/test_prd_routes.py
.venv/bin/python -m pytest tests/test_prd_generator.py tests/test_prd_routes.py -q
.venv/bin/python -m pytest tests/test_prd_routes.py tests/test_source_clickthrough_contract.py tests/test_connector_response_models.py tests/test_github_connector.py tests/test_evidence_chain.py -q
.venv/bin/python -m compileall signal_miner frontend/app.py
node --check frontend/static/app.js
```
