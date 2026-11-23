# P13-2 金标标注指南 v1

## 1. signal 与非 signal 的边界

**signal**（可提取信号）：
- 表达了对产品功能、体验、内容、价格等方面的可操作反馈
- 用户明确说出了"希望/需要/建议/抱怨/喜欢"某个具体事项
- 包含了至少一个可用于产品决策的意图或需求方向
- AIGC 视频模式：捕捉了创作者可以用来改进内容的可操作技术/策略/规律

**非 signal**（不提取）：
- 纯情绪表达，没有具体指向（"太烂了"但不说明哪里烂）
- 闲聊、问候、无实质内容的感谢
- 机器人/垃圾/重复模板文本
- 完全不涉及产品/AIGC 创作的话题
- 仅有链接/图片引用，无文字描述

## 2. signal_type 定义与正反例

### product_feedback profile

| 类型 | 含义 | 正例 | 反例 |
| --- | --- | --- | --- |
| `feature_request` | 请求新增或改进功能 | "希望增加暗黑模式" | "这个功能很好"（是 praise） |
| `bug_report` | 报告产品缺陷 | "点击提交按钮无反应" | "我觉得这个不好用"（太模糊） |
| `usability_issue` | 使用不便但不是 bug | "菜单层级太深，找不到设置" | "界面不好看"（太模糊） |
| `question` | 询问产品相关问题 | "怎么导出数据？" | "你们公司在哪里？"（不是产品问题） |
| `praise` | 具体正面评价 | "导出功能做得很好用" | "不错"（太模糊） |
| `complaint` | 具体不满或投诉 | "价格上涨太频繁，才续费又涨价" | "垃圾"（太模糊） |
| `churn_risk` | 有流失风险的表态 | "再这样我就换竞品了" | "考虑一下"（太模糊） |

### aigc_video profile

| 类型 | 含义 |
| --- | --- |
| `viral_hook` | 爆款开头/钩子技巧 |
| `content_pattern` | 内容模式/选题策略 |
| `visual_technique` | 视觉技术/特效 |
| `audio_strategy` | 音频/BGM 策略 |
| `engagement_trigger` | 互动引导技巧 |
| `platform_algorithm` | 平台算法观察 |
| `topic_trend` | 话题趋势 |
| `monetization_pattern` | 变现模式 |

## 3. evidence 区间标注规范

- 使用 `[start, end)` 半开区间，标记 `redacted_text` 中的位置
- `start` 是证据片段第一个字符的索引（含），`end` 是最后一个字符的后一位（不含）
- 验证器将检查 `redacted_text[start:end] == evidence_text`
- 中文和 Unicode 字符按 Python 字符串索引（code point 级别）
- evidence 必须逐字引用原文，不得改写、不得概括
- 如证据跨越多句，可以使用多段 EvidenceSpan

## 4. 显式需求、隐含需求、有依据推断和无依据幻觉

- **显式需求**：用户直接说出（"我想导出数据"）
- **隐含需求（有依据）**：`implicitNeed` 可以从 evidence 合理推断
  - 例：用户说"每次都要手动复制粘贴"→ 隐含需求："需要批量导出功能"
  - `implicit_need_has_basis = true`
- **无依据幻觉**：标注员无法从原文找到推断依据
  - `hallucination = true`
  - `implicit_need_has_basis = false`

## 5. 一条文本包含多个信号时的拆分

- 每个独立的可操作反馈都应作为单独信号标注
- 如果用户在同一句话提了两个不相关的问题，标注为两条信号
- evidence 必须独立，不能共享同一个 span

## 6. 边界情况处理

- **冲突**：同一段文字表达了矛盾的观点时，分别标注，在 notes 注明冲突
- **信息不足**：标记为 `has_signals=false`，不强行提取
- **讽刺**：以字面含义为准，在 notes 注明
- **转述**：如果用户转述他人观点，标注为对应信号
- **重复**：同一 content_hash 的反馈只在标注集中出现一次
- **跨句 evidence**：使用多段 EvidenceSpan

## 7. 标注员信息隔离规则

**所有标注员都不得查看**：
- `model_self_score`
- `calibrated_confidence`
- 任何置信度字段

### assisted_review（development + calibration）

- ✅ 可以查看明确标记的预标注 suggestion
- ❌ 不得查看 suggestion_model（模型身份）
- ❌ 不得查看模型自评分
- 人工必须确认或修改，不能一键默认接受
- 接受 suggestion 时需要显式标记 action

### blind（test）

- ❌ 不得查看任何 prediction、suggestion、模型身份、prompt 版本、模型分数
- 完全独立标注
- 标注包在导出时会递归清除上述所有字段

## 8. 双标规则

- 数量：不少于 `max(20, ceil(总样本数 × 20%))`
- 优先从 25 条 test 中选择
- A 和 B 独立完成标注后，比较一致性
- 分歧不裁决，现阶段保留原始 A/B 标签
- 向 A 展示的标注包中不得包含 B 的标签，反之亦然
- A/B 的标注员槽位真实身份不得存在于导出文件中
