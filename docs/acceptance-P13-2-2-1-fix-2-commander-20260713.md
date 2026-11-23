# P13-2-2-1 fix-2 Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- Importer 已输出结构化 `checks`，mutation runner 会从同次报告读取指定 target。
- 5 类“exit 1 但目标未失败”的元负例通过。
- Ruff：PASS。
- 聚焦测试：36 passed。
- 全量回归：260 passed，3 warnings。
- annotation mutation gate：脚本报告 26/26 mutation、1/1 invariant、5/5 meta-negative。
- P13-1 behavior probe：PASS。
- P13-2 goldset validator：PASS / READY（fixture）。
- 两份 evidence JSON 均可解析，`git diff --check` 通过。
- 退化 κ、stage policy 与零候选 exit 2/BLOCKED 没有回退。

## 阻断问题

### P0-1：fixture 可通过改 annotation ID 冒充真实人工标签

位置：`scripts/p13_2_import_human_annotations.py` 的 `fixture_provenance`。

问题：任务包每条任务及包顶层均已有可信 `fixture=true`，但 importer 不比较 `annotation.fixture` 与冻结任务的 fixture 属性。当前只在 `annotation_id` 包含 `fixann/fixture/test/mock/sample/fake/demo` 时拒绝 `fixture=false`。

Commander 独立正式 CLI 反例：

1. 读取一条现有 fixture annotation。
2. 仅把 `annotation_id` 改为普通值 `ann_human_20260713_0001`。
3. 把 `fixture` 改为 `false`，其余 task identity 保持不变。
4. 使用正式 `p13_2_import_human_annotations.py` 和冻结 fixture task packs 导入临时 store。

实际结果：

```json
{
  "exit": 0,
  "status": "IMPORTED",
  "passed": true,
  "fixture_provenance": {"passed": true},
  "added": 1,
  "stored_fixture": false,
  "stored_id": "ann_human_20260713_0001"
}
```

影响：validator 根据 annotation 的 `fixture=false` 计算 `real_count` 和 `human_verified_count`。攻击者或错误流程可以批量重命名 fixture annotation，使其污染真实人工计数、κ 和后续置信度/校准依据。这正是本项目最高优先级的置信度来源问题。

根因：provenance 被可自由编辑的命名启发式替代，未使用冻结任务包已有的结构化来源真值。

验收要求：

- `annotation.fixture` 必须精确等于对应冻结 task 的 `fixture`。
- task pack 顶层 fixture 与逐任务 fixture 必须一致；冲突或缺失均失败。
- fixture/real 身份必须参与冻结 task hash 或被独立验证，不能由 annotation ID 推断。
- 普通 ID、随机 ID、空前缀均不得绕过。
- 正式 CLI mutation 必须复现本报告的“普通 ID + fixture=false”，并让 `fixture_provenance=false`、exit 1。

## 非阻断观察项

交付报告已经主动披露“fixture_provenance 依赖 id 标记词”和“content hash 不含 fixture”。该风险实际可利用，因此不是可接受的未覆盖风险，而是 P0 阻断。

## 问题统计归类

- 授权 / 来源真实性被命名启发式替代：再次复发，P0。
- 契约测试缺少真实绕过负例：再次复发，P0。
- 当前 importer target-check 真值化本身有效，但尚未覆盖正确的 provenance 业务目标。

## 复验要求

只修复结构化 fixture provenance，保留已通过的 importer checks、元负例、退化 κ、stage policy 和 readiness invariant。不得用更多 ID 关键词补丁代替任务来源绑定。
