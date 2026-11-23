# P13-2-2-1 fix-3 Commander 独立验收报告

验收日期：2026-07-13

结论：**不通过，需要返修；不得进入 P13-2-2-2。**

## 已通过项

- annotation 侧普通 ID / UUID + `fixture=false` 已能被 task fixture 对比阻断。
- Importer 不再使用 ID 关键词决定来源身份。
- Ruff：PASS。
- 聚焦测试：41 passed。
- 全量回归：265 passed，3 warnings。
- mutation gate：脚本报告 30/30 mutation、1/1 invariant、5/5 meta-negative。
- P13-1 behavior probe、P13-2 goldset validator 和 `git diff --check` 通过。
- 退化 κ、stage policy、结构化 importer checks 没有回退。

## 阻断问题

### P0-1：task hash 生成端加入 fixture，但 importer 未独立复算，整包篡改仍可冒充真实来源

位置：

- `signal_miner/evaluation/human_annotation.py::compute_task_hash()`
- `scripts/p13_2_import_human_annotations.py::_validate_one()`
- `scripts/p13_2_import_human_annotations.py::_build_task_index()`

问题：生成端现在把 `fixture` 纳入 task hash，但 importer 的 `dataset_identity` 仅比较：

```text
annotation.task_hash == task.task_hash
```

它没有用 task 中的 `dataset_id/sample_id/slot/content_hash/fixture` 重新计算期望 hash。因此 task 文件的 fixture 和 pack 顶层 fixture 可以一起被修改，而旧 task hash 仍会被接受。

Commander 独立正式 CLI 反例：

1. 复制冻结 fixture task packs。
2. 找到目标 annotation 所在 pack，把该 pack 顶层和 pack 内全部 task 的 `fixture` 改为 false。
3. 保留所有原 task hashes 不变。
4. 把对应 fixture annotation 改为普通 ID、`fixture=false`，保留原 task hash。
5. 使用正式 importer 导入临时 store。

实际结果：

```json
{
  "exit": 0,
  "status": "IMPORTED",
  "passed": true,
  "dataset_identity": {"passed": true},
  "fixture_provenance": {"passed": true},
  "added": 1,
  "stored_fixture": false
}
```

影响：伪造标签再次进入真实人工计数。新增的“fixture 已参与 task hash”只是生成端声明，没有在消费端形成可验证的完整性闭环。

根因：同源字段互相比较代替了独立重算；fix-3 指令明确要求“翻转 task fixture 但保留旧 task hash”mutation，但交付的 5 类 provenance mutation 未覆盖该项。

验收要求：

- Importer 必须从 task 的规范字段独立重算 task hash，并与 task.task_hash 比较。
- annotation.task_hash、task.task_hash、重算 expected_task_hash 三者必须一致。
- pack 顶层 fixture 缺失、非 bool 也必须失败，不能只检查与 task 的相等性。
- 正式 CLI mutation 必须覆盖“整个 pack/task fixture 一起翻转但保留旧 hash”，指定真实 `task_integrity` 或 `dataset_identity` target=false、exit 1。
- 导入失败时 store 保持不存在或 SHA 不变。

## 非阻断观察项

即使重算普通 SHA，也只能发现“字段被改但 hash 未同步”，不能抵抗能够同时重算全部 hash 的恶意改包。进入真实人工标注前，仍需用冻结 manifest 的 pack SHA、只读发布物或签名/HMAC建立外部信任根。本次至少先完成任务书要求的独立重算闭环。

## 问题统计归类

- 授权 / 来源真实性完整性链未闭环：再次复发，P0。
- 验证器以同源字段相等代替独立重算：再次复发，P0。
- 契约测试遗漏任务书已明确的旧 hash 篡改负例：再次复发，P0。

## 复验要求

只修复 importer 独立 hash 重算、pack fixture 完整性和对应 mutation。不得再扩展名称规则，也不得开始真实人工标注。
