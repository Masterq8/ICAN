# P4.3 科研核查、筛选与报告使用说明

P4.3 将结论分成可验证类别。系统不会因为模型给出了引用 ID 就标记结论成立；尤其是代码运行结论会先检查被引用代码范围内的静态 `assert` 条件。

## 结论状态

| 状态 | 含义 |
|---|---|
| `supported` | 此类型要求的本地核查通过，且来源未标记人工复核 |
| `blocked_by_precondition` | 已知前置断言为假，不能把后续计算称为实际执行结果 |
| `insufficient_evidence` | 引用、quote、计算、bindings 或静态条件不完整／不支持 |
| `requires_review` | 推断类结论，或引用来源本身标记需复核；不会自动升级为已确认 |

`supported` 不代表完整训练或仓库已经运行成功，也不代表自由文本的语义蕴含已经被证明。

## 直接核查 API

启动服务：

```powershell
conda activate ican
python scripts/serve_api.py
```

在 Swagger 的 `POST /v1/research/verify-claims` 中提交固定检索范围和候选结论。以下案例验证 Swin-T 将输入尺寸改为112后，第三次下采样前的7×7网格不满足偶数断言：

```json
{
  "scope": {
    "query": "Swin-T 112 input PatchMerging assertion",
    "collection": "swin_v1",
    "family": "swin_v1",
    "filters": {"source_types": ["code"]}
  },
  "claims": [
    {
      "statement": "7×7 网格可以继续执行 PatchMerging。",
      "kind": "code_execution",
      "evidence_ids": ["chunk:3a345ff050583924611f5ed650c251769c521400e551fd9701ade11b670ec16e"],
      "conditions": [
        {
          "chunk_id": "chunk:3a345ff050583924611f5ed650c251769c521400e551fd9701ade11b670ec16e",
          "bindings": {"H": 7, "W": 7}
        }
      ]
    }
  ]
}
```

返回应包含 `blocked_by_precondition`，并定位 `H % 2 == 0 and W % 2 == 0`。同一代码块还有 `L == H * W` 断言；没有提供 L 时该项是 `unsupported`，但已知偶数条件失败足以阻断“可以执行”的结论。

四种 `kind` 的输入要求如下：

- `verbatim`：提供 `quote`，它必须在每个指定原始 chunk 中精确出现。
- `numeric`：提供 `calculation.expression`，系统按有界 Decimal 算术重算，且必须有范围内证据 ID。
- `code_execution`：提供至少一个 `conditions`。仅支持数值 bindings、基本算术、比较与布尔表达式；不会导入或执行仓库代码。
- `inference`：只验证证据 ID 的来源与范围，始终返回 `requires_review`。

## 筛选、提取与报告

`POST /v1/research/screening` 接收 `scope` 与 `draft`，保存纳入、排除或待定决定。`POST /v1/research/extraction` 保存以下固定字段：task、model、dataset、input_setting、training、metric、result、limitation、code_availability。每个字段至少有一个 Claim。

所有保存操作生成新的 UUID revision；通过 `revision_of` 指向旧记录，不会覆盖旧内容。记录写到本机忽略目录 `data/processed/research/p4-v1/records/`。用 `POST /v1/research/report` 传入 1–10 个 revision UUID 可得到 Markdown；报告会显示不足、阻断和人工复核项，而不会把它们隐藏掉。

Agent 也可调用 `verify_claims`、`record_screening`、`record_extraction` 与 `build_research_report`。前三者只接受当前任务证据池中的 chunk ID；报告仅接受已保存的 UUID。P4.3 没有启动新的真实模型批量评测，P4.4 再另行设置预算与外部回归。
