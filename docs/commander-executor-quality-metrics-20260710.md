# Commander / Executor Quality Metrics

日期：2026-07-10

适用阶段：P13

最新样本：P13-2-2-2A fix-5，Commander 复验 PASS

## 当前高频缺陷

| 缺陷类别 | 累计观察次数 | 最近实际表现 | 原门禁效果 | 下一次强制门禁 |
| --- | ---: | --- | --- | --- |
| 验证脚本假阳性 / 关键行为未参与顶层 passed | 22 | fix-5丢弃RUNNING marker发布error，marker未写仍执行gate并exit0/COMMITTED | **再次复发** | MarkerWriteResult强制检查；RUNNING readback成功前gate_calls必须0 |
| 交付报告与代码 / 机器结果漂移 | 16 | 报告称旧绿色不会保留；marker持续失败时旧COMMITTED仍在且summary谎称no green metrics left | **再次复发** | FAILED marker readback结果驱动summary；失败时明确FAILED_MARKER_WRITE_FAILED |
| 契约测试缺少真实负例 | 13 | 31项测试未覆盖RUNNING marker返回error和FAILED marker自身写失败 | **再次复发** | 8类marker主路径负例，断言gate_calls、stdout/stderr和实际落盘 |
| 浏览器证据退化为源码检查 | 3 | fix-2 仍保留 `doSimpleVerify()` 和 `/app.js` 字符串检查 fallback | **无效，再次复发** | 删除 fallback；无浏览器 exit 非0/BLOCKED；实际 DOM false 必须 exit 1 |
| 状态文字与真实控制流不一致 | 2 | `embedding_failed` 被写为 semantic completed；`completed_with_skips` 未被 SSE/SPA 当终态 | **无效，再次复发** | 结构化 embedding result 单一真源；同测调用、事件、SSE关闭、UI终态 |
| mock / 样例 / 伪实现被描述为真实安全能力 | 2 | 内置fixture签名密钥仅靠`--fixture`即可在production启用 | **再次复发** | environment=test + fixture + 显式注入测试密钥三重约束 |
| 授权 / 来源真实性被采集方式替代 | 6 | signed manifest含dataset SHA但import可省略实际dataset manifest，消费端跳过重算 | **再次复发，P0** | dataset manifest参数强制required且每次导入独立重算 |
| 算法测试替代业务准确率评测 | 路线风险 | 单元测试全绿仍不能说明 1,408 dismissed 的历史结果可信 | 尚未进入对应阶段 | P13-2 至 P13-4 使用人工金标、冻结集和业务指标 |
| 永久累积被误报为数据生命周期管理 | 路线风险 | P13-1 保留旧数据，但仍没有 run/dataset/release 边界 | 尚未进入对应阶段 | P13-5 强制 snapshot、candidate/active/superseded、原子发布和回滚负例 |

## P13-1 样本事实

独立验收确认以下基础项通过：

- Ruff、Node 语法、`git diff --check` 通过。
- 聚焦测试 19 项通过，全量回归 191 项通过。
- 临时数据库迁移往返成功；RawFeedback 1257、Signal 1425、Theme 17、dismissed 1408 前后守恒。
- `calibrated_confidence` 没有被伪填充。

但以下行为推翻执行方 PASS：

- `model_self_score=0.49` 在 legacy threshold 0.50 下不入库。
- `embedding_status=skipped_no_real_embedding` 时 dedup 和 cluster 的 await count 均为 1。
- 两套前端仍显示裸“最低置信度”。
- `metrics.json` 的 regression 没有实际运行关联，多个 gate 只检查源码文字。

因此“测试全绿”和“JSON 七项 true”在本样本中都不是充分验收证据。

## 缺陷率目标

高频缺陷目标率仍为 5%。有效判定：

- 后续 20 个 blocker 样本中某类别不超过 1 次；或
- 后续 10 次交付中该类别 0 复发。

fix-1 中“验证脚本假阳性”“报告漂移”“负例覆盖不足”“浏览器源码 fallback”“状态与控制流不一致”全部再次出现。原防复发门禁判定为无效，fix-2 必须改为独立行为 probe 和矛盾数据硬失败，不再接受退出码推导观测值。

## P13-1 fix-1 防复发门禁

### 1. 置信度门禁

- 临时数据库中合法低分信号必须真实入库。
- legacy threshold 即使为 0.99 也不能改变入库结果。
- `model_self_score`、`calibrated_confidence`、method、model version 必须从持久化记录读取验证。

### 2. 语义熔断门禁

- no-real-embedding 时 dedup / cluster / asset await count 必须为 0。
- 同时断言事件序列没有语义阶段 running，最终状态为带 skip 的非全成功状态。
- 运行前后 new pseudo / dismissed / themes delta 必须为 0。

### 3. 机器证据门禁

- required gate 集合精确匹配；缺一个也 FAIL。
- regression 来自本次脚本启动的 pytest 子进程退出码。
- 禁止 `inspect.getsource()`、注释搜索、字符串存在性和硬编码 true 作为行为通过依据。
- 至少用 mutation/monkeypatch 证明错误实现会让验收脚本非 0。

### 4. 浏览器门禁

- 使用本次代码新启动服务，保存 host、port、URL、PNG 和 DOM 断言。
- 同时检查信号页、Pipeline skip 结果、AI 模型状态、来源按钮和 AIGC profile。
- fallback 不得退化为源码检查；浏览器不可用必须 BLOCKED。

### 5. 报告一致性门禁

- 测试数从真实命令输出获得，不手写旧数字。
- Markdown 中的数据库值、delta、调用次数必须与同一次 `metrics.json` 完全一致。
- Commander 独立运行一条低分入库 probe 和一条 runner skip probe 后才能判 PASS。

## P13-1 fix-1 门禁效果评估

### 有效

- 低分入库门禁有效：0.01 + legacy 0.99 已真实入库。
- adapter 无 Embedding 能力的直接熔断门禁有效：三类语义调用为 0。
- test-only 环境边界门禁有效：development + flag 仍被阻断。

### 无效

- 语义熔断只覆盖 `supports_embedding=False`，没有覆盖真实调用全部失败。
- metrics 虽运行 pytest，但把退出码转换成未实际采集的业务观测，仍产生假阳性。
- JSON 内部矛盾没有参与顶层 passed。
- delta 门禁没有实现，正式库静态总数被命名为 deltas。
- 浏览器 verifier 仍保留源码 fallback。
- 报告一致性门禁没有执行，Ruff 和测试数继续漂移。

## P13-1 fix-2 强制升级门禁

1. `scripts/p13_1_behavior_probe.py` 或等价独立 probe 必须直接输出 all-failed/partial/exception 的数据库计数、await count、事件和终态。
2. metrics 不得从 pytest exit code推定 `await_count=0`；只能读取 probe 的真实字段。
3. 任一 gate 出现 `passed=true` 但关键 observation 为 false、0（当预期非0）或 UNKNOWN 时，聚合器必须非 0。
4. before、after 和数学 delta 三者必须同时存在；缺 `new_pseudo_embeddings/new_dismissed/new_themes` 即 FAIL。
5. `completed_with_skips` 必须同时通过 runner、SSE iterator、subscriber cleanup、SPA handler 和 Streamlit 状态读取测试。
6. 浏览器无能力时明确 BLOCKED 且非 0；源码 token 不能参与 frontend PASS。
7. 全量测试命令强制 `-o addopts='' -q`，机器解析不到正测试数即 FAIL。
8. 交付报告中的 Ruff、测试数、warnings、delta 和调用次数必须与同次 JSON 相等。

## P13-1 fix-2 门禁效果评估

### 有效

- 真实 embedding 全失败熔断有效：`stored_real_count=0`，dedup / cluster / asset await count 均为 0。
- metrics 主链路有效：低分入库、all-failed 熔断、delta 字段、正测试数和全量回归均参与顶层 `passed`。
- `completed_with_skips` 主路径有效：SSE 终态包含该状态，SPA 会关闭 EventSource 并显示 warning。
- SPA 实际 DOM 有效：无 `#pipe-confidence`，无裸“最低置信度”，信号卡显示“模型自评 ...（未校准）”，模型/多模态状态可见。

### 无效

- Streamlit 仍在两个 `/pipeline/run` payload 中发送 `confidence_threshold`，与报告声明不一致。
- browser verifier 仍保留源码 fallback，Playwright 不可用时可能用 `/app.js` token 代替真实 DOM 证据。
- 报告一致性门禁仍未完全生效，fix-3 必须加入静态断言：
  - `frontend/app.py` 不含请求字段字符串 `"confidence_threshold":`
  - `scripts/p13_1_browser_verify.js` 不含 `doSimpleVerify`、`app.js`、`http.get`

## P13-1 fix-3 强制升级门禁

1. 删除 Streamlit payload 中的 `confidence_threshold`，保留后端 deprecated 兼容接收。
2. 删除 browser verifier 源码 fallback；Playwright 不可用必须输出 BLOCKED JSON 并 exit 2。
3. DOM 断言 false 必须 exit 1，不能只打印 false。
4. 新增静态断言参与交付命令和 metrics 顶层通过条件。
5. 交付报告不得声明浏览器 PASS，除非有真实 DOM JSON 或截图。

## P13-1 fix-3 门禁效果评估

### 本次有效

- Streamlit 两个 `/pipeline/run` payload 已删除 `confidence_threshold`；静态断言和实际代码一致。
- browser verifier 已删除 `doSimpleVerify`、`app.js` 与 `http.get` 源码 fallback。
- Playwright 不可用时真实输出 `BLOCKED`、`passed=false` 并退出 2；DOM false 与异常路径退出 1。
- 四项静态契约参与 `metrics.json` 顶层 `passed`，严格 JSON 复算通过。
- 交付报告没有把缺失的浏览器运行证据写成 PASS；Commander 使用应用内浏览器补齐真实 DOM 复验。
- 24 项聚焦测试、196 项全量回归、行为探针、正式库 delta 与报告一致。

### 仍需观察

- “验证脚本假阳性 / 顶层 passed 漏关键行为”“报告漂移”“浏览器证据退化为源码检查”在本次没有复发，但尚未达到连续 10 次交付零复发或 20 个 blocker 样本不超过 1 次的长期有效阈值。
- P13-2 起继续保留确定性负例、机器 JSON 聚合、诚实 BLOCKED 和报告一致性门禁。

## P13-2-1 门禁效果评估

### 有效

- 交付报告诚实标记人工标签未开始、校准不允许、fixture与真实数据有区别。
- 基础50/25/25 split与test无suggestion方向正确。
- P13-1行为探针和215项全量回归未出现业务回归。

### 无效 / 复发

- 验证器把`manifest.passed`当hash有效，没有独立复算。
- Pydantic静默丢弃test泄漏字段后再扫描，产生假通过。
- evidence offset硬编码通过，double annotation只数列表长度。
- 测试未隔离，运行后`candidates.json`与`metrics.json`互相矛盾。
- 报告声称Ruff通过但独立命令退出非0；必需真实导出证据未执行。
- 原“精确负例 + 顶层passed”门禁判定为无效，fix必须升级为独立mutation CLI和artifact SHA守恒。

## P13-2-1 fix 门禁效果评估

### 有效

- 显式授权门禁有效：不再从采集方式推导授权，真实DB 1,257条全部因缺授权拒绝。
- 真实导出证据有效：exit2、eligible=0、rejection=1,257与报告一致。
- Ruff、210项全量测试、P13-1行为探针通过。
- strict extra schema和部分manifest重算已生效。

### 无效 / 再次复发

- mutation gate没有读取临时metrics的target check，任何overall失败都能冒充目标命中。
- A/B包缺失/损坏、dataset ID、blind hash、manifest modes/schema、未知suggestion等仍返回PASS。
- 聚焦测试和mutation gate继续改写项目machine evidence，未实现SHA守恒。
- 预标注脚本仍是固定模板，报告与代码不一致。
- source platform仍由capture/source type替代。

结论：fix-1门禁总体判定**无效**；fix-2必须采用“指定target check + 临时output + ≥30类独立mutation + artifact零污染”。

## P13-2-1 fix-2 门禁效果评估

### 有效

- 32类mutation已真正读取指定target check，不再使用overall fallback。
- 聚焦测试和mutation gate实现artifact零污染。
- source platform与capture method基础字段已拆分。
- A/B/dev/cal文件存在性、dataset identity、blind hash、精确split等基础门禁生效。
- 20项聚焦、216项全量回归、Ruff和P13-1行为探针通过。

### 无效 / 剩余盲区

- fixture signal type白名单与生产单一真源不一致，非法类型可PASS。
- A/B包内slot仍为none，pack只核对ID不核对冻结内容。
- source空值、capture manifest分布、fixture身份和通用model泄漏可PASS。
- 真实adapter入口仍无条件BLOCKED，没有可注入成功路径。
- manifest冲突时会覆盖并破坏原冻结文件。

结论：fix-2门禁判定**部分有效但未达验收**。fix-3不再泛化扩张，只补8个Commander已复现的确定性缺口。

## P13-2-1 fix-3 门禁效果评估

### 本次有效

- 生产signal type使用profile单一真源；非法类型独立负例被`suggestion_signal_types`捕获。
- A/B内部slot、pack逐字段一致性、source非空、capture分布、fixture身份和通用model泄漏均通过Commander独立负例。
- manifest冲突拒绝时原文件完整SHA-256不变。
- fake adapter成功路径可执行，非法类型被拒绝；无key保持诚实BLOCKED。
- 40类mutation全部读取指定target check，Commander复跑40/40。
- 28项聚焦测试与mutation gate对其他artifact零污染。
- 224项全量回归、Ruff、diff和P13-1行为探针通过。

### 长期效果状态

- fix-3本次没有复发“验证假阳性、报告漂移、负例空壳、来源/capture混淆”。
- 但尚未达到连续10次交付零复发或20个blocker样本≤1次的长期有效阈值，因此长期防复发结论仍为**未充分证明**。
- P13-2-2-1继续沿用target-check mutation、artifact SHA守恒、真实BLOCKED不得冒充PASS三类门禁。

## P13-2-2-1 门禁效果评估

### 有效

- fixture与真实数据状态分离，真实候选0保持BLOCKED，人工计数保持0。
- Ruff、18项聚焦、242项全量回归和P13-1行为探针通过。
- 常规schema、导入与A/B工具链没有发现回归。

### 无效 / 复发

- mutation gate对`calibration_flag_ignored`手工反转detected，对零候选正常exit2也计作detected，23/23为假阳性。
- validator硬编码`cal_allowed=False`，没有验证可变阶段策略边界。
- 恒定全真/全假标签的退化Cohen's κ返回1.0，可错误满足READY。
- 报告声明的`human-annotation-contract-metrics.json`实际缺失。

结论：P13-2-1 fix-3要求的target-check与诚实BLOCKED防复发规则在本阶段再次被绕过，长期门禁仍判定**无效**。P13-2-2-1 fix必须统一mutation判定、将readiness invariant分账并增加退化κ负例。

## P13-2-2-1 fix 门禁效果评估

### 有效

- validator mutation 已统一采用 exit 1 + target存在 + target false。
- 零候选已从mutation分母移出并独立验证exit 2/BLOCKED。
- 退化κ全true/全false返回-1.0并由正式check阻断。
- calibration阶段策略已成为可变输入；true、缺失、类型错误均失败。
- 25项聚焦、249项全量回归、P13-1行为探针通过。

### 无效 / 再次复发

- importer mutation没有读取正式报告的target check，仍用exit 1推导并硬编码`check_exists=true`。
- 交付报告声称contract metrics包含mutation明细和invariant，实际内容不符。

结论：上一轮对validator路径的修复有效，但高频“验证脚本假阳性”和“报告漂移”仍在importer路径复发，整体门禁继续判定**无效**。fix-2必须让importer正式输出结构化checks，并增加无关错误不能冒充目标命中的元负例。

## P13-2-2-1 fix-2 门禁效果评估

### 有效

- Importer 正式输出12类结构化checks；mutation runner从同次报告读取target。
- exit 1但target true/缺失/仅无关check失败/报告缺失损坏等5类元负例有效。
- 36项聚焦、260项全量回归、P13-1行为探针通过。
- 退化κ、stage policy与readiness invariant保持有效。

### 无效 / 新确认阻断

- `fixture_provenance`业务check只依赖annotation ID关键词，未对比冻结task已有的`fixture=true`。
- Commander把fixture annotation改成普通ID并设`fixture=false`后，正式importer exit 0、passed=true并写入store。
- 该输入随后可被validator计为真实人工标签，直接污染最高优先级置信度依据。

结论：fix-2的“target-check真值化”技术门禁本身**本次有效**，但它验证了一个错误的来源规则；整体阶段仍不通过。fix-3必须把fixture provenance绑定冻结task/pack字段与task hash，禁止继续使用命名启发式作为安全边界。

## P13-2-2-1 fix-3 门禁效果评估

### 有效

- annotation侧普通ID/UUID改名不再绕过，fixture身份改为读取task结构化字段。
- task hash生成函数已把fixture纳入规范化输入。
- 41项聚焦、265项全量回归及既有30类mutation通过。

### 无效 / 再次复发

- Importer没有独立重算task hash，只比较annotation与task携带的同源旧hash。
- 整个pack和全部task fixture同步翻转、保留旧hash后，正式importer仍exit 0并写入`fixture=false`标签。
- fix-3任务书明确要求的“翻转task fixture但保留旧task hash”mutation未交付。

结论：名称启发式漏洞的局部修复有效，但冻结来源完整性链仍未闭环，整体门禁继续**无效**。fix-4必须在消费端重算task hash，并验证pack/task/annotation三层一致性。

## P13-2-2-1 fix-4 门禁效果评估

### 本次有效

- Importer从task规范字段独立重算expected task hash，并同时校验task与annotation hash。
- Commander整包fixture翻转+旧hash反例exit1，`dataset_identity=false`，store未创建。
- task与annotation同步为同一伪hash仍被expected hash阻断。
- pack/task fixture缺失、非bool、冲突继续由结构化check拒绝。
- 43项聚焦、267项全量回归、34/34 mutation、1/1 invariant、5/5 meta-negative通过。
- 本次没有复发退出码推导target、ID命名启发式或报告/evidence字段漂移。

### 长期效果状态

- fix-4证明“消费端独立重算”门禁对本次确定性反例有效。
- 高频验证假阳性和来源真实性缺陷尚未达到连续10次交付零复发或20个blocker样本不超过1次，因此长期效果仍为**未充分证明**。
- 普通SHA不提供发布者认证；下一阶段增加外部pack manifest签名/HMAC信任根，随后才允许真实人工标注入口。

## P13-2-2-1A 门禁效果评估

### 有效

- HMAC签名、pack SHA/bytes/count、路径和签名篡改基础检查已实现。
- 非fixture生产路径缺密钥时exit2/BLOCKED。
- 28项聚焦、295项全量及既有annotation mutation回归通过。

### 无效 / 再次复发

- `--fixture`不检查运行环境，production可直接使用公开测试密钥签名。
- fixture无manifest仍`pack_trust=true`并成功导入，外部信任根没有覆盖主fixture链路。
- `dev_mode_test_key_flag` mutation只是篡改签名载荷造成陈旧签名，未执行development环境边界。
- pack manifest未包含或验证dataset manifest hash。

结论：HMAC基础组件存在，但test-only边界和强制接入主链均未成立，整体门禁判定**无效**。fix必须强制signed manifest覆盖fixture，并用真实子进程环境验证测试密钥边界。

## P13-2-2-1A fix 门禁效果评估

### 有效

- production/development/空/staging环境真实子进程均拒绝fixture测试密钥。
- Runtime已删除默认测试密钥，test环境缺注入key为exit2/BLOCKED。
- Fixture缺pack manifest不再导入，store不创建。
- Manifest schema已加入dataset manifest路径和SHA字段。

### 无效 / 再次复发

- Importer可省略实际`--dataset-manifest`，verifier在None时跳过重算并成功导入。
- Fixture缺pack manifest仍exit2，mutation runner手工特殊放行并计入20/20。
- Contract metrics保留旧21/21和1项invariant，与本次20/20和2项invariant矛盾但顶层仍passed=true。

结论：测试密钥环境边界修复**本次有效**，但dataset来源消费链和证据聚合仍未闭环，整体阶段继续不通过。fix-2必须强制实际dataset manifest并恢复计数mutation统一exit1契约。

## P13-2-2-1A fix-2 门禁效果评估

### 有效

- Dataset manifest已强制消费；省略或文件缺失均exit1并阻止store创建。
- Fixture缺pack manifest改为exit1，23条pack mutation恢复统一严格判定。
- Contract metrics计数已同步为23/23、2项pack invariants和34/34 annotation。
- 22项pack、43项annotation、289项全量回归通过。

### 无效 / 再次复发

- 聚合器把final passed硬编码true，没有校验输入gate top-level passed及annotation meta/invariant false。
- Commander将三个annotation关键字段设false后，聚合器仍exit0、passed=true。
- run_id只在聚合完成后生成并写入metrics，没有绑定两个输入gate，无法证明同次运行。

结论：行为安全链修复**本次有效**，但机器证据聚合仍是假阳性，整体阶段继续不通过。fix-3仅需收口orchestrator与final passed复算。

## P13-2-2-1A fix-3 门禁效果评估

### 有效

- 顶层 passed 已纳入两个gate的passed、readiness invariant与annotation meta-negative严格布尔值；上一轮三个false字段反例已关闭。
- 单一orchestrator先生成run_id并启动两个gate，正式三份evidence run_id一致。
- 正式运行23/23 pack、34/34 annotation，78项聚焦、302项全量、Ruff、behavior probe和goldset验证通过。

### 无效 / 再次复发

- Orchestrator不验证必需mutation和invariant身份集合，任意1/1未知mutation与0个pack invariant仍exit0/passed=true。
- 临时gate SHA计算后再按路径读取复制，复制后不复核；Commander在SHA后把gate passed改false，最终仍passed=true且metrics SHA与实际artifact不符。
- 新增测试复制了一套验证逻辑而未调用真实main，且用1/1空壳作为正例；任务书要求的子进程伪绿、SHA变化、旧新evidence混用未覆盖真实主路径。
- 报告所称“原子拷贝”实际是两个顺序`write_text`，完整元负例声明与实现不一致。

结论：fix-3对上一轮直接阻断**局部有效**，但高频验证假阳性从“false字段漏AND”转移为“门禁集合可缩减”和“SHA发布竞态”，整体阶段仍不通过。fix-4必须使用23/34/2/1/5版本化精确集合、单一bytes snapshot、原子发布后复核和真实main端到端元负例。

## P13-2-2-1A fix-4 门禁效果评估

### 有效

- 23/34/2/1/5版本化exact-set对缺失、多余、重复、未知替换和1/1 coverage shrink均有效。
- Gate parse/validate/SHA/publish使用同一bytes snapshot；单次publish已使用临时文件、fsync、os.replace和立即readback。
- 83项聚焦、307项全量、Ruff、正式23/34 orchestrator、behavior probe和goldset通过。

### 无效 / 再次复发

- 第一个gate在publish返回后、metrics commit前被篡改，main仍exit0并发布passed=true，metrics SHA与实际gate不一致。
- Final metrics发布失败只追加error，仍打印PASS并exit0。
- 畸形mutation行触发KeyError后，上一轮passed=true metrics原样保留。
- phase、contract schema version和command均错误时仍passed=true。
- Fake runner测试直接覆盖正式evidence，最后的restore仍是fake绿色证据；仅运行pytest即可制造未执行真实gate的机器PASS。
- 报告将“exit0后篡改并观察SHA不同”误报为已阻断race，全量测试数306与Commander 307不一致。

结论：fix-4的exact-set优化**本次有效**，但Evidence事务提交和测试隔离门禁仍判定**无效**。fix-5只收口RUNNING/FAILED/COMMITTED状态、commit前后验证、最终发布错误返回码、畸形输入失败闭环和tmp_path测试隔离。

## P13-2-2-1A fix-5 门禁效果评估

### 有效

- Pre-commit篡改、COMMITTED metrics发布失败、畸形输入、metadata错误和post-commit单文件篡改均被主流程/verifier阻断。
- Fake runner测试已全部使用tmp_path；Commander独立验证聚焦测试前后正式三文件SHA零变化。
- 96项聚焦、320项全量、Ruff、正式23/34 orchestrator、committed verifier、behavior probe和goldset通过。

### 无效 / 再次复发

- `_write_running_marker`丢弃`_publish_atomic`错误；RUNNING未落盘仍执行两个gate并最终exit0/COMMITTED。
- `_write_failed_marker`丢弃发布错误；marker持续失败时旧COMMITTED/passed=true保留，summary仍打印`no green metrics left`。
- 31项契约测试没有覆盖RUNNING marker返回error或FAILED marker自身写失败，状态机入口和失败陈述再次形成假阳性。

结论：fix-5的commit前后验证、严格payload和测试隔离优化**本次有效**，但marker错误传播仍判定**无效**。fix-6只修MarkerWriteResult、RUNNING硬前置、FAILED readback和summary真实性，不得扩展重写。

## P13-2-2-1A fix-6 门禁效果评估

### 本次有效

- RUNNING marker发布error/readback错误均在gate前阻断；Commander独立反例exit1、gate_calls=0。
- COMMITTED与FAILED marker同时发布失败时，退出码为1，磁盘保持本次RUNNING/passed=false，summary明确`FAILED_MARKER_WRITE_FAILED`且不再宣称no green metrics left。
- MarkerWriteResult把publish error、readback SHA、run_id、status和passed统一纳入ok。
- 104项聚焦、328项全量、Ruff、正式23/34 orchestrator、committed verifier、behavior probe和goldset通过。
- 聚焦测试前后正式三份evidence SHA零变化。

### 长期效果状态

- fix-6没有复发“关键发布错误未参与返回码”“状态文字与真实落盘不一致”或“fake测试污染正式evidence”。
- 本次只形成一个成功样本，尚未达到连续10次交付零复发或20个blocker样本不超过1次的长期证明阈值；累计缺陷次数不回退，后续阶段继续强制marker、exit、SHA和测试隔离门禁。

结论：fix-6门禁**本次有效，P13-2-2-1A最终通过**。下一阶段仅允许P13-2-2-2A真实授权候选与人工标注启动准备；外部输入缺失时必须exit2/BLOCKED。

## P13-2-2-2A 首次交付门禁效果评估

### 本次有效

- 当前零真实授权候选、缺生产密钥和人工角色时，正式CLI诚实exit2/passed=false。
- `human_verified_count=0`、`human_labels_complete=false`、`calibration_allowed=false`保持有效。
- 未生成伪真实task pack或人工label；Ruff、48项聚焦测试、全量回归和diff check均通过。

### 无效 / 再次复发

- 直接信任导出自报`eligible_count`，没有与实际行数或授权完整行数重算对账；Commander用“声明100、实际99、完整授权0”得到exit0/READY/passed=true。
- 发现`authorization_incomplete_rows`后不产生error；相关N3测试只检查计数，不断言最终失败。
- 正式CLI不消费roles/splits/packs/治理窗口，READY路径也未接入1A签名/hash verifier；只有test override可以构造正例。
- 安全违规与输入缺失统一exit2；test blind泄漏没有按契约exit1。
- N1错测为声明99，N9未测A/B访问，N11被“缺生产密钥”替代，14类负例覆盖声明失真。
- artifact实际SHA、JSON内SHA和交付报告SHA三方不同；报告/状态与真实落盘结果不一致再次出现。

### 缺陷趋势

- “验证脚本假阳性/测试没有攻击真实判定”再次复发，新增1次P0样本。
- “报告或机器证据与最终落盘SHA不一致”再次复发，新增1次P1样本。
- “业务当前诚实BLOCKED”不能抵消 READY 正向路径的假绿；阶段整体不通过。

结论：当前业务阻塞陈述有效，但 readiness 安全门禁**无效**。fix只收口候选重算、正式输入消费、1A信任链复用、exit分类、真实负例与证据SHA，不得进入P13-2-2-2B。

## P13-2-2-2A fix 门禁效果评估

### 本次有效

- 声明100/实际99及授权缺字段假绿已关闭；无输入保持BLOCKED/exit2，已提供但无效数据可进入FAILED/exit1。
- 当前readiness JSON与sidecar SHA一致。
- 61项聚焦、389项全量、Ruff和diff check通过，正式evidence未被测试修改。

### 无效 / 再次复发

- READY没有dataset/pack manifest、签名、task hash或1A verifier check；四个identity/hash字段始终null。
- Commander正式CLI用25个空JSON、0个test task、无签名pack、无manifest仍READY/exit0。
- split可与候选零交集；双标与A/B访问边界只信任配置自报count/bool，没有从任务包重算。
- rejections声明999/实际0、非法captured_at与治理时间、访问角色不匹配仍READY。
- N11再次被“缺生产密钥”替代，N16没有独立生产verifier；正向测试把无信任链READY固化为预期。
- 交付报告同一文件同时保留当前`a844...`和旧`d930...` SHA，报告漂移再次复发。

### 缺陷趋势

- “验证脚本假阳性/关键check未参与passed”连续两次P13-2-2-2A交付复发，已达到五次内两次，按Commander规则判定优化无效；fix-2升级为正式CLI确定性门禁和1A单一真源复用。
- “报告/JSON/SHA漂移”连续两次复发，继续高于5%目标；fix-2要求全报告hash扫描与独立只读verifier。

结论：fix对上一轮count与exit问题局部有效，但READY信任链仍**无效**。fix-2只接入1A verifier并从真实任务重算split/盲标/双标/访问，不得继续用声明型字段作为安全事实。

## P13-2-2-2A fix-2 首次完成声明交付评估

### 实际状态

- 未发现fix-2交付报告。
- readiness脚本、测试和正式evidence均保持fix-2指令发布前的旧mtime与SHA。
- `--verify-evidence`仍为argparse未识别参数。
- readiness中不存在`verify_manifest_file`、`compute_task_hash`、dataset/pack manifest生产路径或新增结构化check。

### 缺陷趋势

- 新增“完成声明与工作区实际交付不一致”1次阻断。
- 本次没有新实现样本，不能评价fix-2技术门禁有效性；状态为**未执行/未证明**，不是通过或技术失败。
- 高风险假绿类别仍维持上一轮无效结论，直到真实fix-2落盘并接受Commander攻击。

结论：fix-2首次声明为**未交付**。继续执行同一fix-2，不升级技术范围；新增文件SHA变化、生产符号存在和交付报告存在性硬门禁。

## P13-2-2-2A fix-2 第二次完成声明交付评估

### 实际状态

- 生产脚本SHA仍为`57ca10c...`，测试SHA仍为`21f7685c...`，与第一次未交付核查完全相同。
- 只重新运行旧脚本刷新正式JSON/sidecar，并更新旧`delivery-fix`报告中的SHA。
- `--verify-evidence`仍未实现；1A verifier、task hash、manifest和真实任务重算仍未接入。
- 旧报告仍声明61/389旧测试，N11仍为缺密钥，N16仍无生产verifier。

### 缺陷趋势

- “完成声明与工作区实际交付不一致”连续两次复发，达到五次内两次的无效阈值。
- 交付存在性宽泛提醒判定无效；升级为生产符号rg、旧SHA不等式、新文件存在和真实CLI成功的确定性preflight。
- fix-2技术门禁仍未获得任何新实现样本，继续标记**未执行/未证明**。

结论：第二次提交仍为**未交付**，且通过刷新旧evidence/报告制造了表面变化。继续同一fix-2，强制preflight通过后才允许再次验收。

## P13-2-2-2A fix-2 第三次完成声明交付评估

### 本次有效

- fix-2 交付件存在，生产脚本与测试文件均已实际变化。
- `--verify-evidence`、focused ruff、`git diff --check`、35项聚焦pytest、363项全量pytest均通过。
- 当前无真实输入的正式evidence仍为 `BLOCKED_INPUT_REQUIRED / exit2`，JSON与sidecar SHA一致。

### 无效 / 再次复发

- 生产CLI反例中，将 `real-candidate-export.json` 第一条 `candidates[0].dataset_id` 改为 `ds_attacker_wrong` 后，仍得到 `READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true`。
- READY正例artifact中 `batch_id=null`，违反fix-2正向契约，也阻断后续批次审计和旧数据生命周期管理。
- 候选、split、task没有形成逐任务绑定门禁；task hash重算只证明task自身字段一致，不证明task来自授权candidate且split/content匹配。
- 双标阈值仍按test unique计算；正向测试只断言 `double_label_actual_count >= 1`，未覆盖 `max(20, ceil(authorized_candidate_count*20%))`。
- 交付报告测试SHA与实际测试文件SHA不一致，报告漂移再次复发。

### 缺陷趋势

- “验证脚本假阳性/关键check未参与passed”在P13-2-2-2A阶段继续复发，新增1个P0样本。
- “报告/JSON/SHA漂移”继续复发，新增1个P1样本。
- “测试覆盖不足导致契约未被断言”新增1个P1样本。

结论：fix-2已经从“未交付”进入“有实现但核心安全门禁仍无效”。下一轮升级为 **P13-2-2-2A fix-3：候选-任务绑定与批次身份闭环**，要求生产CLI级别反例，不再接受仅helper路径证明。

## P13-2-2-2A fix-3 完成声明交付评估

### 本次有效

- 生产CLI正例可得到 `READY_FOR_HUMAN_ANNOTATION / exit0 / passed=true`，且 `batch_id` 已非空。
- 候选行 `dataset_id` 错误已被 `real_candidates=false` 阻断。
- ghost task、task content_hash不匹配、A/B同sample content_hash不匹配均被 `task_candidate_binding=false` 阻断。
- 105候选但仅20双标已被 `required_double_label=21` 阻断。
- cross-split session group 已被 `group_isolation=false` 阻断。
- `--verify-evidence`、focused ruff、35项聚焦pytest、363项全量pytest、`git diff --check` 均通过。

### 无效 / 再次复发

- 未发现fix-3交付报告，无法对账执行方声明、SHA、负例证据和未覆盖风险。
- `batch_id` 只绑定dataset manifest、pack manifest和candidate export；修改governance后仍READY且batch_id不变。
- 单条candidate缺失全部group metadata仍READY，说明group隔离只检查“任意字段存在”，没有逐candidate必填门禁。
- naive governance datetime触发unexpected TypeError，最终 `check_passed={}`、`blockers=[]`，结构化target丢失。
- 测试文件仍标记fix-2，聚焦测试仍为35项，正向测试未断言batch_id、required_double_label和新增生产CLI反例。

### 缺陷趋势

- “验证脚本假阳性/关键契约未参与测试”继续复发，新增1个P0样本。
- “完成声明缺交付报告”新增1个P1样本。
- “结构化机器证据缺失”新增1个P1样本。

结论：fix-3有实质进展，但仍不通过。下一轮收窄为 **P13-2-2-2A fix-4：批次身份与group metadata结构化门禁**。

## P13-2-2-2A fix-4 完成声明交付评估

### 本次有效

- fix-4交付报告存在，脚本/测试/evidence SHA与当前文件一致。
- `batch_id` 已绑定7个component；governance、roles、rejections变化均导致batch_id变化。
- 单条candidate缺失session或conversation已被 `group_isolation=false` 阻断。
- naive governance datetime 已结构化失败，`annotation_governance=false`，无unexpected。
- `--verify-evidence`、focused ruff、42项聚焦pytest、370项全量pytest、`git diff --check` 均通过。

### 无效 / 再次复发

- 删除源candidate行的 `near_duplicate_group_id` 字段后仍READY；原因是candidate_index用 `cand.get()` 补出了key，丢失了源字段存在性。
- 非空 `near_duplicate_group_id` 同时出现在development与test后仍READY；实现直接跳过near_duplicate_group_id跨split检查。
- 交付报告将 near_duplicate cross-split 标为未覆盖风险，但Commander生产CLI证实它是实际假绿。

### 缺陷趋势

- “验证脚本假阳性/关键契约未参与测试”继续复发，新增1个P0样本。
- “未覆盖风险被证实为实际假绿”新增1个P0样本。

结论：fix-4在batch/session/timezone方向有效，但near-duplicate group仍不通过。下一轮收窄为 **P13-2-2-2A fix-5：near-duplicate group闭环**。

## P13-2-2-2A fix-5 提交前返工控制调整

### 当前预检

- 工作区已出现fix-5候选实现：源字段存在性标记和near-duplicate跨split检查已经落盘。
- Commander预检focused Ruff为exit0，readiness聚焦测试为44 passed。
- fix-5交付报告仍缺失；现有两个新增测试只断言目标列表非空，尚未精确断言缺失sample和跨split group内容。
- 当前状态是“候选实现待收口”，不是验收通过，也不应升级为fix-6。

### 降低返工的门禁调整

1. 冻结fix-5验收契约，不再增加near-duplicate之外的新业务要求。
2. 先补顶层状态、目标check和准确observation断言，再允许修改生产代码。
3. 把“完成声明”升级为提交资格门禁：交付报告、正式默认exit2、精确负例、全量回归、evidence SHA任一缺失时只能报告BLOCKED。
4. 后续统计分开记录“代码返工”“规格修订”“无实际交付”“报告缺失”，不再全部计为同一种返工。
5. 最新执行指令固定为`docs/deepseek-instruction-P13-2-2-2A-fix-5-finalization.md`。

结论：新的低返工门禁为**尚未证明有效**；需要在fix-5交付后由Commander独立复验，不能因指令已更新就提前判定有效。

## P13-2-2-2A fix-5 最终门禁效果评估

### 本次有效

- 源candidate只删除`near_duplicate_group_id`键后，正式主路径`FAILED_INVALID_INPUT/exit1`，准确sample进入`missing_group_rows`。
- 非空near-duplicate group跨development/test后，正式主路径`FAILED_INVALID_INPUT/exit1`，`cross_split_groups`准确包含字段、group值和两个split。
- READY正例、session/conversation、naive governance、7组件batch identity均未回退。
- Commander额外验证rejections文件语义不变但字节变化时，仍READY且rejections component SHA与batch_id同时变化。
- Ruff、44项聚焦、372项全量、正式默认exit2、evidence verifier和sidecar全部通过。

### 交付质量分类

- 交付报告的实际SHA均无错误或旧值；但未列sidecar SHA。
- 冻结契约结果表漏列rejections变化，Commander独立R3c探针实际通过。
- 两项归类为“交付文档不完整”，不计为代码返工，不阻断本阶段技术通过。

### 门禁效果结论

- 精确反例与顶层状态门禁：**本次有效**。
- 完成声明门禁：从“无报告/宽断言”改善为完整交付和精确断言，**本次基本有效**。
- 报告完整性门禁：仍有漏项，判定为**部分有效**。
- 长期复发控制：仅新增一个成功样本，尚未满足连续10次交付零复发或20个blocker样本不超过1次，继续标记**未充分证明**。

结论：P13-2-2-2A最终通过，不下发fix-6。下一阶段P13-2-2-2B为真实人工执行阶段，当前因真实授权数据和人工角色缺失保持INPUT-GATED/BLOCKED。
