# 📦 SignalMiner 项目存档索引

> **项目周期**: 2026-05-09 ~ 2026-05-30
> **协作模式**: 双 AI 协作 (Commander + Executor)
> **总阶段数**: 7 (Phase 0 ~ Phase 6)

---

## 📁 目录结构

```
docs/archive/
├── README.md                          ← 本文件（存档索引）
├── commander-instructions/            ← 指挥官下达的执行指令
│   ├── phase-3-instruction.md
│   ├── phase-4-instruction.md
│   ├── phase-5-instruction.md
│   └── phase-6-instruction.md
├── commander-reviews/                 ← 指挥官的验收审查报告
│   ├── phase-3-review.md
│   ├── phase-4-review.md
│   ├── phase-5-review.md
│   └── phase-6-review.md
└── delivery-reports/                  ← 执行者提交的交付报告
    ├── phase-3-prd-generator-report.md
    ├── phase-3-rework-report.md
    ├── phase-4-connectors-report.md
    ├── phase-5-frontend-report.md
    └── phase-6-production-report.md
```

---

## 📋 全阶段追溯表

| Phase | 名称 | 指挥官指令 | 执行者交付 | 指挥官审查 | 首轮通过 | 返工次数 |
|-------|------|-----------|-----------|-----------|----------|----------|
| **0** | 工程基础加固 | *(口头指令)* | *(口头汇报)* | *(口头验收)* | ✅ | 0 |
| **1** | Pipeline 健壮性 | *(口头指令)* | *(口头汇报)* | *(口头验收)* | ✅ | 0 |
| **2** | 证据链闭环 | *(口头指令)* | *(口头汇报)* | *(口头验收)* | ✅ | 0 |
| **3** | PRD 生成器与导出 | [phase-3-instruction.md](commander-instructions/phase-3-instruction.md) | [初次交付](delivery-reports/phase-3-prd-generator-report.md) / [返工交付](delivery-reports/phase-3-rework-report.md) | [phase-3-review.md](commander-reviews/phase-3-review.md) | ❌ | 1 |
| **4** | 多源连接器 | [phase-4-instruction.md](commander-instructions/phase-4-instruction.md) | [phase-4-connectors-report.md](delivery-reports/phase-4-connectors-report.md) | [phase-4-review.md](commander-reviews/phase-4-review.md) | ✅ | 0 |
| **5** | 前端升级 | [phase-5-instruction.md](commander-instructions/phase-5-instruction.md) | [phase-5-frontend-report.md](delivery-reports/phase-5-frontend-report.md) | [phase-5-review.md](commander-reviews/phase-5-review.md) | ❌ | 1 |
| **6** | 生产化准备 | [phase-6-instruction.md](commander-instructions/phase-6-instruction.md) | [phase-6-production-report.md](delivery-reports/phase-6-production-report.md) | [phase-6-review.md](commander-reviews/phase-6-review.md) | ✅ | 0 |

---

## 🔍 返工原因速查

### Phase 3 返工 (1 次)
- **问题**: PRD 生成器 Prompt 模板格式错误 + 测试 mock 不完整
- **详见**: [phase-3-review.md](commander-reviews/phase-3-review.md)

### Phase 5 返工 (1 次)
- **Bug #1**: `app.js:L343` — 模板字面量 `${...}` 缺少 `$` 前缀，信号置信度显示为原始代码文本
- **Bug #2**: `app.js:L217` — POST body 多包了一层 `{body: {...}}`，导致手动导入 422 错误
- **Bug #3**: `app.js:L324` — 置信度滑块值未传入 API 请求
- **详见**: [phase-5-review.md](commander-reviews/phase-5-review.md)

---

## 📊 项目统计

| 指标 | 数值 |
|------|------|
| 总阶段数 | 7 |
| 一次通过率 | 5/7 (71.4%) |
| 累计返工次数 | 2 |
| 累计测试用例 | 42+ |
| 指挥官审查报告 | 4 份 |
| 执行者交付报告 | 5 份 (含 1 份返工) |
| 指挥官执行指令 | 4 份 |

---

*存档生成于: 2026-05-30 by Commander AI*
