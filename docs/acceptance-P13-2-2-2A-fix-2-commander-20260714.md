# P13-2-2-2A fix-2 Commander 验收报告

验收日期：2026-07-14

结论：**未交付；第二次完成声明仍未实现fix-2，无法进入功能复验；不得进入 P13-2-2-2B。**

用户侧声明“已完成”，但当前工作区没有任何 fix-2 实现或交付物。现存代码、测试、正式evidence和交付报告仍全部是上一轮 fix 版本，因此不能把旧产物重复验收为 fix-2。

## 独立核查结果

### 1. 缺少 fix-2 交付报告

预期至少存在：

```text
docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md
```

全局检索未发现该文件，也未发现其他命名的fix-2交付报告。

### 2. 实现与测试没有更新

| 文件 | 修改时间 | 当前SHA-256 |
| --- | --- | --- |
| `scripts/p13_2_real_annotation_launch_readiness.py` | 2026-07-14 14:51:42 | `57ca10c8588dbfb3af9adb832b1fc7330aeb56af5ea5077344cad4f68e979b59` |
| `tests/test_p13_2_real_annotation_launch_readiness.py` | 2026-07-14 14:55:23 | `21f7685c21b627fa2352de5fafbf21e6d6219e7313582d198633f44a5592e16b` |
| `docs/P13-2-evidence/real-annotation-launch-readiness.json` | 2026-07-14 15:01:12 | `a844c819943db671695dcfb3b908b5b513e3153e0034dd86e329254968fb90b8` |

这些均早于Commander发布fix-2指令，且内容仍是上一轮已判失败的版本。

### 3. fix-2要求的生产入口不存在

独立执行：

```bash
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

实际：

```text
error: unrecognized arguments: --verify-evidence
exit 2
```

这不是“篡改被验证器阻断”，而是参数根本没有实现。

### 4. fix-2核心符号不存在

在readiness脚本和对应测试中检索以下符号：

- `verify_manifest_file`
- `compute_task_hash`
- `dataset_manifest_path`
- `pack_manifest_path`
- `task_dir`
- `pack_trust`
- `task_identity`
- `split_binding`
- `double_label_recomputed`

除一条“Pack trust constants”注释外均无命中。说明P13-2-2-1A verifier、task hash重算、manifest路径和真实任务绑定尚未接入。

## 仍然有效的上一轮阻断

由于实现未变化，上一份Commander报告中的正式CLI假绿仍未关闭：

- 无dataset/pack manifest仍可READY；
- 0个签名pack、0个test task仍可READY；
- split与候选零交集仍可READY；
- 双标与访问边界仍只信任配置自报；
- N11/N16仍未走生产主路径；
- 旧交付报告仍同时保留当前与陈旧SHA。

详见 `docs/acceptance-P13-2-2-2A-fix-commander-20260714.md`。

## 验收决策

- 本次不运行“61项旧聚焦测试/389项旧全量测试”作为fix-2证据，因为它们已经在上一轮证明会放行假绿。
- 当前状态不是代码返修失败，而是交付物缺失。
- 继续执行同一P13-2-2-2A fix-2，不升级到fix-3，也不改变原技术范围。

## 复验前置条件

只有下列条件全部满足后才接受下一次“已完成”复验：

1. readiness实现和测试实际包含fix-2核心符号与生产CLI路径；
2. 新增fix-2交付报告；
3. 正式evidence/sidecar按新实现重新生成并对账；
4. 提供原fix-2指令要求的14个生产主路径负例及正向签名pack证据；
5. 不修改Commander验收报告来伪装交付完成。

## 问题统计归类

- 完成声明与工作区实际交付不一致：新增1次交付完整性阻断。
- 未执行回归却不能据旧结果宣告新阶段通过：归入“报告/执行状态不一致”。

## 第二次重提交核查（2026-07-14）

第二次声明完成后，工作区只发生以下变化：

- 重新运行旧readiness脚本，刷新正式JSON、sidecar和时间戳；
- 修改旧文件 `docs/acceptance-P13-2-2-2A-delivery-fix-20260714.md` 中的SHA。

生产实现和测试仍保持完全相同的旧SHA：

```text
scripts/p13_2_real_annotation_launch_readiness.py
57ca10c8588dbfb3af9adb832b1fc7330aeb56af5ea5077344cad4f68e979b59

tests/test_p13_2_real_annotation_launch_readiness.py
21f7685c21b627fa2352de5fafbf21e6d6219e7313582d198633f44a5592e16b
```

再次独立执行 `--verify-evidence` 仍为 `unrecognized arguments / exit2`；源码仍无 `verify_manifest_file`、`compute_task_hash`、dataset/pack manifest或task_dir生产路径。

更新后的旧交付报告仍然：

- 依据旧 `fix.md`，不是 `fix-2.md`；
- 报告61项旧聚焦测试和389项旧全量测试；
- 把N11列为“缺生产密钥”，不是签名/dataset/task hash篡改；
- 把N16列为内存SHA比较，没有生产只读verifier；
- 声称“工具链已就绪”，但核心实现不存在。

因此第二次提交不是fix-2交付，而是**刷新旧报告和旧evidence**。交付完整性阻断累计第二次复发；不得再通过更新时间或SHA变化代替代码实现。
