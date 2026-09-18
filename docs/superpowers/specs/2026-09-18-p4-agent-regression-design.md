# P4.4 Agent 开发集与外部回归设计

## 目标

以与 P4.2 分离的 32 次付费调用上限，验证 P4.3 的结构化核查是否在真实 Agent 轨迹中改善已知开发问题，并对固定外部 QASPER validation 子集做一次回归。冻结 Swin test 仍仅校验 SHA，不解析、不检索、不评分。

## 方案选择

| 方案 | 内容 | 取舍 |
|---|---|---|
| A | 只重跑 4 个 Swin 开发案例 | 成本低，但没有外部回归 |
| B（采用） | 4 个 Swin 开发案例＋4 个按问题 ID 哈希固定选择的 QASPER validation 案例，每例最多 3 次规划＋1 次回答 | 32 次硬上限下同时验证已知缺陷和外部回归；QASPER validation 已观察，只能称回归 |
| C | 全部 12 个 Swin dev 和 32 个 QASPER validation | 成本和调试风险过高，且会在已观察样本上反复调优 |

## 样本与隔离

- Swin 开发集固定为 `swin_dev_06`（学习率）、`swin_dev_05`（配置链）、`swin_dev_04`（7×7 条件）和 `swin_dev_12`（动机／拒答）。它们只服务 P4.4 的已知回归，不替代冻结测试。
- QASPER 外部组只从 validation 问题的 `question_id` 做 SHA-256 排序后取前四个。选择不读取答案、证据标注或先前回答的优劣；执行前写入 manifest，之后不可替换。
- 每个请求固定 `limit=8`；Swin 用 `hybrid_rerank`，QASPER 用 `dense`、所属论文的 paper path scope。
- 运行前重新核验评测输入 manifest、当前源码身份与冻结文件 SHA。任何身份变化使用新目录，已开始的 case 绝不自动重试。

## 运行架构

新增 `P4AgentEvaluationRunner`，只依赖现有 `AgentService`、`PaidJournal` 和 `ican.evaluation.data.load_inputs`。runner 建立独立 `data/processed/agent/p4-v2/paid-journal.jsonl`，累计上限 32；服务配置覆盖为 3 次 planner、8 次工具、一次答案调用、180 秒总超时。

每个 case 先持久化 query-only 请求和输入身份，再发送模型请求。结果保存单独 response 文件，并将实际 planner／answer 调用数、工具轨迹、引用和结构化 Claim artifact 原样保留。runner 不读取冻结题内容，也不直接修改 P4.2 的 journal 或任务文件。

## 验收与报告

离线审计将检查每个固定 case 至多一次、journal 预约与完成事件配对、调用数不超过 32、请求范围与 manifest 一致、所有引用 chunk 属于请求范围。Swin 的 7×7 case 额外要求出现 `blocked_by_precondition` Claim；动机 case 的推断 Claim 必须为 `requires_review`。这两条是工作流约束，不用字面 answer 正则伪造正确。

报告分开列出：开发回归的逐案例状态、QASPER 外部回归的运行／引用完整性、调用与 token／实际费用、模型／源码／索引身份，以及不通过和未能回答的案例。除非每个评测条件满足，不报告准确率或泛化提升。

## 停止与成本

- 预算固定为 32 次已发送前预约；无 SDK 重试、无备用模型、无续跑补答。
- 单题达到 planner 或工具限制、模型超时、索引身份变更和开始标记冲突均停止并保存状态。
- 从 API 返回 usage 记录实际 token／费用；费用未知为 `null`，不以旧价格假设伪装实付。
- P4.4 不改检索参数、prompt 或 case 集合来追随本次外部结果；结果只用于记录后续问题。
