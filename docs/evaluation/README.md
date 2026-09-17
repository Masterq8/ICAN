# P2.6 审核记录

这些文件保存本轮助手逐题判断、理由与结果汇总；不是人类独立复核。

- `p26-root-review.jsonl`：Swin dev两版24条及QASPER train两版6条，含固定评分点的0/1覆盖。
- `p26-qasper-review.jsonl`：独立审查助手核对QASPER validation两版64条。
- `p26-audit-manifest.json`：固定参考输入、检索快照、实际生成journal及以上审核文件的SHA。
- `p26-acceptance-summary.json`：官方指标、助手判断分布、分母、用量及标明价格假设的费用估算；实付未知为null。

本机原始run位于`data/processed/evaluation/p26-v2`，被Git忽略。`scripts/finalize_baseline_audit.py`只合并明确写出的判定，不自动评分、不调用模型；需恢复完全相同的材料和journal，hash匹配后方可重建。另一轮生成即使题目相同也必须新审核，不能沿用本轮判定。

## 判断口径

`answer_judgment`为完整、部分、错误、拒答或参考歧义。参考有冲突时保留歧义；拒答标记与语义上的拒答另记。`citation_support`判断实质结论是否被实际引用原文支持，包括模型、实验及版本范围；没有实质答案可记not_applicable。支持率按答句统计，排除not_applicable，不把段落重叠算语义支持。

`semantic_status_correct`只判断可答性／拒答边界，证据或参考歧义／未能可靠赋状态时为null。Swin仅明确拒答有该项，不能由其子集推全12题状态准确率。既定评分点覆盖不排除额外错误主张，所以四点全中仍可能只判部分正确。

词面F1、段落覆盖、引用格式、语义完整性与语义支持各自衡量不同问题，详见[基线报告](../p2-baseline-report.md)。
