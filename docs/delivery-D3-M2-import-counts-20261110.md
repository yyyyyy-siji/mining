# D3-M2 批量导入新增/重复计数交付

日期：2026-11-10。按`docs/executor-instruction-D3-M2-import-counts-20261110.md`完成唯一修复，等待Commander独立复验。**仅修正批量回执计数；没有采集、浏览器、登录或诊断改动，没有实网请求。**

## 问题与结果

Commander用现有普通Chrome读取的1正文3评论在独立18817库中复现：重复提交后实际ID复用、数据库仍4行、快照未改，接口却报4新增0重复。原批量路由把`duplicates`固定为0，非空ID无法区分本次插入与复用。

现在新增/重复依据**本次入库事务的实际结果**：新事务commit成功才算新增；已有记录、legacy复用、IntegrityError后复用其他事务胜出记录均算重复。没有用请求前存在性查询估算计数，没有修改任何去重/来源规则。

| 输入 | total | ingested（实际新增） | duplicates（实际复用） |
| --- | --- | --- | --- |
| 首次4条不同材料 | 4 | 4 | 0 |
| 相同4条再次提交 | 4 | 0 | 4 |
| 同批4次相同材料 | 4 | 1 | 3 |
| 已有2条，混合新旧及同批重复6项 | 6 | 2 | 4 |
| 同一legacy材料提交2次 | 2 | 0 | 2 |
| 并发2个事务均先查不到同一来源 | 合计2 | 合计1 | 合计1 |

`feedback_ids`继续按输入顺序逐项返回实际ID，重复项允许出现同一ID。总数等于新增加重复。空批次为0/0/0。

## 实现与兼容性

`signal_miner/pipeline/runner.py`仅在原入库实现周围增加冻结结果对象`IngestFeedbackResult(feedback_id, inserted)`与`ingest_feedback_with_result`。原事务的SELECT、legacy条件、源键、行内容、commit/rollback、IntegrityError胜出查询及profile保护原样保留；各既有return分支现在附带真实inserted标记。

原公共`ingest_feedback(...) -> str`变成薄包装，仍返回实际反馈ID字符串，参数和调用兼容。单条`/feedback/ingest`继续使用它，原HTTP状态和返回行为不改；本轮没有额外修订单条接口标志。

`signal_miner/routes/feedback.py`只有批量执行段改用结果接口，按`inserted`计数；仍先预校验所有材料，再逐项入库。没有把计数改成预查询、没有额外事务/批次锁，没有吞掉数据库错误。批量原本逐项提交的语义不变：运行期数据库错误继续传播，不能将失败包装成完整成功回执；本轮不引入整批原子事务。

## 新增专用验证

`tests/test_feedback_batch_counts_D3.py`使用自己的临时SQLite/FastAPI客户端，材料全为OFFLINE fixture，未读取或写入Commander隔离库或业务库。

8项验证覆盖：

- 首次4条/重复4条，实际行数4、ID顺序一致，全部来源快照verified且完整不变；重复提交携带更新采集元数据也不覆盖旧快照。
- 混合新旧、请求内重复、空批次，逐项ID和实际DB行数相符；不同评论相同正文仍分别保留身份。
- legacy真实行复用计入重复，旧context/正文不变，不伪造来源快照。
- 强制两个实际事务都完成首次SELECT且均未命中，再放行提交；真实唯一约束触发一次rollback，合计仅1新增1重复，数据库只有1行且快照verified。由此证明不是仅靠请求前查询误判新增。
- 在不同来源键上制造真实主键冲突，确认没有同键winner时IntegrityError仍传播，旧行完全不变，不能虚报新增/重复成功。
- 批次第2条来源不合格时，整个批次写入前返回422，数据库0行。
- 原字符串调用、结果接口和单条HTTP接口均复用同一个实际ID，兼容性保留。

## 实际命令、退出码与数量

```sh
.venv/bin/pytest -o addopts='' -q tests/test_feedback_batch_counts_D3.py
```

exit0：**8 passed，1.57s**。

```sh
.venv/bin/pytest -o addopts='' -q tests/test_feedback_batch_counts_D3.py tests/test_mediacrawler_D3.py tests/test_mediacrawler_frontend.py tests/test_community_preview_frontend.py tests/test_d1_source_frontend.py tests/test_source_evidence_D1.py tests/test_auth.py tests/test_source_acquisition_contract.py tests/test_community_preview_routes.py tests/test_opportunity_discovery.py tests/test_feedback_ingest_source_contract.py tests/test_source_clickthrough_contract.py tests/test_zhihu_search_preparation.py
```

exit0：**445 passed**（原437项加新增8项），1个既有Starlette/httpx弃用warning，4.13s。旧用例未改动、未削弱。

```sh
node --test tests/mediacrawler_frontend.test.cjs tests/community_preview_frontend.test.cjs tests/d1_source_frontend.test.cjs
node --check frontend/static/app.js
.venv/bin/ruff check signal_miner/pipeline/runner.py signal_miner/routes/feedback.py tests/test_feedback_batch_counts_D3.py
.venv/bin/python -m compileall -q signal_miner/pipeline/runner.py signal_miner/routes/feedback.py tests/test_feedback_batch_counts_D3.py
```

各命令exit0：**Node26/26**，JS语法通过，Ruff **All checks passed**，编译通过。静态命令另分别执行确认退出码，未以整条复合命令末尾结果替代单项检查。

按`outputs/D3-M1/existing-tests-sha256-20261106.json`逐个重算：**36/36历史测试SHA一致，changed=[]**。

## 精确交付文件与未执行项

仅修改/新增：

- `signal_miner/pipeline/runner.py`
- `signal_miner/routes/feedback.py`
- `tests/test_feedback_batch_counts_D3.py`
- 本报告`docs/delivery-D3-M2-import-counts-20261110.md`

没有修改采集/登录/浏览器/诊断/上游、来源身份或哈希快照、模型流程、数据库结构、业务数据库、`.env`或系统设置；没有新增代理、打开窗口、执行实网或创建提交。

实现和要求内测试已完成，无未完成项。真实4条材料在同一18817隔离库的重复计数、ID及快照复验由Commander执行；本轮不冒称已经执行该真实库复验。
