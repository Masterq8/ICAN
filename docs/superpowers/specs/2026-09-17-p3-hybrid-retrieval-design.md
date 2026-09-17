# P3 混合检索与重排序设计

用户已确认P3方向并要求当前会话开始；按已有授权连续执行，常规参数由开发实现与开发集验证确定。

## 问题与选择

P2.6 dense检索把标准Swin-T与V2／MLP／MoE／SimMIM混淆，单行配置或类docstring无法形成复现证据链。只加范围过滤可解决部分变体问题，无法覆盖精确符号；LLM改写增加费用及不可控实验变量。本节点选择模型范围约束、确定性关键词展开、BM25与dense候选融合、本地交叉编码器重排与结构上下文选择。

## 数据与接口

复用现有3959块和immutable Qdrant索引，不重新分块、不更改chunk ID／正文／位置／review_required。BM25来自同一经过验证的chunk allowlist，使用正文、source_path、structure_name及context_path；gold、社区回复和项目文档不成为语料。

SearchRequest新增strategy（dense/dense_scoped/bm25/hybrid/hybrid_rerank）及family（auto/all/swin_v1/swin_v2/swin_mlp/swin_moe/simmim）；默认dense保持既有调用行为，改进版显式选择hybrid_rerank。SearchResponse添加trace，记录模型范围理由、展开词、候选来源、排序及分数含义、重排模型身份、窗口截断和额外上下文。PaperQA2消费相同EvidenceResult，不把RRF／rerank分数伪装成LLM相关性。

范围约束来自请求、问题及仓库路径元数据。swin_v1 collection的auto默认为标准Swin家族；问题明确指定其他变体时切换，多个变体冲突则不自动限定；all可关闭自动范围。标准共享训练／配置入口保留。所有渠道包括上下文展开均与用户来源类型／安全路径前缀求交，不扩大用户指定范围。元数据约束并不证明文件内部所有分支属于目标模型，P4再做分支核查。

## 算法及资源

BM25使用rank-bm25，标识符保留全名并拆分camelCase／snake_case；中文采用字符及bigram，配置／命令行写法展开为可解释标识符。dense原文查询不改；候选预算每渠道40，RRF常数60。先对候选取前48个本地BGE-reranker-v2-m3打分，再按结构选择后续原文块，最终Top8供评测与问答。

模型为Apache-2.0，固定revision953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e，下载明确allowlist并核对上游文件身份和SHA。AutoTokenizer／AutoModelForSequenceClassification，本地only／无remote code，FP16 CUDA、batch2、最大pair1536tokens。排序窗口可截断且需明确记录，证据原文不截断不改写；有限logit按相关性排序，不声称概率校准。健康检查不加载encoder或reranker；模型不可用时失败，不静默改用其他排序。

结构上下文按同文件／函数或配置字段查询匹配选择，所有额外片段均为既有可定位chunk，受Top8和字符预算约束。不能把召回配置默认值和覆盖代码误称为已经执行配置；动态trace_config留P4。

## 评测与交付

固定12 Swin dev和3 QASPER train用于检查和选参数，32 QASPER validation作为已观察的回归样本。比较五种策略及必要定位／仓库完整范围／段落完整召回K1/3/5/8，报告范围、展开、重排与上下文贡献和耗时；不以新盲测名义报告已见validation。P2.6原run、94次生成和审核保留，冻结Swin8题仅核对SHA。

实现及纯检索不调用生成API。问答对照使用相同PaperQA2领域prompt和模型，以新run明确有限调用量并保留真实用量，避免为五种策略都生成答案。交付技术配置、可对接现有API的service adapter、模型来源清单、可重建BM25记录、检索消融、必要证据及引用支持失败分析、使用说明。生成若未执行不得宣称引用支持改善。

错误验收覆盖过滤渠道一致性、家族冲突、范围内精确配置命中、RRF去重稳定、上下文位置真实性、预算与模型不可用。独立代码审查、相关测试及保护文件哈希通过后本地保存，不自动启动P4；进入Agent规划前继续提醒用户切换最高阶模型。
