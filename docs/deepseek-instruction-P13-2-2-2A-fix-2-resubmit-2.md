# DeepSeek 第二次重提指令：P13-2-2-2A fix-2 禁止仅刷新旧报告

## 任务目标

实际实现 `docs/deepseek-instruction-P13-2-2-2A-fix-2.md`。前两次完成声明均没有修改生产脚本或测试；第二次只重跑旧脚本并刷新旧交付报告SHA。本次增加确定性preflight，未通过时禁止提交验收。

## 不接受的操作

- 只重跑旧readiness生成新`generated_at`和新SHA；
- 只修改 `acceptance-P13-2-2-2A-delivery-fix-20260714.md`；
- 继续报告61项/389项旧测试；
- 继续把N11写成“缺生产密钥”；
- 复制Commander文档中的术语而不在生产源码调用对应函数。

## 提交前强制preflight

以下命令必须全部成功，否则不得声明完成：

```bash
test -f docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md

rg -n 'verify_manifest_file' scripts/p13_2_real_annotation_launch_readiness.py
rg -n 'compute_task_hash' scripts/p13_2_real_annotation_launch_readiness.py
rg -n 'dataset_manifest_path' scripts/p13_2_real_annotation_launch_readiness.py
rg -n 'pack_manifest_path' scripts/p13_2_real_annotation_launch_readiness.py
rg -n 'task_dir' scripts/p13_2_real_annotation_launch_readiness.py
rg -n 'verify-evidence' scripts/p13_2_real_annotation_launch_readiness.py

test "$(shasum -a 256 scripts/p13_2_real_annotation_launch_readiness.py | awk '{print $1}')" != \
  '57ca10c8588dbfb3af9adb832b1fc7330aeb56af5ea5077344cad4f68e979b59'
test "$(shasum -a 256 tests/test_p13_2_real_annotation_launch_readiness.py | awk '{print $1}')" != \
  '21f7685c21b627fa2352de5fafbf21e6d6219e7313582d198633f44a5592e16b'

.venv/bin/python scripts/p13_2_real_annotation_launch_readiness.py --verify-evidence
```

最后一条必须是实际只读验证成功的exit0，不能是argparse `unrecognized arguments`。

## 技术要求

所有技术要求仍以以下文件为准，不删减：

```text
docs/deepseek-instruction-P13-2-2-2A-fix-2.md
```

尤其必须完成：

- 复用1A `verify_manifest_file`；
- 逐task调用 `compute_task_hash`；
- 从签名pack重算test任务、双标和访问隔离；
- split与候选/任务精确绑定；
- N11真实签名、dataset hash、task hash篡改；
- N16调用生产`--verify-evidence`；
- 正向READY使用真实tmp_path四pack和签名manifest。

## 交付报告

必须新建：

```text
docs/acceptance-P13-2-2-2A-delivery-fix-2-20260714.md
```

不得继续覆盖旧 `delivery-fix-20260714.md`。新报告须记录：

- 修改文件清单及新SHA；
- preflight每条退出码；
- 新聚焦/全量测试数量；
- 14个生产主路径负例；
- 正向签名pack READY证据；
- 正式无输入BLOCKED evidence及sidecar对账。

## 完成边界

fix-2实际落盘前不得再次声明完成。当前真实候选仍为0，正式默认运行必须BLOCKED；不得进入P13-2-2-2B。
