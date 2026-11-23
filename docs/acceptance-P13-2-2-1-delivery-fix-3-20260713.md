# P13-2-2-1 fix-3 交付报告

## 结论

**通过**。修复了 fixture annotation 通过重命名 ID 并设置 `fixture=false` 冒充真实人工标签的 P0 漏洞。来源身份改为绑定冻结 task pack 的结构化 `fixture` 字段，删除了 ID 名称关键词启发式。

## 修改文件

| 文件 | 变更 |
|---|---|
| `signal_miner/evaluation/human_annotation.py` | `compute_task_hash` 新增 `fixture` 参数，纳入规范化输入；任何 fixture 变动都改变 task hash |
| `scripts/p13_2_prepare_human_tasks.py` | 调用 `compute_task_hash` 时传入 `fixture=fixture` |
| `scripts/p13_2_import_human_annotations.py` | `fixture_provenance` 改为从冻结 task 读取 `task.fixture` 与 `annotation.fixture` 严格相等比较；删除 `_FIXTURE_ID_TAGS` 安全边界；新增 pack 级 fixture 一致性校验 |
| `scripts/p13_2_annotation_mutation_gate.py` | 替换旧 m20（ID 标签），新增 5 类 fixture provenance mutation（普通 ID、UUID、task fixture 缺失、类型错误、pack/task 冲突） |
| `tests/test_p13_2_human_annotation_contract.py` | 新增 `TestFixtureProvenanceTaskBinding`（5 项）：Commander 普通 ID 反例、UUID 反例、clean fixture 通过、ID 改名不影响判定、task fixture 缺失检测 |
| `sample_data/p13_2/human_tasks/*` | 重新生成（task hash 现在包含 fixture） |
| `sample_data/p13_2/annotations/fixture_annotations.json` | 重新生成（task hash 现在匹配） |
| `docs/P13-2-evidence/*` | 重新生成 evidence JSON |

## Fixture provenance 单一真源

**修复前**：`fixture_provenance` 检查 annotation_id 是否包含 `fixann/test/mock/...`。

**修复后**：
```python
# importer _validate_one, 第 12 条检查:
if task is not None:
    task_fixture = task.get("fixture")
    if task_fixture is None:
        → fixture_provenance = false (task_fixture_missing)
    elif not isinstance(task_fixture, bool):
        → fixture_provenance = false (task_fixture_not_bool)
    elif ann.fixture is not task_fixture:
        → fixture_provenance = false (fixture_mismatch)
```

- annotation_id 改名不影响判定
- 普通 ID、随机 UUID、任何不含关键词的 ID 均被结构化比较阻断
- 真实 task 即使 ID 含 `test` 等词，也不会仅因名称被判 fixture
- 身份只来自冻结结构化字段

## Task hash / pack 一致性契约

`compute_task_hash` 现在包含 `fixture`：

```python
payload = "|".join([dataset_id, sample_id, annotator_slot, content_hash,
                    str(fixture).lower()])
```

这意味着：
- task 侧翻转 fixture 会改变 task hash → `dataset_identity` 检查失败（双重保护）
- `_build_task_index` 同时校验 pack 顶层 fixture 与逐条 task fixture 一致

## Commander 普通 ID 反例

正式 CLI 验证：

```
输入: fixture annotation + annotation_id="ann_human_20260713_0001" + fixture=false
exit: 1
status: FAIL_VALIDATION
passed: false
fixture_provenance.passed: false
error: ann_human_20260713_0001: fixture_mismatch annotation=False task=True
store exists: false (未被创建/修改)
```

## 新增 mutation 与 target 证据

| # | mutation 名称 | target_check | child_exit | check_exists | target_passed | detected |
|---|-------------|-------------|-----------|-------------|--------------|----------|
| 20a | fixture_normal_id_false | fixture_provenance | 1 | true | false | true |
| 20b | fixture_uuid_id_false | fixture_provenance | 1 | true | false | true |
| 20c | task_fixture_missing | fixture_provenance | 1 | true | false | true |
| 20d | task_fixture_wrong_type | fixture_provenance | 1 | true | false | true |
| 20e | pack_task_fixture_conflict | fixture_provenance | 1 | true | false | true |

**总计：30/30 mutation 检测，1/1 invariant 通过，5/5 meta-negative 通过。**

## Store SHA 守恒

```
Commander 绕过导入前: store 不存在
Commander 绕过导入后: store 不存在（exit 1，未创建）
正常 fixture 导入: store 创建，120 条 fixture=true annotation
```

## 全量回归与状态不变量

| 命令 | Exit Code |
|---|---|
| ruff check | 0 |
| focused pytest (41 passed) | 0 |
| full pytest (265 passed) | 0 |
| mutation gate (30/30 + 1/1 + 5/5) | 0 |
| P13-1 behavior probe | 0 |
| P13-2 goldset validator | 0 |
| contract-metrics.json parse | 0 |
| mutation-gate.json parse | 0 |

**状态不变量**：
- `status = FIXTURE_PASS`
- `human_verified_count = 0`
- `human_labels_complete = false`
- `calibration_allowed = false`
- 退化 κ、stage policy、exit 2/BLOCKED readiness invariant 未回退
- 既有 importer checks、meta-negatives 全部有效

## 未覆盖风险

- 真实授权数据仍为 0，P13-2-2-2 及后续阶段继续冻结
- `content hash` 仍不含 `fixture` 字段（翻转 fixture 不改 content hash，需依赖 task hash 双重保护）
- pack fixture 一致性校验依赖 importer 的 task_index 构建，不独立于导入流程
