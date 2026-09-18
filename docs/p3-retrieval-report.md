# P3 混合检索与重排序评测

**状态：P3交付完成（2026-09-18）。** 检索、真实回答、引用审核及接口验证均已完成；Swin专项改善，QASPER回归下降，两者分别报告。

## 问题与方案

P2.6基础dense把Swin-T与V2／MoE／MLP／SimMIM的专用实现混入候选，精确YAML字段也会缺少默认值与覆盖顺序。P3沿用原始3959块和不可变Qdrant索引，新增范围预过滤、BM25精确符号检索、RRF融合、本地BGE-reranker-v2-m3、原始结构证据补充。

Kotaemon仅借鉴过滤→双路候选→重排→TopK流程，不安装或复制其完整模块。重排实际调用固定公开版本的本地模型；PaperQA2继续使用既有公开接口adapter。来源、版本、使用步骤及各策略行为见 [使用说明](p3-retrieval-guide.md)。

## 协议

- 同12道Swin dev、3道QASPER train格式题、32道已经观察过的QASPER validation；validation用于回归，不能称新盲测。
- 参数仅在dev/train校准：每路40候选、RRF60、最多48候选重排、FP16 CUDA batch2、最大pair1536 tokens、输出Top8，最多3个原始结构追加块。
- 五种实际策略加一组从同一重排列表派生的raw消融；不为每组重复生成答案。
- `p3-preflight`保留首轮90记录，`p3-preflight-v3`保留第二轮90记录；最终`p3-preflight-v4`固定代码/配置后先完成90记录，再进入validation。中断的v2保留，不算正式结果。
- manifest绑定输入、代码、模型账本、实际index fingerprint/identity/manifest SHA；完整282条才seal。P2.6的retrieval、journal及审核不改写，冻结8题只校验SHA。
- 新`p3-qa-v1`从已封存v4的hybrid_rerank导出47题证据，使用原`eval-adapter-v2-question-language-v1`、deepseek-flash与PaperQA2 2026.8.12，累计生成47次，不自动重试。
- 随后真实HTTP短查询发现具名YAML字段仍可能被Top8挤掉，新增明确字段锚点及中文相邻标识符边界修复；独立复核再补右ASCII边界，避免foo／_foo／1foo等后缀误匹配字段前缀。接口缺陷独立于validation gold，最终以`p3-final-v3`重新运行全部282条检索，未追加付费生成。v2保留为上一版，中断的`p3-final-v1`保留且不计结果。
- 离线逐题重新准备实际PaperQA2上下文、system／qa提示、来源rank／score及字符预算：最终v3与已生成v1的**47/47输入完全相同**，见[p3-input-equivalence.json](evaluation/p3-input-equivalence.json)。答句审核始终绑定原v1 journal，不冒充重新生成后的审核；本文检索表为最终v3结果。

## Swin 开发集：Top8

| 策略 | 必要定位召回 | 必要仓库完整行范围覆盖 |
|---|---:|---:|
| dense，保留P2基线 | 32.64% | 8.33% |
| dense_scoped | 53.47% | 23.61% |
| BM25 | 70.14% | 27.78% |
| hybrid，RRF融合 | 72.92% | 34.03% |
| hybrid_rerank_raw | 71.53% | 27.78% |
| hybrid_rerank，含结构证据 | **80.56%** | **31.94%** |

各题召回按其适用必要证据取平均，分母12题；定位命中与完整行范围覆盖分开。完整覆盖指标仍较低，不能用80.56%宣称答案正确率。RRF的完整行范围覆盖高于最终重排版，说明重排并非所有指标都最佳；保留各策略供后续Agent补查选择。

首轮结构补充机械预留3槽，定位召回64.58%，低于raw的69.44%；最终规则保留原TopK、保护高排名种子，优先替换重复说明文档，按查询中的明确代码实体和具名YAML配置链补证据。所有新增块都是既有chunk，不拼接新引用范围。

## 配置链与训练入口实例

- `swin_dev_05`：最终先返回具名`swin_tiny_patch4_window7_224.yaml:4`的0.2，再返回`config.py:1`所在默认值块，以及268–280的文件合并、283–289的`--opts`、294–349的特定CLI覆盖块。已能展示默认值→YAML→CLI的静态链；未执行配置，也未完整覆盖标注的所有长行范围。
- `swin_dev_06`：保留`main.py:300`所在的运行时LR缩放块，避免结构扩展将它挤掉。其他YAML的LR仍可出现在候选，需生成端遵守问题给定参数和引用归因。
- `swin_dev_08`：在保留默认值与运行时LR块的同时，补`main.py:174`所在`train_one_epoch`梯度累积实现，完整覆盖该题两个必要仓库范围。
- `swin_dev_01`：固定“linear embedding”术语只增加PatchEmbed具名类的原始投影与forward片段，避免仅靠类docstring回答具体操作。

## 变体路径与外部回归

Swin dev12题的96个Top8位置中，dense有64个来自V2／MoE／MLP／SimMIM专用来源路径，最终策略为0个。统计仅判断专用路径，不代表共享代码／文档里的其它变体文字也全部排除。全部47题重排序pair截断数为0。

| QASPER validation指标 | P2.6领域adapter／dense | P3领域adapter／hybrid_rerank |
|---|---:|---:|
| Top8完整段落证据召回，31个适用问题 | 78.49% | 75.27% |
| 官方Answer F1，32题 | 16.95% | 11.79% |
| 官方Evidence F1，32题 | 47.41% | 37.23% |
| 助手判断完整答案 | 21/32 | 19/32 |
| 助手判断引用完全支持，适用答句 | 24/29 | 22/30 |

外部指标均有下降。相同32题已在P2.6观察，仅作为回归；没有根据这些结果再调参或改gold。Answer F1衡量词面重合，中文解释及过长boolean回答会影响分数，不能当语义准确率。语义判断也下降，不能仅以语言因素解释回退。默认API仍为dense；P3提供可选改进策略，不声称统一优于基线。后续按任务选择策略需新留出样本验证。

QASPER train仅3道格式题，完整段落召回最终0.25、dense0（2题适用），不用于宣称泛化。所有K1/3/5/8消融结果见[p3-retrieval-summary.json](evaluation/p3-retrieval-summary.json)。

## 同adapter真实答案审核

| Swin dev指标 | P2.6领域adapter | P3领域adapter |
|---|---:|---:|
| 固定评分点覆盖 | 18/49 | **40/49** |
| 逐题评分覆盖宏平均 | 37.50% | 82.50% |
| 完整／部分／错误／拒答 | 0／7／1／4 | 4／6／2／0 |
| 引用完全支持 | 见P2.6审核 | 6/12 |

评分点与总体判断分别统计：dev12四点全中，但配置引用落在SWIN_MLP分支，整体仍判部分；dev04对不能运行和分辨率的说明正确，但实际失败位置／断言错误。固定评分点包含一个否定错误理由的点，满足该点不能洗掉其它错误。

已改善的完整答案为patch投影、patches_resolution、DROP_PATH_RATE覆盖链及resume优先级。仍需处理：

- dev06引用了正确LR公式，却把0.001×2算成0.512；必须用计算工具校验数值。
- dev04未定位第三次PatchMerging的偶数断言；需要跨stage补查。
- dev02、09、10、11遗漏block索引、absolute_pos_embed、头数条件或首层形状例子。
- dev12共享config块中的MLP分支被当标准Swin配置；路径过滤后仍需字段所属分支归因。
- 外部问题仍混淆相关工作／本论文实验，或已有数字却拒绝计算；论文表格正文缺失与5个validation参考歧义原样保留。

47份新回答逐条核对实际引用，助手审核，未经独立人类复核。validation为完整19、部分3、错误3、拒答2、参考歧义5；引用支持22、部分5、不支持3、不适用2。train为错误1、拒答1、参考歧义1。dev12对作者动机的部分拒答被原regex漏识别，语义审核单列，不回填原journal。

审核文件及SHA绑定见[evaluation目录说明](evaluation/README.md)，汇总见[p3-acceptance-summary.json](evaluation/p3-acceptance-summary.json)。所有回答的引用ID均存在，不代表全部语义支持。

## 调用、费用与验证

- 47次开始、47次成功完成、每题一次生成，无错误、重试或额外summary／远程embedding；本轮150081输入tokens、7048输出tokens。
- 沿用2026-09-17核验价格假设（输入0.30／输出1.20美元每百万tokens），全部输入cache-miss估算**0.0534819美元**，实付未知为null；不是读取账单得出的实际费用。
- 完整测试178通过、1项Windows符号链接权限跳过；实际HTTP两项通过（具名YAML短查询的默认／文件／opts链，以及明确V2路径约束），该验证生成调用0。
- 61份受保护材料、冻结8题SHA及P2.6原检索／生成journal保持不变。独立代码审查检查过滤、模型完整性、实际混合通道和恢复索引身份。
- 同机47题检索耗时中位数：dense约0.66秒、BM25约0.003秒、hybrid约0.69秒、最终重排约1.19秒；这是本轮串行实测，不包含服务并发能力或首次模型加载承诺。

最终检索seal：`1c2f9b7a287f96e3fba63c42fc4e2e8cccf9da7e2d7b30384edce4266ce591de`；原新答案journal：`d6123f21d609cad8b799b73670b0b4d21f2a9386bdbd77d13df38389ba6925e0`。模型与源码身份在检索汇总，审核来源绑定在audit manifest。

## 限制与后续

家族过滤约束来源路径，共享README／get_started／build分支可能仍描述其他变体。结构补充是有限静态选块，不是完整调用图或实际配置解释器。112输入失败的跨stage证据、位置张量处理的额外断言、作者设计动机以及公式／表格仍可能缺证据；原表格review_required保留。

问答协议沿用P2.6拒答识别器以便对照，已知自然拒答regex漏识别不在本轮观察validation后回填。语义审核需绑定新答案及引用SHA，不能复用旧答句判断；助手审核不等于独立人工复核。

下一节点P4实现工具调用及Agent规划。进入该节点前提醒用户使用最高阶模型。
