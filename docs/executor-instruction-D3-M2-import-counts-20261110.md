# D3-M2 执行指令：修正真实材料重复导入计数

日期：2026-11-10。

## 任务目标

只修正批量导入的新增/重复数量，使响应与实际数据库行为一致；不改采集、登录、浏览器、来源身份或模型流程。

## 背景 / 真实复现

用户明确使用其当前普通Chrome页面，不新开独立窗口、不再处理登录。Commander已停止专用任务，通过原Chrome界面读取国内小红书1篇正文和3条已加载评论，生成 `outputs/D3-M2/commander-20261110/xhs-existing-chrome-batch.json`。

在独立18817/acceptance.sqlite通过现有POST `/api/v1/feedback/batch`导入：首次 total4/ingested4/duplicates0。重复提交同一包后仍报告ingested4/duplicates0，但feedback_ids完全相同，数据库仍只有4条，四条快照verified且没有改写。实际去重正常，API数量虚报新增。routes/feedback.py的duplicates当前始终为0。

这是本次真实爬取材料验收暴露的问题。Commander已在本机执行断言并失败，不能把该失败计为测试通过。

## 允许修改范围

- `signal_miner/routes/feedback.py`
- `signal_miner/pipeline/runner.py`（仅在需要准确获知事务实际插入结果时，小范围提供兼容的结果信息）
- 新增专用测试文件，例如 `tests/test_feedback_batch_counts_D3.py`
- 本次交付报告 `docs/delivery-D3-M2-import-counts-20261110.md`

## 禁止修改范围

任何登录、域名、专用窗口/Chrome连接、上游、diagnostic、来源去重键/快照规则、模型调用、业务库、.env和系统设置。不得自行接触真实平台或使用Commander隔离库写测试；不得新增代理。

## 实现要求

1. 统计基于本次真实插入/复用结果；不能把非空ID当新增，也不能仅凭请求前存在性查询在竞态中误报新增。
2. 首次全新4项为4新增0重复；相同4项再次提交为0新增4重复；混合新旧和同一请求内重复逐项正确统计。
3. 保持原有 `ingest_feedback(...) -> str` 调用兼容，以及按输入顺序返回实际feedback_ids；不改变单条接口原有行为。
4. 原来源快照、重复复用ID、legacy分支及IntegrityError并发胜出复用不被改写；统计失败不能吞掉真正数据库错误。
5. 只做这一项，不扩展为新采集架构或恢复独立浏览器。用户已经提供当前Chrome，后续采集验证由Commander执行。

## 验收标准

### 静态检查

修改文件Ruff/compile通过，每条命令检查退出码。

### 功能验证

在独立测试库验证全新、重复、混合、请求内重复、legacy复用、事务竞态胜出复用的计数和ID语义；快照与原文不变，行数符合数量。包含失败传播和批次预校验行为，不用mirror实现的断言代替数据库效果。

### 回归验证

保留原437项、Node26项、历史36测试SHA不变。新增测试单独列明。不要修改/削弱旧用例或把未跑项写成通过。

### 交付门禁

报告列精确文件、实际命令/退出码/总数、兼容性、未完成项。代码稳定后尽快报告，交付后停止编辑。Commander会在真实4条材料的同一个隔离库复验重复计数、ID和快照。
