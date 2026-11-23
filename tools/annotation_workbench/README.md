# SignalMiner 人工标注工作台

这是一个完全本地运行的人工标注页面。它读取项目生成的`human_tasks_*.json`任务包，在浏览器中保存草稿，并导出可交给`p13_2_import_human_annotations.py`的JSON。

## 为什么使用页面而不是Excel

- 鼠标划选原文即可生成Python兼容的`[start, end)`字符区间；
- 自动检查evidence是否逐字匹配原文；
- 自动使用任务包中的dataset、task hash、content hash和fixture来源；
- blind任务不会显示suggestion，并会拒绝含模型、Prompt、置信度等字段的任务包；
- 导出系统JSON的同时，也可以导出Excel可读的CSV供人工复核。

## 打开方式

最简单的方式是双击：

```text
tools/annotation_workbench/index.html
```

也可以从项目根目录启动只读本地静态服务：

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1
```

然后打开：

```text
http://127.0.0.1:8765/tools/annotation_workbench/
```

如果只想直接开始当前仓库内置的开发/校准练习任务，可打开：

```text
http://127.0.0.1:8765/tools/annotation_workbench/?autoload=fixture-assisted
```

这个入口会自动载入`development + calibration`共75条任务。它们全部是
`fixture=true`的流程练习数据，页面会持续显示`FIXTURE`，不得作为正式金标。

页面不调用后端API，不会自动上传任务或标注。草稿保存在当前浏览器的localStorage中。

## 标注流程

1. 标注协调员把一个槽位的任务包交给标注员。
2. 点击“导入任务包”。
   - assisted标注员可同时导入development和calibration包；
   - test A和test B必须在不同工作区、不同标注员下分别操作；
   - 页面禁止把A、B和assisted任务包混在同一工作区。
3. 填写或本地生成不可逆`annotator_pseudonym`。
4. 阅读脱敏原文，判断“有信号/无信号”。
5. 有信号时：
   - 添加一条或多条信号；
   - 选择signal type；
   - 写摘要；
   - 在左侧原文中划选证据，点击“添加到当前信号”；
   - 填写隐含需求、依据和备注。
6. assisted-review任务还必须选择接受、修改或拒绝建议。
7. 点击“校验并完成”。
8. 完成若干任务后可以随时导出：
   - “系统JSON”：用于正式importer；
   - “CSV”：用于Excel检查，不作为系统导入文件。

快捷键：

- `Option + ← / →`：切换任务；
- `Command/Ctrl + Enter`：校验并完成当前任务。

## 恢复工作

- 重新导入完全相同的任务包时，页面会自动恢复本地草稿；
- 也可以先导入任务包，再点击“恢复标注”导入之前导出的系统JSON；
- 恢复时会重新核对dataset、sample、slot、task hash、content hash、annotation mode和fixture来源。

## 导入项目annotation store

系统JSON导出后，仍必须使用已验收importer校验。真实路径示例：

```bash
APP_ENVIRONMENT=production \
ANNOTATION_PACK_SIGNING_KEY='<通过环境安全注入，不要写入仓库>' \
.venv/bin/python scripts/p13_2_import_human_annotations.py \
  --input <工作台导出的human_annotations_*.json> \
  --tasks <本批次human_tasks目录> \
  --manifest <本批次human-task-pack-manifest.json> \
  --dataset-manifest <本批次dataset-manifest.json> \
  --store <本批次human-annotation-store.json> \
  --out <本批次import-report.json>
```

fixture演示导入必须使用项目既有test环境边界和显式注入测试密钥，不能把fixture结果当真实人工金标。

## 当前边界

- 页面是单机单人工作台，没有多人在线协作和任务锁；
- 页面不负责签名任务包，也不修改任务hash；
- 页面不计算kappa，不负责分歧裁决；
- 页面通过不等于正式annotation通过，最终以importer和validator机器结果为准；
- 真实标注不得使用页面内置fixture演示数据。
