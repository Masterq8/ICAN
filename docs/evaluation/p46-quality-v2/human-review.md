# P4.6 v2 人工复核工作表

**人工复核已完成。** 用户逐 occurrence 对照 `review-input.json` 中的原字段、绑定证据与 `presence_decisions`，更新了 `manual-review.json`；身份为 `human`，状态为 `completed`。封存与review-input哈希绑定已由finalize验证通过。

如果今后需要更正本轮人工判断，编辑完成后再次执行以下命令重算：

```powershell
conda run -n ican python scripts/evaluate_research_cards_v2.py finalize --config configs/evaluation/p46-quality-v2.json
```

finalize 会重新检查 seal、原始字段哈希、72 个存在性槽位和三项审核产物绑定后重算。
