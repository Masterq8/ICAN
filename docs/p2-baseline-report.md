# P2.6 基线报告：检索、双版问答与语义审核

日期：2026-09-17。状态：**complete**。用户授权由助手决定调用量，本轮选择47题×2版＝**94次真实生成**，全部完成，逐条保存94份助手语义审核。结果显示：领域版在本次QASPER样本的词面答案／段落证据F1较高，但Swin固定实现核查仍受变体混入、代码块缺失及配置链检索失败限制。两版均没有完整解决全部要求的Swin答句，后续优先改善检索。此结论仅适用于本轮模型、配置与样本。

## 1. 固定材料与协议

- Swin dev12题，开发题及标注保持原字节；冻结8题只核对SHA，未解析问题或标准答案。
- QASPER train按question_id排序取前3题检查格式；validation10篇论文32题、57份答案标注，独立报告。训练小样本不代表训练集总体表现。
- 既有BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`，1024维归一化Cosine；索引 `3fcc38131d303a03b83cbe0dea77dc74b83398f597aee10e6a4fb1fbae9eaa87`。
- 单次检索Top8；Swin只限定collection，未按gold选择类型／路径。QASPER根据题目原paper_id限制到给定论文，符合其问答任务定义。
- 首次preflight完成全部检索；经相同问题、输入SHA、chunk正文／来源核验复用到最终 `data/processed/evaluation/p26-v2/`，原始检索协议保留在provenance。两版生成将消费同一快照，不再次检索。
- 快照SHA `14aa782abf9a15bfc43fc820ac22122c129388a47bc26304e47df6cef1558d7f`；已封存快照不能重新赋hash覆盖，生成／报告发现变更即拒绝。

## 2. 检索结果

所有数值为逐题macro平均。不同任务的指标定义和来源约束分别写明。

| Top-K | Swin必要定位召回，n=12 | Swin必要仓库证据完整行范围覆盖，n=12 | QASPER validation完整段落召回，n=31 |
|---|---:|---:|---:|
| 1 | 8.33% | 0.00% | 25.27% |
| 3 | 27.08% | 0.00% | 62.37% |
| 5 | 27.08% | 8.33% | 73.66% |
| 8 | 32.64% | 8.33% | 78.49% |

**Swin口径：** 论文以固定页码命中为代理，仓库证据以目标代码行相交为定位命中。完整行范围覆盖需要多个chunk联合覆盖标注中的全部区间，包含additional_path；这是严格的来源范围指标。页码／行号命中不证明语义必要证据已完整出现，粗粒度代码范围也可能包含回答不需要的行。因此不将上述定位指标命名为语义Required Evidence Recall。Top8仅2/12题找齐全部必要定位入口。

**QASPER口径：** 根据原段落unit ID和chunk字符范围，联合覆盖段落所有非空白字符才算完整召回；对多份可回答且带证据的标注取最佳比例。32题中31题适用该指标；有1份可回答标注未提供证据，4份标注为unanswerable，均保留明细和每份参考证据分母。一个题目可能同时包含不同类型标注。此样本的段落命中召回与完整召回相同；不能推广为所有长段落均不会拆分。Top8有24/32题完整覆盖至少一份非空证据标注，其余无参考证据题不算覆盖成功。

**Train格式样本：** 3题中2题带可回答证据标注，K1/3/5/8完整段落召回均为0。仅用作格式／错误检查，不与validation合并。

## 3. 失败样例与下一步

检索记录可直接定位以下开发题失败：

- swin_dev_01：前三项来自swin_mlp.py、swin_transformer_v2.py、swin_transformer_moe.py；Top8只命中P01，缺标准Swin-T配置和PatchEmbed代码证据。
- swin_dev_04：前三项为SwinV2分辨率微调YAML，未命中题目所需PatchEmbed／PatchMerging／stage构造入口。
- swin_dev_06：学习率问题召回MoE训练配置，缺config.py默认值与main.py运行时缩放。
- swin_dev_07：加载分支问题召回SimMIM／MoE工具文件，缺标准main.py分支。
- swin_dev_08：梯度累积问题召回SwinV2 YAML，缺标准训练循环及启动缩放代码。

这些是原始dense基线的实际失败，不在本节点用gold路径修正后覆盖基线。P3优先加入可从问题／仓库元数据识别的模型家族约束、精确符号／配置检索、BM25融合及重排序。参数用Swin dev／QASPER train决定，validation保留为本轮独立结果。

## 4. 已运行的问答对照

模型使用用户已配置的 `deepseek-flash`，服务为DeepSeek OpenAI兼容接口；每题每版最多1次、1536输出tokens、90秒，无summary／embedding／补查／重试／fallback。实际47题×2版＝94次，其中6次train格式检查、24次Swin dev、64次QASPER validation。先train、后dev、再validation，全程未根据validation结果调整配置。

| 配置 | prompt／serializer | 实际证据范围 |
|---|---|---|
| adapter | 基于生产swin-evidence-v2，仅将中文要求改为问题语言；独立版本eval-adapter-v2-question-language-v1 | 检索顺序，最多8块／18000原文字符；详细位置和review标记 |
| paperqa-default | 固定PaperQA2 2026.8.12默认问答prompt及serializer；关闭自动补查以固定单轮预算 | 默认按score／name排序，最多5sources；记录实际送入的ID |

这是**同检索快照的默认问答配置对照**，未运行完整PaperQA2自主Agent／默认embedding及检索链。源码及prompt hash在manifest保存。生产API提示仍为中文v2，不因评测语言协议改变。

QASPER指标调用[作者官方evaluator](https://github.com/allenai/qasper-led-baseline/blob/afd0fb96bf78ce8cd8157639c6f6a6995e4f9089/scripts/evaluator.py)，按其规则分别对多份答案／证据标注取最佳F1。原始答句保留，评分前移除引用标记；证据从被引用chunk回溯原段落，段落命中Evidence F1与完整段落Evidence F1分别统计。词面F1受答案长度、语言和改写影响，不等于语义正确率。

### 4.1 官方词面评分与引用格式

| 数据／指标 | adapter | paperqa-default |
|---|---:|---:|
| QASPER validation Answer F1，n=32 | 16.95% | 8.42% |
| QASPER validation Evidence F1，n=32 | 47.41% | 22.25% |
| QASPER validation完整段落Evidence F1，n=32 | 47.41% | 22.25% |
| QASPER validation引用格式有效答句 | 32/32 | 32/32 |
| Swin dev引用格式有效答句 | 11/12 | 12/12 |
| QASPER train Answer F1，仅3题格式样本 | 7.38% | 0.00% |
| QASPER train Evidence F1，仅3题格式样本 | 0.00% | 0.00% |

没有未知引用ID；唯一未满足引用格式条件的是adapter的swin_dev_08无引用拒答，不能算成伪造引用。引用ID存在不等于结论得到支持。Evidence F1通过被引用chunk回溯原段落，是段落集合匹配；本样本命中与完整段落两种F1恰好相同。

**已发现评分限制：** 原始拒答识别器接受`[INSUFFICIENT_EVIDENCE]`或开头的`I cannot answer`，会漏掉末尾／自然表达的拒答。上述官方分数保持本轮原始协议，不在观察validation后修改规则回填。人工语义式审核发现9条记录与拒答标记不一致（Swin默认版4条，QASPER领域版1条／默认版4条）；明细可复查。后续建立新评分协议时修正，并同时保留本轮结果。

### 4.2 逐题助手审核

对Swin逐项核对固定grading_points，对QASPER逐份参考答案核对；再读实际引用原文，检查相邻结论及模型／实验范围。每条保存具体理由，不用段落重叠自动替代语义支持。**审核者为开发助手，未有人类独立复核；这些是定性基线，不能当成人工验证的正确率。**

| 样本／判断 | adapter | paperqa-default |
|---|---:|---:|
| Swin完整／部分／错误／拒答，n=12 | 0 / 7 / 1 / 4 | 0 / 6 / 1 / 5 |
| Swin评分点覆盖，micro，49点 | 18/49（36.73%） | 16/49（32.65%） |
| Swin逐题评分点覆盖，macro | 37.50% | 33.33% |
| Swin答句结论全部受引用支持／适用答句 | 1/8 | 1/7 |
| QASPER完整／部分／错误／拒答／参考歧义，n=32 | 21 / 1 / 4 / 1 / 5 | 18 / 5 / 3 / 1 / 5 |
| QASPER答句结论全部受引用支持／适用答句 | 24/29 | 19/29 |
| QASPER语义上的拒答（含歧义题） | 3/32 | 4/32 |

评分点用0/1严格记录，复合点需覆盖规定内容；只说“无法回答”不获得“没有错误归因”等分数。评分点覆盖和完整答句正确性是两种判断：swin_dev_10虽覆盖四点，但额外把head不匹配时的warning解读为跳过张量；源代码并未删除该参数，因此整体仍为部分正确。引用支持按**答句**统计，不是逐个citation百分比；分母排除`not_applicable`，如没有实质答案的拒答。可以有“部分正确但已给部分均有支持”，不能把引用支持直接等同答案完整。

语义状态不比较API状态字符串。QASPER可答性／拒答状态在27个非歧义题上两版各25/27；5个参考歧义题记null。Swin仅对明确拒答审核该状态：领域版1/4、默认版1/5符合gold（swin_dev_12）；其余非拒答的supported／conditional细分未独立赋状态，记null，**不报告全12题状态准确率**。train3题单列：领域版3条错误，默认版1错误／1拒答／1参考歧义，不代表全训练集。

**失败原因与资料边界：**

- swin_dev_05：领域版找到目标YAML的0.2，仍缺config.py→BASE→当前YAML→CLI链；默认serializer排序／5sources丢掉该目标项后拒答。差异同时涉及排序和证据容量，不能归因只改了prompt。
- swin_dev_07：领域版改答main_simmim_pt.py，并声称PRETRAINED先加载；这不是指定main.py，引用也未显示该分支。默认版从工具函数独立推成无互斥逻辑，同样缺入口证据。
- QASPER：出现把相关工作的非英语数据误当本论文实验、把综述算法当本论文方法、漏第三个正则项、SimpleQuestions之外数据集问题答Yes等错误。INLINEFORM占位公式没有恢复，不能凭常识补成确定的文内等式。
- QASPER参考也有冲突：语言对与aligned argument的CLV粒度、SOTA／医疗术语／英语TAC的混合可答性、None与MemNN的baseline标注，均保留歧义理由。train的表格差值题只有caption而缺数值；另一baseline题参考名单与其证据不一致。未改写原gold来提高得分。
- QASPER短标准答案对冗长解释敏感；布尔题附加解释后token F1可能很低。领域版仍有英语题输出中文的问题。21个语义完整答句与16.95%词面F1可以同时出现，二者不可互换。

逐条理由及hash绑定见[审核目录](evaluation/README.md)；运行journal、原始答句和完整引用保存在本机忽略的run目录。此validation已用于观察结果，后续不能称同一批题是从未看过的新盲测；最终独立验收继续保留冻结集／另设留出样本。

## 5. 耗时、可靠性与恢复

检索请求耗时中位数0.984秒，首题75.141秒，含首次索引核验和BGE-M3加载。生成请求中位数：Swin领域版1.353秒／默认版1.877秒，QASPER validation领域版1.289秒／默认版1.770秒；这些是复用检索快照的单次生成耗时，不是新请求端到端RAG耗时。

94个started和94个completed，无error／unfinished／缺用量；本轮无review_required引用（不代表人工验证通过）。总输入180,661、输出19,786 tokens。两份用户账单CSV位于已失效的临时路径，未能读取，不能声称核对过账单。按[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)在2026-09-17核验的USD／百万tokens高峰cache-miss输入0.30、输出1.20估算：`180661×0.30/1e6 + 19786×1.20/1e6 = 0.0779415 USD`。这是指定价格假设下的估算；缓存／时段／账单币种折算未知，实付cost_usd保持null。本节点不再追加付费调用。

调用前started记录flush＋fsync，已开始键永久跳过；中断／失败不自动重试。未完成started计入失败及引用率分母，未知tokens单独计数。CLI单写者文件锁避免两个进程同时消耗同一运行预算。resume核对模型服务、输入／代码／prompt hash和密封快照；改变配置需新run，不将旧结果混入。

最终完整测试142通过／1项Windows符号链接权限跳过，改动范围Ruff／format通过；此前pip check通过且本次未改依赖。新增6项审核完整性回归验证重复审核不能掩盖缺题、评分点不能丢失、审核不能移用到另一次生成，以及重复started／completed和超额call记录不能被字典／计数掩盖。审核CLI与评测CLI共用单写者锁。独立审查修正快照可变、重新封存绕过、中断统计遗漏、无证据分母和审核journal完整性问题，最终无剩余重要发现。61个受保护文件、生成代码／prompt协议及索引identity未变；冻结gold仍只核对SHA。

## 6. 运行说明

```powershell
conda activate ican
# 新环境恢复材料和索引后，从头获取新快照。
python scripts/evaluate_baseline.py retrieval --run-dir data/processed/evaluation/new-run
python scripts/evaluate_baseline.py report --run-dir data/processed/evaluation/new-run
# 以下会调用用户API；max-calls为同一run累计上限，须符合已给定预算。
python scripts/evaluate_baseline.py generate --run-dir data/processed/evaluation/p26-v2 --max-calls 94
python scripts/evaluate_baseline.py report --run-dir data/processed/evaluation/p26-v2
# 不调用模型；仅用于hash匹配的本轮结果，合并已经做出的逐条审核。
python scripts/finalize_baseline_audit.py --run-dir data/processed/evaluation/p26-v2
```

最终本地产物：manifest.json、retrieval.jsonl、generation-identity.json、journal.jsonl、summary.json、semantic-audit.jsonl、acceptance-summary.json。原始材料／生成数据被Git忽略，协议、代码、官方脚本与Apache-2.0许可入库；[汇总](evaluation/p26-acceptance-summary.json)、逐题审核理由与审核manifest入库。审核manifest绑定输入、检索、journal及review文件SHA，不能把旧判定移用于新答案。

P2.6完成。下一节点为P3混合检索：先识别Swin模型家族与精确符号，再比较dense／BM25／hybrid／hybrid＋rerank；针对代码函数与配置覆盖链补齐上下文。拒答协议修正、布尔短答与公式／表格边界处理另立版本，保留本轮94次结果作比较。本次不提前修改检索排序。
