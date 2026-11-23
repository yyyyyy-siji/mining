# DeepSeek 重提指令：P13-2-2-2A fix-2 必须实际落盘

## 任务目标

实际执行并落盘 `docs/deepseek-instruction-P13-2-2-2A-fix-2.md`。本文件不改变技术范围，只补充“交付存在性”门禁，防止再次在代码、测试和evidence均未变化时声明完成。

## 当前状态

- readiness脚本SHA仍为 `57ca10c8588dbfb3af9adb832b1fc7330aeb56af5ea5077344cad4f68e979b59`。
- 测试SHA仍为 `21f7685c21b627fa2352de5fafbf21e6d6219e7313582d198633f44a5592e16b`。
- `--verify-evidence`尚未实现。
- readiness未导入 `verify_manifest_file` 或 `compute_task_hash`。
- fix-2交付报告不存在。

因此当前不是“fix-2已完成但待复验”，而是“fix-2未交付”。

## 执行要求

完整执行原指令：

```text
docs/deepseek-instruction-P13-2-2-2A-fix-2.md
```

不得只修改旧交付报告、Commander报告、任务书或quality metrics；必须有实际实现、测试和正式evidence变化。

## 交付存在性硬门禁

提交复验前必须同时满足：

1. `scripts/p13_2_real_annotation_launch_readiness.py` 实际包含并使用：
   - `verify_manifest_file`
   - `compute_task_hash`
   - dataset/pack manifest与task_dir生产路径
   - `--verify-evidence`只读验证入口
2. `tests/test_p13_2_real_annotation_launch_readiness.py`包含原fix-2要求的14个生产主路径负例，特别是：
   - manifest签名、dataset hash、task hash真实篡改；
   - 空pack/0 test task；
   - split与候选零交集；
   - 双标与访问边界从task重算；
   - evidence/sidecar篡改调用真实`--verify-evidence`并exit1。
3. 正向测试必须使用tmp_path下真实四pack、dataset manifest和签名pack manifest，不得继续使用空JSON或内存声明作为READY证据。
4. 新增交付报告：

```text
docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md
```

5. 正式运行仍应为无输入 `BLOCKED_INPUT_REQUIRED/exit2`，并重新发布：
   - `docs/P13-2-evidence/real-annotation-launch-readiness.json`
   - `docs/P13-2-evidence/real-annotation-launch-readiness.json.sha256`
6. 交付报告必须记录修改后文件SHA，并证明与本指令列出的旧SHA不同；若实现SHA未变化，不得声明完成。

## 必跑命令

```bash
.venv/bin/ruff check signal_miner tests scripts
.venv/bin/python -m pytest -o addopts= -q tests/test_p13_2_real_annotation_launch_readiness.py
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --no-publish
.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
.venv/bin/python scripts/p13_2_verify_committed_evidence.py
git diff --check
```

每条命令必须记录真实退出码。`--verify-evidence`不得再是argparse未识别参数。

## 禁止事项

- 不得把上一轮61项/389项旧结果复制为fix-2证据。
- 不得编辑Commander验收报告以消除阻断描述。
- 不得只创建空交付报告而不修改生产实现。
- 不得进入P13-2-2-2B或任何下游阶段。

## 完成边界

只有实际文件落盘且原fix-2全部门禁通过后，才可再次声明“已完成，进行验收”。当前真实输入仍为0，不得制造生产READY。

