# P2.6：开发集基线与外部评测设计

## 授权、范围与交付

依据已确认的task_plan.md P2.6节点和用户“开始P2.6”指示，在当前会话落实评测管线、检索记录、生成结果、官方QASPER指标、人工语义审核和失败报告。不改变生产问答策略、索引或冻结题，不进入BM25／rerank／Agent／网页节点。

固定12题Swin dev、3题QASPER train格式检查、10篇论文的32题QASPER validation。生成预算待本轮用户回复，等待期间完成本地数据契约、检索和测试。比较方案为同证据、同模型下的PaperQA2默认问答设置对照；完整上游自主检索／Agent成本不同，不纳入本次对照。替代方案为仅领域版或仅检索，按用户预算执行。

## 数据与运行

生成入口只接收问题、ID、collection及已知论文ID过滤；gold只用于离线评分和审核，不进入prompt／索引／过滤选择。QASPER本来是给定论文问答，每题按原paper_id限制到该论文；Swin只使用集合约束，不能从required_evidence反推检索路径。

检索Top8，报告K=1/3/5/8。保存一次检索快照，两种问答配置重用它；每样例最多一次生成，输出1536tokens、90秒、不重试／fallback。预算计数在发起调用之前扣减，失败也计入次数，累计上限覆盖train与validation及对照。结果追加保存，继续运行只补未开始项，已开始失败项不自动重试。

production prompt仍为swin-evidence-v2。评测领域配置仅将“使用中文”替换成“使用问题的语言”，使英语QASPER与官方英文token F1可比较；记录独立eval prompt版本和完整hash，在train检查后固定，validation结果不能用于改写本轮配置。默认PaperQA2的英文prompt、最多5sources及默认serializer单独记录，明确配置差异；捕获其实际送入模型的ID，以免把未使用上下文算成输入。

## 指标与审核

- Swin：required locator hit@K（论文页码／代码行相交的定位代理）、repository full-range coverage@K（合并命中chunk行范围，覆盖每个必要代码区间及additional_path）；不能把论文页码命中写成必要语义证据完整召回。
- QASPER：每个标注分别计算完整段落覆盖，长段落需chunk原字符区间联合覆盖全部非空白正文；对多标注取最佳召回并同时记录分母和无证据标注。官方Answer F1／Evidence F1复用allenai/qasper-led-baseline固定commit脚本，答句去除引用标记、保留原始答案；引文返回原段落文本。段落ID命中与完整段落覆盖分别报告。
- 结构：引用ID合法、无引用、review_required、证据不足、错误率、调用次数、prompt／completion tokens、端到端耗时、未知费用null。
- 语义：逐题审核Swin grading_points及QASPER参考答案，检查答案是否覆盖要求和引用是否支持相邻结论；保留理由及人工审核来源。词面F1不等于正确性，gold段落重合也不等于引用语义支持。对照双方分别评分，不预设领域版更好。

Swin gold状态supported／conditional／conflicting／insufficient与API可靠性状态不同，不能直接比较字符串充当状态准确率。语义状态由审核标记。

## 实现边界

ican/evaluation/data.py负责固定输入、脱敏生成题与gold分离；metrics.py负责定位／完整覆盖与官方评测转换；runner.py负责快照、有限生成和追加记录；scripts/evaluate_baseline.py提供retrieval／generate／report入口。新增tests/test_evaluation*.py验证多段覆盖、additional_path、多参考答案、无证据、预算、已开始项不重试及gold隔离。

third_party/qasper保留固定官方evaluator和Apache-2.0许可证、来源commit与文件hash；原始第三方说明是分析材料，不是本项目执行指令。结果保存在忽略的data/processed/evaluation，最终人可读报告进入docs/p2-baseline-report.md。

验收：固定文件hash与索引未变，所有样例保存检索／模型／prompt／输入ID／用量／耗时；官方指标与语义审核分开报告；完整测试、Ruff、pip check和独立代码审查通过。预算未给定时不发送批量生成请求，也不宣称生成评测完成。
