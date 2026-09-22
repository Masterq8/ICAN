# P4.5：必经核查工作流与后续独立验收

日期：2026-09-18—19。**工程控制已实现；原两条真实开发验收失败保持原样，修复后的新协议与独立科研流程另行记录。** 自动论文筛选、字段提取、多论文报告和网页已有首版，稳定性及字段语义尚未完成验收。

## 已交付

- 新`configs/agent/v2.json`使用`verified`模式，复用PaperQA2原生环境与`Docs.aquery`；保留旧`tool_loop`配置及历史轨迹。
- 只有合法`submit_claims`能进入草稿、核查、一次引用回答阶段。直接`gen_answer`无法绕过；最后规划轮无论有无证据都只开放提交工具，并在API指定工具名。
- 提交必须使用任务已保留、最终已选择的证据，满足请求显式指定的Claim类型。最终上下文丢失任一Claim证据时，在付费回答前停止。
- 推断传播为`review_required`，不足传播为`insufficient_evidence`；前置断言阻断保留为结构化结果。类型化检查不证明任意自由文本结论正确。
- 响应新增`workflow_mode`、`workflow_stages`及带原文位置／版本的核查产物，便于Vue展示。
- `scripts/verify_agent_workflow.py`绑定源码、请求、配置、冻结测试SHA；独立8次硬上限与开始标记阻止自动重试。

## 离线验证与独立复核

最终全量测试：**255项通过、1项Windows符号链接权限跳过**；13个范围内Python文件Ruff与格式检查通过。新增11项测试覆盖提交策略、必经核查、直接回答拒绝、预算、单工具命名、空证据收尾、上下文丢证据、原始断言和独立草稿上下文。

按requesting-code-review技能做独立只读复核。首轮发现“无证据时最后轮仍开放调查”，已修复并新增原生工具回归；随后复核类型分支schema。最终复核独立草稿上下文，30项Agent测试通过，无重要发现。这些均为离线复核。

61项受保护材料、冻结Swin测试SHA及5项P2/P3封存文件均未变。旧P4.2 journal仍39次，P4.4仍25次。本轮未读取冻结测试题内容。

## 真实验收：失败，未重试

新目录`data/processed/evaluation/p4-v3`，两个既有Swin开发题各一次，最多3次Pro规划加1次Flash回答。实际**6次Pro、0次Flash**，68,116输入／2,175输出token；6个started与6个completed配对，usage无缺失、API错误无记录。实付费用未知；剩余2次未使用。

| 案例 | 请求必需类型 | 实际结果 | 原因 |
|---|---|---|---|
| `swin_dev_04`，112尺寸／7×7 | `code_execution` | `no_progress`，无答案／核查产物 | 已读到PatchMerging第331–352行，包含第338行偶数断言；最终轮已指定submit工具，模型仍请求两次read_evidence，服务拒绝 |
| `swin_dev_12`，PatchEmbed归一化动机 | `inference` | `budget_exhausted`，无答案／核查产物 | 最终调用submit_claims，但推断Claim携带quote，与类型契约冲突；整批拒绝，不能跳过非法结论生成回答 |

**既未获得所需`blocked_by_precondition`，也未获得`requires_review`真实Agent产物。** 安全拒绝通过，不等于任务成功；不计算两题答案正确率，不把离线核查结果回填为真实轨迹。

## 验收后的修复与版本边界

原Pydantic生成的schema展示所有可选字段，类型互斥只存在Python validator中。现`submission_tool_schema`通过`oneOf`明确四种类型的允许字段与必填载荷，离线可拒绝“inference带quote”和缺少类型载荷的草稿。

另已将最终草稿阶段与调查历史分离：重建只有system／user的消息，完整保留结构化用户请求、当前原文证据及计算／配置产物，不传递此前assistant／tool调用历史；仍只允许submit_claims。原生工具回归验证这些数据不丢失、合法提交只回答一次。

这些补丁发生在真实运行之后，改变workflow、service及prompts源码。原manifest和journal保持原样；**新schema与独立草稿上下文尚未真实验证**。schema和消息隔离不能保证服务端模型遵守指定工具，也不能保证quote与原文精确一致。实际动机提交的其他verbatim含省略号或改写，修复类型后仍可能被精确引文核查判不足。

## 封存身份

| 产物 | SHA-256 |
|---|---|
| manifest.json | `0d97dc0ebdc39515aed27cb6959638b144f162829812cb61368f031af9761bb5` |
| paid-journal.jsonl | `09ffc5532a5ad1bf7b10a0b8b3f4eed5d2d61a15b90b0ed2cb50f592266d6dbb` |
| shape.json | `740e462f7b87df6dde97c99a57e796a0d9375d8b23ee4115542db023ad803142` |
| motivation.json | `59f4dc084e4bfbe5ab9e503676b1df09a706d0a478b310264dfa0c99c0f2228d` |
| summary.json | `cc876d3f56421c7c201dfab54bd49491ae63139ddac465685475240a916635ac` |

运行产物按仓库策略不提交；可提交摘要见[evaluation/p4-verified-workflow-summary.json](evaluation/p4-verified-workflow-summary.json)。

## 下一步

独立草稿阶段先离线实现；随后按既定顺序使用中性协议样例核对 SDK 请求和服务端工具选择，再用新目录、新源码身份与独立预算执行一条新科研题。不反复重跑同一开发题修饰结果。之后进入 P4.6 与 P5 产品链路，没有扩大旧题的全量评测。

## 2026-09-19 补充验收

1. `tests/test_agent_sdk_protocol.py` 用真实安装的 OpenAI SDK 和本地 HTTP mock 检查请求 JSON：具名 `tool_choice` 指向 `submit_claims`，工具 schema 与选择一致。测试通过，不消耗模型调用。
2. `scripts/verify_agent_tool_protocol.py` 用中性 `submit_token(token="ok")` 执行一次真实 DeepSeek Pro 调用，工具名、参数和最终校验均通过。记录在独立 `data/processed/evaluation/p4-v4-protocol/`；1 次调用，307 输入 token、36 输出 token。该结果只证明中性协议行为，不外推为科研题正确率。
3. `scripts/verify_agent_research_v4.py` 用独立新题检查 `PatchMerging.forward` 在 `L=64,H=8,W=8` 时的两项前置断言。真实流程完成草稿提交、逐条核查和引用回答，4 次调用（3 Pro、1 Flash），17,816 输入 token、1,107 输出 token。第一条具备完整绑定的代码结论通过；第二条遗漏 `L` 绑定，被判 `insufficient_evidence`；另一条推断为 `requires_review`。整体 `insufficient_evidence`，不计为解答成功，也不重跑该题。记录在 `data/processed/evaluation/p4-v4-research/`。
4. P4.6 首轮独立产品 smoke 的 3 个模型提交均为 `ToolInputError`，结果原样留在 `data/processed/evaluation/p46-product-smoke-v1/`。后续单独的新 QASPER train 诊断样本成功生成 7 个字面匹配字段；网页端两篇此前未测 train 论文也各成功生成信息卡，并形成“不直接排名”的多论文报告。这证明完整路径可用，但 3 个首轮失败和字段语义误归类说明稳定性、准确性尚未过关。
5. 当前全量回归 269 通过、1 跳过；本轮 15 个 Python 变更文件的 Ruff 格式与静态检查、Vue/TypeScript 严格构建通过。上述付费运行的供应商返回 `actual_cost_usd=null`，这里只报告调用和 token，不推算实际账单金额。

**口径：** P4.5 的必经控制与工具协议已验证，真实题的答案质量未通过；P4.6/P5 有可操作首版，但不能宣称自动科研结论可靠或正式上线。
