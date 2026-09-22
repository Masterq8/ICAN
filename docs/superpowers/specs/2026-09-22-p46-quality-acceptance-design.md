# P4.6 定向质量验收设计

## 目标与边界

用 8 篇从未进入既有真实运行产物的 QASPER train 论文，验收一次调用生成实验信息卡的质量。每篇论文只允许一次 `deepseek-flash` 调用，不自动重试，不用旧题修饰结果。完整原始动作、解析诊断和人工审核互相独立保存。

本轮不扩展语料、不运行 QASPER validation、不修改冻结 Swin 测试集，也不根据审核答案重新生成同一论文。

## 样本与运行身份

- 固定 8 个 `source_id`、论文标题、统一研究问题、当前 source version、检索 index fingerprint、6 条证据 ID 与文本 SHA-256。
- 样本须不出现在既有 P4.6 真实运行的 request／started／trace 产物中。
- 每个样本在调用前写入 started marker；已有 marker 或结果时拒绝再次运行。
- 使用独立目录、独立记录库和 8 次调用上限。原始 trace 留在忽略的运行目录；冻结清单、人工审核和汇总报告进入版本控制。

## 提交诊断

将模型动作依次诊断为：缺少工具调用、多工具调用、工具调用结构错误、工具名错误、arguments 类型错误、JSON 解析错误、schema 校验错误、越界证据 ID 或协议成功。诊断保留 Pydantic 的字段路径、错误类型和简化消息，不记录密钥或请求头。

“工具提交成功”只表示恰好一次正确工具调用、schema 合法且引用当前论文证据；语义错误单独计入字段归类指标，不能通过确定性规则改写成成功答案。

## 确定性字段规则

规则层保留原始字段和值，只为强冲突添加诊断：

- `dataset`：应是数据集、语料库、benchmark 或任务集合名称；若值只有 accuracy／F1／BLEU／WER 等度量词，提示应归为 `metric`；若值主要是分数或“outperform/achieve”结论，提示应归为 `result`。
- `metric`：应是评价度量名称；若值是带 dataset／corpus／benchmark 语境的资源名称且没有度量词，提示应归为 `dataset`；若包含具体分数或比较结论，提示应归为 `result`。
- `result`：应包含测得数值、比较关系或实验结论；若只有度量名称而无数值／比较／结论动词，提示应归为 `metric`；若只有数据集名称，提示应归为 `dataset`。

规则诊断写入字段记录和对照报告警告。规则不删除字段，不改变字段名，不计作人工正确。

## 人工审核与指标

审核员只查看模型实际收到的 6 条证据和原始提交，对每个样本标注九类字段在证据中是否存在，并逐条判断提交字段的引用支持和类型。保留运行前约定的成功提交口径（设计提交 `31fa99e`）：失败样本进入工具成功率分母，其字段指标不可审核，不当作零字段“全对”。

1. **工具提交成功率** = 协议成功样本数 / 8。
2. **原文支持率** = 成功卡片中被原文直接支持的字段数 / 成功卡片可审核字段数。
3. **字段归类正确率** = 成功卡片中类型正确的字段数 / 成功卡片可审核字段数。
4. **缺失字段识别率** = 成功卡片中审核判为缺失且模型省略的字段槽位数 / 成功卡片中审核判为缺失的槽位数。

运行后另加全部可解析草稿的补充口径，明确标记为事后增加，不替换原口径。包含被 schema 拒绝的原始字段，重复字段按 occurrence 分别审核；不可解析动作不进字段分母。缺失分母按每篇九类槽位计算。额外报告已有字段槽位覆盖率、混淆和遗漏；槽位覆盖不要求内容正确，不等于正确内容召回率。

当前标签是助手逐条初审，`reviewer_type=assistant`、`human_review_status=pending`，不得称为已完成人工审核。人工可对照 `human-review.md` 中的原始字段与全部输入证据修改审核文件；保留字段哈希后离线 `finalize` 重算，不产生模型调用。

## 产物

- `configs/evaluation/p46-quality-v1.json`：固定样本和查询。
- `data/processed/evaluation/p46-quality-v1/`：运行 manifest、started marker、原始 trace、卡片和调用 journal（Git 忽略）。
- `docs/evaluation/p46-quality-v1/manifest.json`：去除原文后的冻结身份与哈希。
- `docs/evaluation/p46-quality-v1/manual-review.json`：逐样本审核标签、审核身份与状态，当前为助手初审。
- `docs/evaluation/p46-quality-v1/human-review.md`：原始字段、判断理由和实际输入证据，供人类复核。
- `docs/evaluation/p46-quality-v1/run-seal.json`：运行后首次归档哈希，与真实运行源码提交 `2937a56` 绑定。
- `docs/evaluation/p46-quality-v1/report.md`：两种口径的四项指标、槽位覆盖、混淆和具体失败诊断。

## 验收条件

- 8 篇均为新论文且每篇最多一次调用。
- 任一失败可定位到具体协议／schema／证据或字段规则原因。
- 四项指标能由 manifest、raw result 和 manual review 重算。
- 确定性规则有单元测试，现有 P4.6/P5 接口兼容，全量测试与前端构建通过。
