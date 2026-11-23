# P13-2-2-1 fix-4 交付报告

## 结论

**通过**。修复了 pack/task fixture 整体翻转并保留旧 task hash 后 importer 仍接受伪造来源的 P0 漏洞。Importer 现在对每条命中的 task 独立重算 task hash，形成 `task.task_hash` ↔ `expected_hash` ↔ `ann.task_hash` 三方一致性闭环。

## 修改文件

| 文件 | 变更 |
|---|---|
| `scripts/p13_2_import_human_annotations.py` | 新增 `compute_task_hash` 导入；`_validate_one` 在 `dataset_identity` 中独立重算 task hash 并与 `task.task_hash` / `ann.task_hash` 比较；`_build_task_index` 新增 pack 顶层及 task 级 fixture schema 完整性校验（必须存在且为 bool） |
| `scripts/p13_2_annotation_mutation_gate.py` | 新增 5 类 fix-4 mutation（整包翻转保留旧 hash、双端同步 fake hash、pack fixture 缺失、pack fixture 字符串、任意改写同源 hash） |
| `tests/test_p13_2_human_annotation_contract.py` | 新增 `TestTaskHashRecompute`（2 项）：Commander 整包翻转回归、双端同步 fake hash 回归 |

## Task hash 三方一致性契约

```
expected_hash = compute_task_hash(
    task.dataset_id, task.sample_id, task.annotator_slot,
    task.content_hash, fixture=task.fixture
)
```

必须同时满足：

- `task.task_hash == expected_hash` → 否则 `dataset_identity: task_hash_recompute_mismatch`
- `ann.task_hash == expected_hash` → 否则 `dataset_identity: task_hash_recompute_mismatch`

任一不一致 → exit 1, `dataset_identity.passed = false`, store 不变。

## Pack fixture schema 契约

| 规则 | 违反时错误 |
|---|---|
| pack 顶层 `fixture` 必须存在 | `pack_fixture_missing` |
| pack 顶层 `fixture` 必须为 bool | `pack_fixture_not_bool` |
| 每条 task `fixture` 必须存在 | `task_fixture_missing` |
| 每条 task `fixture` 必须为 bool | `task_fixture_not_bool` |
| pack fixture == 每条 task fixture | `pack_fixture != task_fixture` |

所有错误均进入 `fixture_provenance`。

## Commander 整包翻转反例

```
构造：
1. 复制 fixture task packs → 临时目录
2. 把 development pack 顶层及全部 task fixture 改为 false
3. 保留旧 task hashes（不更新）
4. annotation 用普通 ID + fixture=false + 旧 task_hash
5. 运行正式 importer CLI

结果：
exit: 1
status: FAIL_VALIDATION
passed: false
dataset_identity:
  passed: false
  errors:
    - task_hash_recompute_mismatch task_hash=8a2f2653... expected=41b78f8a...
    - task_hash_recompute_mismatch ann_hash=8a2f2653... expected=41b78f8a...
store exists: false（未被创建）
```

## 新增 mutation 与 target 证据

| mutation | target_check | child_exit | check_exists | target_passed | detected |
|---|---|---|---|---|---|
| full_pack_fixture_flip_old_hash | dataset_identity | 1 | true | false | true |
| task_hash_rewritten_both_sides | dataset_identity | 1 | true | false | true |
| pack_fixture_missing | fixture_provenance | 1 | true | false | true |
| pack_fixture_wrong_type | fixture_provenance | 1 | true | false | true |

**总计：34/34 mutation 检测，1/1 invariant 通过，5/5 meta-negative 通过。**

## 全量回归和状态不变量

| 命令 | Exit Code |
|---|---|
| ruff check | 0 |
| focused pytest (43 passed) | 0 |
| full pytest (267 passed) | 0 |
| mutation gate (34/34 + 1/1 + 5/5) | 0 |
| P13-1 behavior probe | 0 |
| P13-2 goldset validator | 0 |
| contract-metrics.json parse | 0 |
| mutation-gate.json parse | 0 |

- fixture 工具链仍为 `FIXTURE_PASS`
- `human_verified_count=0`、`human_labels_complete=false`
- 既有退化 κ、stage policy、ID/UUID 绕过阻断、importer checks 均未回退

## 外部信任根剩余风险

- 即使独立重算 hash，攻击者若同时更新 hash 值也可绕过。进入真实人工标注前，需用冻结 manifest pack SHA 或签名/HMAC 建立外部信任根
- 当前 fixture 生成后 task hash 含 fixture，但无独立于生成器的 hash 验证
