# P4.6 v2 人工复核工作表

当前 AI 审核已完成，人工状态仍为 `pending`。人工复核时逐 occurrence 对照 `review-input.json` 的原字段、绑定证据与 `presence_decisions`；修改 `manual-review.json` 中的布尔判断、correct_type 和理由，不得修改 occurrence、name 或 raw_field_sha256。

完成后把 reviewer_type 改为 `human`、human_review_status 改为 `completed`，并执行：

```powershell
conda run -n ican python scripts/evaluate_research_cards_v2.py finalize --config configs/evaluation/p46-quality-v2.json
```

finalize 会重新检查 seal、原始字段哈希、72 个存在性槽位和三项审核产物绑定后重算。
