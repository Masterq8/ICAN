# P4.6 v2 新论文质量门禁

结论：**FAILED**。8 篇全新 QASPER train 论文只调用一次 `deepseek-v4-pro`，不重试；工具提交成功 5/8。

## 冻结指标

- 工具提交成功率：62.5% (5/8)，门槛 87.5%。
- 原文支持率：92.3% (60/65)，门槛 90%。
- 字段归类正确率：96.9% (63/65)，门槛 85%。
- 缺失字段识别率：94.1% (16/17)，门槛 85%。
- 补充字段存在性准确率：62.5% (45/72)。

审核身份：ai；AI 审核 completed；人工审核 pending。

## 失败诊断

3 篇在 completion tokens 恰好达到 2048 后没有形成工具调用，SDK 将响应标为不完整并记录为 `ModelUnavailable/runtime_error`。这是根据用量和缺失工具动作作出的最大输出耗尽推断；旧运行未保存 finish_reason，因此不把该推断写成已证实的服务端原因，也不重跑。

| 样本 | 运行 | 工具诊断 | 原始字段数 | 错误类别 |
|---|---:|---|---:|---|
| gaussian_priors | failed | runtime_error | 0 | provider_or_payload |
| urban_legends | completed | accepted | 17 | — |
| linguistic_hedges | completed | accepted | 7 | — |
| grail_prover | completed | accepted | 14 | — |
| syntactic_structures | completed | accepted | 12 | — |
| rnn_domain_adaptation | failed | runtime_error | 0 | provider_or_payload |
| attsum | failed | runtime_error | 0 | provider_or_payload |
| causal_statements | completed | accepted | 15 | — |

## 门禁处理

工具提交成功率未达到预先冻结的 7/8，因此 P4.6 v2 不通过。原文支持率、字段归类和缺失识别即使通过，也不能覆盖生成阶段的失败。按设计进入高置信结果与同论文人工查证降级流程，不扩大样本、不重跑旧题。

## 审计身份

- 运行源码提交：`5a4bd98fc0518e85d61c2f7e3e689527f92bcad5`。
- 模型：`deepseek-v4-pro`；调用 8 次；输入 19008 tokens；输出 13335 tokens。
- seal：`f76a40870923094c80b497e687fd30a3e7ffa299de660588f9d532ba96b14533`。
