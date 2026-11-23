# DeepSeek 执行指令：P13-2-2-1A 人工任务包外部信任根

## 任务目标

为人工 task packs 建立独立于 pack 内容和普通 task hash 的外部完整性信任根，使能够同时修改 task 字段并重新计算 SHA 的改包行为仍被拒绝。本阶段只建设签名、验证和操作边界，不执行真实人工标注。

## 背景 / 当前问题

P13-2-2-1 fix-4 已通过：importer 会独立重算 task hash，可发现字段被改但旧 hash 未更新。

剩余风险是普通 SHA 没有身份认证能力。若改包者同时修改 fixture/任务内容并重新计算所有 hashes，单靠 pack 自身无法证明它来自授权发布者。真实人工标签进入前必须增加 pack manifest 和外部密钥签名/HMAC信任根。

当前真实授权候选仍为0，因此真实模式必须诚实 BLOCKED，禁止用 fixture、测试密钥或 LLM 标签冒充生产就绪。

## 允许修改范围

- `signal_miner/evaluation/` 下新增 pack trust 模块
- 人工任务包 prepare/import/validate 脚本的 manifest/signature 参数
- 新增 `scripts/p13_2_sign_human_task_pack.py` 或等价专用工具
- 新增独立 mutation gate 与聚焦测试，或扩展现有人工 annotation gate
- `docs/P13-2/` 操作说明
- fixture task pack manifest/signature 测试 artifacts
- `docs/P13-2-evidence/` 本阶段证据

## 禁止修改范围

- 在仓库、报告、fixture 或日志中写真实签名密钥
- 生产模式使用默认密钥、硬编码密钥或公开 fixture 密钥
- 无密钥时降级为普通 SHA 后仍标 PASS
- 伪造真实授权候选、人工标签或签名完成状态
- 生产 pipeline、LLM、Embedding、去重、聚类、API、前端和数据库
- P13-2-2-2、校准及后续指标调优

## 实现要求

### 1. Pack manifest

生成规范化 `human-task-pack-manifest.json`，至少包含：

- schema/version
- dataset_id 与 dataset manifest hash
- fixture 标志
- 四个 pack 的相对路径、SHA-256、字节数、task count
- 每个 pack 的 annotation mode、slot和split
- total task count
- generated_at 与 signer key id（只存标识，不存密钥）
- canonicalization version

所有路径必须是受控相对路径，禁止绝对路径和 `..`。

### 2. 外部认证

- 使用 HMAC-SHA256 或项目环境可用的等价认证签名对 canonical manifest 签名。
- 真实模式密钥只从环境变量或外部 secret provider读取，例如 `ANNOTATION_PACK_SIGNING_KEY`。
- 密钥缺失：生成/导入真实 pack 必须 `BLOCKED_MISSING_PACK_SIGNING_KEY/exit2`。
- 签名错误、manifest/pack被改：FAIL/exit1。
- fixture 可以使用显式 test-only 注入密钥，但必须同时满足 `environment=test` 与 `fixture=true`；development/production 即使设置测试开关也不得启用。
- 日志和 JSON 只允许输出 key id、算法和校验结果，禁止输出密钥或完整敏感材料。

### 3. Importer 强制先验验证

Importer 在读取任务内容和导入 annotation 前必须：

1. 读取 manifest。
2. 验证 schema、路径和精确文件集合。
3. 验证每个 pack SHA、bytes、count与语义元数据。
4. 验证外部签名/HMAC。
5. 验证 dataset manifest hash。
6. 全部通过后才建立 task index并运行 P13-2-2-1 checks。

真实模式不得提供跳过签名参数。fixture test-only 路径必须在机器证据中明确标记。

### 4. 单一状态与计数

- `pack_trust_verified` 只能来自正式 verifier 结果。
- `human_verified_count` 只允许统计来自 `pack_trust_verified=true` 的真实 task annotations。
- fixture签名验证不得改变真实人工计数。
- P13-2-2-2的 READY 前置条件新增：真实 pack trust verified。

## 必须存在的 mutation

至少覆盖：

1. 修改任一 task fixture并重新计算task hash，但不更新manifest/signature。
2. 修改task、task hash和manifest SHA，但不更新签名。
3. 修改manifest并伪造`passed=true`字段。
4. 替换一个pack为另一合法pack。
5. 添加额外pack或漏一个pack。
6. 路径穿越和绝对路径。
7. pack bytes/count与manifest不一致。
8. dataset_id或dataset manifest hash不一致。
9. signer key id不匹配。
10. 签名缺失、截断、错误算法、错误密钥。
11. 生产无密钥被fixture测试密钥补齐。
12. `environment=development + test key flag`企图启用测试密钥。
13. fixture签名被计入真实human_verified_count。
14. verifier exit1但target check缺失/true时聚合器不得PASS。

每个 mutation 必须读取正式 CLI 同次结构化 target check；exit1、target存在且false才算捕获。真实无密钥属于exit2/BLOCKED，不计作mutation错误。

## 验收标准

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_pack_trust_contract.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_pack_trust_mutation_gate.py
.venv/bin/python scripts/p13_2_annotation_mutation_gate.py
.venv/bin/python scripts/p13_1_behavior_probe.py
.venv/bin/python scripts/p13_2_validate_goldset.py
git diff --check
```

通过条件：

- fixture test-only 签名工具链 PASS且明确 `fixture_only=true`。
- 真实无密钥路径 exit2/BLOCKED，不得显示PASS。
- 所有pack trust mutation真实命中指定target。
- P13-2-2-1的34类mutation、43项聚焦和状态不变量不回退。
- 测试使用临时目录，冻结 artifact SHA不被测试污染。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`保持。

## 交付前质量门禁

- 对所有子命令采集真实退出码。
- evidence JSON顶层passed由每个关键check复算。
- 报告中的mutation数、fixture状态、真实BLOCKED状态来自同次JSON。
- 扫描仓库和交付报告，确认没有密钥明文。
- 缺少签名工具依赖或密钥时必须诚实BLOCKED，不得跳过后报通过。

## 交付报告模板

```markdown
# P13-2-2-1A 交付报告：人工任务包外部信任根

## 结论
## 修改文件
## Pack manifest契约
## 签名/HMAC与密钥边界
## Importer先验验证
## Fixture test-only与真实BLOCKED
## Mutation target证据
## 密钥泄露扫描
## P13-2-2-1回归
## 状态不变量与人工前置动作
```

交付物：

1. `docs/acceptance-P13-2-2-1A-delivery-20260713.md`
2. `docs/P13-2-evidence/pack-trust-contract-metrics.json`
3. `docs/P13-2-evidence/pack-trust-mutation-gate.json`
4. `docs/P13-2/human-task-pack-trust-operations-v1.md`

## 完成边界

本阶段通过只表示人工 task pack 具备可认证的外部完整性。真实授权候选仍为0时，P13-2-2-2继续冻结；不得生成虚构真实标签或开启概率校准。
