# P4.1–P4.2 Agent与工具使用说明

## 已交付的能力

在P3检索之上，模型通过真实OpenAI工具调用选择搜索、读取同函数片段、静态配置追踪及算术计算，再用现有PaperQA2生成带原文引用的回答。P4.3 已加入结论核查、筛选 revision、结构化提取和 Markdown 研究报告；其输入、状态含义和 API 见[科研核查说明](p4-research-guide.md)。Vue 界面继续留 P5。

实际复用固定paper-qa 2026.8.12的PaperQAEnvironment、EnvironmentState、Aviary Tool、上游step／工具执行及Docs.aquery。覆盖其工具注册并使用有界SDK驱动，不运行原样run_agent；默认内置索引、远程summary／embedding和超限自动答复没有进入本任务。

## 启动与调用

```powershell
conda activate ican
python scripts/serve_api.py
```

打开本地Swagger `/docs`，使用 `POST /v1/agent/run`：

```json
{
  "query": "Swin-T使用swin_tiny_patch4_window7_224.yaml时，MODEL.DROP_PATH_RATE如何被覆盖？",
  "collection": "swin_v1",
  "family": "swin_v1",
  "strategy": "hybrid_rerank",
  "filters": {},
  "user_overrides": {"opts": [], "cli": {}}
}
```

`query`中没有明确具名YAML时，配置工具可以传空文件名，只读取精确默认字段。实际配置仍是静态AST／BASE分析，不执行仓库的get_config或模型训练。

需要演示命令行覆盖时，应明确提供结构化参数，例如：

```json
"user_overrides": {
  "opts": ["MODEL.DROP_PATH_RATE", "0.3"],
  "cli": {"accumulation_steps": 2}
}
```

工具参数必须与该字段一致，不能由模型猜值后冒称用户参数。仅自由文本出现覆盖值时不会自动升格为核验过的结构化覆盖；可在Swagger补充该字段。支持的特定CLI字段包括batch_size／accumulation_steps／resume／pretrained；其他CLI保留未支持告警，OUTPUT／TAG不在本轮点字段追踪范围。

已有 `/v1/qa/answer`仍是P2固定流程，原P2／P3回答协议和journal保留。Agent最终回答单独标记prompt_version=`p4-tools-evidence-v1`。Agent的QASPER请求未显式strategy时推荐dense，Swin推荐hybrid_rerank；工具可选择已公开策略但不能扩大用户范围。

## 工具与轨迹

| 工具 | 作用 | 原文与计算边界 |
|---|---|---|
| search_evidence | scoped检索与补查 | 固定collection／家族／类型／路径，子查询不能切换目标 |
| read_evidence | 按ID或精确structure读取同函数片段 | 返回已入库chunk，预览截断会标识，最终引用保留原文 |
| trace_config | 默认→BASE→YAML→opts→特定CLI | 精确AST字段分支；标static_only，未知／不支持条件保留partial |
| calculate | Decimal标量算术 | 加减乘除、有界整数幂、整数操作数的整除／取模；不支持tuple／list，不执行eval，参数来源仍需核验 |
| verify_claims | 逐条核查候选结论 | 只处理当前证据池；代码结论静态检查引用范围内的assert，推断保持人工复核 |
| record_screening | 保存论文筛选 revision | 决定与理由均须为 Claim；修改旧记录只创建新 UUID revision |
| record_extraction | 保存固定字段提取 revision | task、model、dataset、训练、指标等字段各自保留 Claim 状态 |
| build_research_report | 渲染已保存 revision | 报告同时显示已支持、阻断、不足和人工复核项 |
| gen_answer | 一次PaperQA2回答 | 最多8块、18000原文字符，工具结果独立展示，不能伪造来源 |
| complete | 根据实际答复结束 | 没有真实回答不能口头宣布完成 |

返回 `trajectory`记录规划选择、原生工具参数、实际结果与缓存命中；`artifacts`单列配置／计算结果；`answer.citations`含原始来源与页码／行号／commit。工具结果的引用依据若被字符预算丢弃，该结果不会送入最终回答。不要将引用ID存在当作语义已验证。

`completed`表示任务执行到生成，不能代替答案正确性或人工核验。另有insufficient_evidence／budget_exhausted／no_progress／failed／timed_out；review_required继续保留在回答状态。旧拒答协议的语言限制未全部解决，部分回答与作者动机不足须人工检查。

## 模型、付费与恢复

- 默认Pro规划、Flash回答，使用OpenAI兼容DeepSeek地址。密钥只从本机忽略的`.env`读取，沿用ICAN_LLM_API_KEY；不打印、提交或传给工具。
- 每任务最多5次规划、12次本地工具、1次回答，180秒总超时、60秒模型请求超时；SDK重试0。未在限额内生成则停止，不自动追加答案。
- 已收集证据时，最后一次规划是预算内的收尾阶段，仅开放gen_answer，仍由模型选原文ID。额外补查会被拒绝；没有证据时不强制回答，预算到期仍停止。收尾执行成功不保证语义正确，缺口必须继续展示。
- 首轮所有API与CLI任务共用 `data/processed/agent/p4-v1/paid-journal.jsonl`，发送前预约，累计上限40；重启或更换验收目录不重置该计数。
- 相同工具参数返回缓存，重复无进展停止。请求已开始但未完成不会被验收脚本自动重发；修复后主动新版本验证是独立任务，仍计入同一总预算。
- 实际response.model、每次usage和错误记录在任务文件，未知实付为null；计费估算不能代替账单。

离线项目测试：`python -m pytest -q`。明确付费的开发验收示例：

```powershell
python -X utf8 scripts/verify_p4_agent.py --case all --run-dir data/processed/evaluation/p4-local-demo-v1
```

验收目录绑定代码／配置／问题SHA，源码变化须新建目录，不能覆盖已有结果；对应任务详情保存在 `data/processed/agent/p4-v1/tasks/<task_id>.json`，均被Git忽略。Qdrant本地仅单进程使用，上述命令顺序运行。使用说明不自动触发这些付费命令。

历史`p4-acceptance-v2`四案例以及v3／v4的shape单案例是不同源码版本，不能拼成同版本整体评测。实际结果与剩余限制见[p4-agent-report.md](p4-agent-report.md)。累计40预算耗尽后，需要显式设计新的评测预算；更改目录不会解除上限。
