# P4.6 第二轮 AI 复核与分歧裁定

## 身份与范围

2026-09-23，按用户要求由 Codex 逐条对照工作表，并调用 deepseek-v4-pro 给出辅助审核意见。**AI复核完成；不是人类审核，human_review_status仍为pending。** 全部59个原始字段、8篇×9类共72个字段存在性槽位均已检查。没有重新生成实验卡，也没有修改原运行成功／失败。

保留全部 occurrence、name、raw_field_sha256，以及原始字段值、quote、evidence_id。初审版本在 Git 提交 `bce693856d083aab26f09a173d3ebd9520d3b9e5`，本次修改可逐项追溯。当前标签见 [manual-review.json](manual-review.json)，原文及每类存在／缺失理由见 [工作表](human-review.md)。

## 审核方法及用量

- 第一轮：8次Pro调用，thinking=disabled，不提供初审标签。4份返回的occurrence序号不符合全局顺序；另发现布尔判断矛盾、字段存在性集合或证据摘录问题。原始回复及失败诊断均保留，未自动导入标签。
- 第二轮：8次Pro调用，thinking=enabled，显式提供occurrence，并依据第一轮与原文检查补充统一判定规则。未提供初审逐条标签，但规则已包含争议边界，因此这轮是定向辅助复核，不能称为盲测或独立泛化验证。
- 第二轮8份occurrence序列均正确；entity_coreference的数据集存在性摘录拼接了原文中的不同部分，仍不能直接充当精确引文。最终采用工作表中经本地逐字校验的连续原文。
- Codex逐条裁定，没有按模型投票或挑选更高分标签。模型建议与最终标签分开保存；支持判断和类型判断彼此独立。
- 共16次额外Pro审核：39,443输入token、90,129输出token（含供应商计入completion的思考用量）；实际货币费用未返回。原始8次Flash生成另为15,508输入／8,724输出token，不混算。
- [pro-review.json](pro-review.json)保存两轮提示、返回模型身份、使用量、调用journal、原始意见、诊断及输入／原始产物哈希。审核来源哈希由finalize检查；原生成run-seal未修改。

## 相比初审的实质修正

| 对象 | 初审 | 本次裁定 | 依据 |
|---|---|---|---|
| mobile_robot occurrence=1 | model正确 | model错误，建议input_setting | TurtleBot 2是实验硬件，所引段落没有给出算法模型 |
| mobile_robot的model存在性 | 存在 | 当前六段未提供 | 硬件／ROS平台及学习步骤不能补造论文模型身份 |
| ontology_parser的limitation存在性 | 缺失 | 存在，但卡片遗漏 | 原文明示未解析节点／句子的长尾 |
| speech_recognition的input_setting存在性 | 缺失 | 存在，但卡片遗漏 | 图注明示每个节点只识别指定词集合 |

此外，修正event_extraction的input_setting锚点为Whole data set／Abstracts only／Full papers only表注，修正russian_twitter的limitation锚点为增加语料和向量大小的条件式说明。全部59条理由改为具体中文说明，每个应有字段均附精确摘录，每个缺失类型均给理由。

## 保留的分歧与边界

1. **event_extraction occurrence=7：仍归result。** Pro两轮均倾向把“低但与其他系统相当”归limitation；该值只是成绩比较，没有明确适用约束或比较覆盖缺口，按主语义保留result。记录limitation为可争议替代解释，不隐藏分歧。
2. **russian_twitter occurrence=8：保留limitation。** “要获得更好结果需同时增大语料与向量”有明确的资源条件，比单纯低分比较更接近约束。也可读为结果解释／训练建议，因此保留原合理标签并标记歧义，而非强行降分。其所引段落足以支持文本。
3. **contextual_lstm occurrence=3：保留input_setting且原文支持。** 词表从训练语料构造，但字段主对象是输入表示／预处理；training也有解释空间，不能把分类歧义判成引文不支持。
4. **speech_recognition的task仍存在。** Pro思考轮认为缺少显式目标句；图注已有speech recognition任务名，不需要固定的“We aim to”句式。相反，活动词表题不足以证明dataset或training存在。
5. **speech_recognition occurrence=0：limitation是报告范围含义。** 更多结果留到最终论文表示当前披露不完整，不声称算法本身不能完成任务。
6. **引用支持按原字段自己的chunk判断。** 两个标题引用缺失、event_extraction把two改three、russian_twitter的task引错段，仍为四个不支持字段。其他位置能找到任务，不会自动修复错误引用。
7. 综述event_extraction中的结果、CLSTM的n-gram结果有归属差异：当前支持率衡量文本支持，不证明这些都是论文主方法的结果。后续实验卡应显式绑定方法—数据—指标—结果，避免误比较。

## 更新后的指标

下表是全部可解析原始草稿的补充口径，语义分数仍为AI裁定；预先约定的成功卡片口径继续保留在 [验收报告](report.md)。

| 指标 | 初审 | 第二轮复核 |
|---|---:|---:|
| 工具提交成功率 | 2/8（25.0%） | 2/8（25.0%） |
| 原文支持率 | 55/59（93.2%） | 55/59（93.2%） |
| 字段归类正确率 | 53/59（89.8%） | 52/59（88.1%） |
| 缺失字段识别率 | 16/17（94.1%） | 14/16（87.5%） |
| 已有字段槽位覆盖率 | 47/55（85.5%） | 46/56（82.1%） |

缺失识别分母从17变16，来自字段存在性修正，不是样本删减；字段总数保持59。槽位覆盖只统计原提交名称是否出现，不是正确内容召回率，不能用建议改名后重新计作提交成功。

## 结论与后续

P4.6产品质量仍未通过，原始工具提交仍为2/8。AI逐条复核完成，全部原始证据及模型意见可复查；人类确认仍独立保留。下一产品修复应处理同类字段多个条目及实验归属绑定，先用已有原始输出做离线回放；本次不扩展付费生成评测。
