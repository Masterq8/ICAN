# P4.5：必经核查工作流交付与失败验收

日期：2026-09-18。**工程控制已实现，两条真实开发验收未通过；P4.5整体仍进行中。** 自动论文筛选、字段提取、多论文报告及网页仍待后续节点。

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

独立草稿阶段已离线实现；接下来使用中性协议样例验证SDK请求与服务端工具选择行为，再以新目录、源码身份与独立预算确认真实科研流程。不反复重跑同一开发题修饰结果。然后进入P4.6自动实验信息卡、筛选／比较／研究报告，再接P5网页；不继续扩大全量评测代替产品开发。
