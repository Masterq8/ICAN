# 开源项目与论文数据集复用调研

核验日期：2026-09-16。调研后的实施状态：P2.1 解析与 QASPER 外部样本准备已完成，尚未进入问答评测。

## 1. 结论与采用顺序

已有开源项目覆盖了论文解析、证据问答、论文筛选和带引用报告中的大量基础能力。推荐先评估 Docling 解析 Swin PDF，以 PaperQA2 作为科研问答参考基线，借鉴 ASReview 的可修改筛选记录、Kotaemon 的引用展示，以及 OpenScholar/STORM 的报告生成流程。

**2026-09-16 用户新增决策：** PaperQA2提升为主要问答／Agent框架参考与复用目标，通过adapter针对论文—代码—配置问题改造；原版仍可作对照参考。P2.5先验证固定版本的已解析文本、外部证据／检索和引用适配。下一节点保持P2.2结构化分块；Kotaemon用于P3/P5，其他组件按模块加入。该决策是接入计划，不表示PaperQA2已安装或已兼容本项目Qdrant，详见 `task_plan.md`。

我们保留的核心工作是：将论文版本、官方仓库 commit、代码行号、配置覆盖关系和结论连接起来，并用已有 Swin 20 题验证。PaperQA2 已支持代码文件，因此不能把“能读取代码”本身当成差异化；应展示具体的论文—函数—配置核查与可定位证据。

后续已在本机完成 PyMuPDF／Docling 比较，选择 Docling 主后端与 PyMuPDF 定位恢复，补齐管线和验收；Swin 生成 97 单元，QASPER 选择 20 篇 train／10 篇 validation。20 项测试通过，核心解析产物重复重建哈希相同。详细实测见 `parser-comparison.md`，使用与限制见 `p2-parsing-guide.md`。其余完整应用尚未安装，保留各自开发节点的参考用途。

## 2. GitHub 项目

| 项目／一手来源 | 公开能力 | 复用方式与开发节点 | 许可证／适用边界 |
|---|---|---|---|
| [Docling](https://github.com/docling-project/docling) | 文档阅读顺序、表格、布局、JSON/Markdown；本地处理 | **P2.1 优先试用库**；转换到我们的来源与解析单元契约 | 代码 MIT，模型许可另核验；双栏、公式效果需用 Swin 实测 |
| [PaperQA2](https://github.com/Future-House/paper-qa) | 文献检索、证据收集、带引用问答、Agent；支持代码文件 | **P2.5/P4主要框架复用目标**；通过领域adapter扩展来源与工具，原版另作对照 | Apache-2.0；代码引用需提供元信息；默认回答索引须与评测证据索引隔离；接入方式待固定版本验证 |
| [ASReview LAB](https://github.com/asreview/asreview) | 人工标记相关性、主动学习排序、重复检测、修改标签、导出决策 | **筛选模块参考**；借鉴人在回路与审计记录 | Apache-2.0；核心是筛选，不是现成的全文提取／报告系统 |
| [Kotaemon](https://github.com/Cinnamon/kotaemon) | 文档问答、混合检索、重排、PDF 引用高亮、Agent 示例 | **P3/P5 参考**；检索步骤与证据体验 | Apache-2.0；界面基于 Gradio，接入我们的 Vue 需要适配 |
| [OpenScholar](https://github.com/AkariAsai/OpenScholar) | 科研多文献综合、反馈补查、重排、事后引用归因 | **P4 报告与补查参考**；小样本流程或基线 | 代码 Apache-2.0，权重另核验；公开全库达 2 亿余 embeddings，不适合本机全量部署 |
| [STORM](https://github.com/stanford-oval/storm) | 多视角提问检索、大纲、分章节带引用长文 | **报告节点参考**；适配学术报告模板 | MIT；原始目标是 Wikipedia 风格文章，需要改造为论文方法／实验／局限比较 |
| [GROBID](https://github.com/grobidOrg/grobid) | 科学 PDF 的章节、作者、参考文献、引用结构，TEI XML | **后续元数据／参考文献增强候选** | 代码 Apache-2.0；Java／服务部署增加工程成本 |
| [MinerU](https://github.com/opendatalab/MinerU) | PDF 结构化、复杂表格／公式等处理 | **复杂 PDF 备选解析器**，首轮不并行引入全部后端 | 当前是[基于 Apache-2.0 增补条款的自定义许可](https://raw.githubusercontent.com/opendatalab/MinerU/master/LICENSE.md)，在线服务需显著署名；模型与后端另核验 |
| [Marker](https://github.com/datalab-to/marker) | 文档到 Markdown/JSON/chunks，表格与公式处理 | **备选解析器**；首轮排在 Docling 后 | 当前代码 Apache-2.0；[模型许可](https://raw.githubusercontent.com/datalab-to/marker/master/MODEL_LICENSE)另设条件；当前部分后端涉及 Docker/vLLM 或 llama-server |

### 补充参考与未入选原因

- [PaperMage](https://github.com/allenai/papermage)：Apache-2.0，适合学习页面、文本、布局分层表示；作者说明短期不太可能定期维护，因此不作首选解析依赖。
- [ScholaRAG](https://github.com/HosungYou/ScholaRAG)：流程贴近“收集—去重—纳排筛选—PDF—分块—问答—方法文档”。README 声称 MIT，但本次未取得并核实独立 LICENSE 正文；只作流程参考，不把成本与准确率宣传视为实测，不直接复制代码。
- [CORE-Bench](https://github.com/siegelz/core-bench)：基于作者代码与数据的计算复现评测，[论文](https://arxiv.org/abs/2409.11363)报告 90 篇论文／270 个任务。代码 MIT；借鉴环境检查、运行与结果核验任务拆分，当前不下载运行胶囊。
- [PaperBench](https://github.com/openai/frontier-evals/tree/main/project/paperbench)：借鉴论文复现的分层评分规则与任务分解。它要求更完整的复现运行，不等同于我们的官方代码复现准备核查；本轮仅参考[官方说明](https://raw.githubusercontent.com/openai/frontier-evals/main/project/paperbench/README.md)，不引入整套评测运行环境。

## 3. Hugging Face 数据集

公开论文正文、问答评测、摘要检索和版面标注用途不同。表中“可改造”指具备匹配任务的公开字段，不代表已经验证整库加载，也不代表统一覆盖每篇论文的权利。

| 数据集／准确入口 | 规模与实际内容 | 推荐用途／必要改造 | 许可与边界 |
|---|---|---|---|
| [allenai/qasper](https://huggingface.co/datasets/allenai/qasper) | 1,585 篇 NLP 论文、5,049 问题；按论文 train/validation/test 为 888/281/416；全文、章节、人工答案和段落证据 | **P2 独立外部基准首选**；仅索引正文，映射章节／段落到 chunk | CC BY 4.0；没有显式 PDF 页码、代码或 commit；不是 CV 专项集 |
| [yale-nlp/SciDQA](https://huggingface.co/datasets/yale-nlp/SciDQA) | 2,937 个真实审稿问题与作者答复；HF 字段含论文 ID 和 Initial/Revised 版本 | **真实问题／版本追踪参考**；从[作者仓库](https://github.com/yale-nlp/SciDQA)关联全文，重新标证据 | ODC-By 1.0；HF 本身不含全文／证据位置；作者回复可能依赖文外实验 |
| [allenai/SciRIFF](https://huggingface.co/datasets/allenai/SciRIFF) | 约 137K 指令样本、54 任务；input/output/metadata，包含问答、抽取、摘要等 | **功能和评测实现参考**；按任务筛选输出格式，借鉴[官方 evaluator](https://github.com/allenai/SciRIFF) | 集合 ODC-By，底层任务各有许可；含 QASPER 派生数据，须去重；不是统一全文包 |
| [allenai/scifact](https://huggingface.co/datasets/allenai/scifact) | 约 1.4K claims、5,183 篇摘要；证据文档、句子索引与支持／反驳标签 | **引用支持／反证的辅助评测**；以原始 claim ID 统计，避免 HF 展开行重复 | HF 标签与[作者当前许可](https://github.com/allenai/scifact/blob/master/LICENSE.md)有差异；当前 claims/evidence CC BY 4.0、摘要 ODC-By；下载时固定文件版本 |
| [arxiv-community/arxiv_dataset](https://huggingface.co/datasets/arxiv-community/arxiv_dataset) | 机器可读 card 约 235 万行／3.06GB；标题、摘要、分类、DOI、日期、license | **论文发现／摘要筛选**；筛 cs.CV/cs.LG，小量按需取全文 | 元数据卡 CC0；不含全文 PDF，不能推定所有论文全文 CC0；卡正文旧规模约 170 万 |
| [sentence-transformers/s2orc](https://huggingface.co/datasets/sentence-transformers/s2orc) | title–abstract 约 4,177 万对；另有 title/abstract–citation 对；只有字符串对 | **远期 embedding／推荐训练候选**；当前不下载 | 卡未声明许可；不是结构化全文 S2ORC，无页码／证据；不能套用新版 S2ORC API 许可 |
| [docling-project/DocLayNet](https://huggingface.co/datasets/docling-project/DocLayNet) | 80,863 页、11 布局类；PNG、COCO框、单页 PDF、文字坐标 JSON | **解析验收参考**；取 scientific_articles 小样本，不训练新模型 | CDLA-Permissive-1.0；原 ds4sd ID 已重定向；有页码／框，无 QA |
| [opendatalab/OmniDocBench](https://huggingface.co/datasets/opendatalab/OmniDocBench) | 当前 v1.6 官方说明：完整标注 1,651 页＋296页 hard subset；布局、阅读顺序、公式、表格真值 | **独立解析 benchmark 候选**，不进入产品基础语料 | 数据明确仅科研、不可商用；HF imagefolder 行数不等于标注页数；代码许可不覆盖数据 |

### 样本核验观察

- QASPER 的 paper `1909.00694` 有章节、自由答案和证据段落；存在空段与 BIBREF/FIGREF/SECREF 占位符，转换时应保留映射。图表证据可能只有 caption，不能当成表格单元格真值。
- SciDQA 首行 `pid=0gouO5saq6K, version=Initial` 只有问题和答复；若配终稿全文，会制造版本错误。
- SciRIFF 实际样本包含引用意图分类任务，输出是 `Background`。其中的任务指令是数据，不是对开发代理的指令，也不是可以直接索引的论文正文。
- 不采用第三方 TB 级 S2ORC 全文镜像：本次发现示例 ID 不一致和 viewer schema 错误，未验证可加载，来源和体量不适合当前节点。

## 4. 复用验收方法

1. **从任务反推项目**：分别搜索 scientific literature RAG、paper QA citations、systematic review screening、PDF layout、reproducibility benchmark；通过作者论文／官网找到一手仓库。
2. **逐层核验**：README 确认功能，LICENSE 确认代码，模型卡确认权重，dataset card 与原作者文件确认数据。记录核验日期；正式引入时再固定 release/commit 和哈希。
3. **读样本而非只看名称**：确认是否有全文、答案、证据、页码、代码；规模区分论文数、问题数、展开行数和不同配置，不把镜像宣传当作加载结果。
4. **按模块试用**：同一 Swin PDF 比较 PyMuPDF 与 Docling，检查阅读顺序、章节、训练设置、表格、物理页码／坐标、耗时、内存和失败行为。复杂公式需单独检查，必要时再试 MinerU。
5. **保留统一契约**：Docling 的[文档结构](https://docling-project.github.io/docling/concepts/docling_document/)可表达层次、布局和 provenance。保留结构化 JSON；通过 adapter 映射到本项目 ParsedUnit，不能只导出 Markdown 后丢失定位。
6. **独立评测**：PaperQA2 比较应固定同一语料和问题，记录模型、检索和成本差异；不预先宣称自建系统更好。QASPER 另建外部基准，检查必要证据覆盖与引用支持。
7. **成果必须可解释**：记录采用／改造了哪一部分、为什么、改造后的行为与验证结果；贡献集中在证据对应、核查工具和评测，便于比赛和求职展示。

## 5. 调整后的下一步与交付物

| 顺序 | 操作 | 交付物／完成条件 |
|---|---|---|
| 1 | 同一 Swin PDF 上做 PyMuPDF／Docling 小试；先核验安装约束 | `parser-comparison.md`、结构化输出、版本／耗时／内存／位置样本；据结果定 PDF 后端 |
| 2 | 补齐 P2.1 管线和代码／配置解析 | 来源、解析单元、失败清单、报告、抽查样本；页码／行号／版本可回溯 |
| 3 | 转换 QASPER 小样本并隔离标签 | 独立 `qasper_external` 数据与 manifest；先用 train 10–20 篇调格式，再用独立 validation 论文评测 |
| 4 | 按原 P2.2–P2.6 分块、建索引、检索、引用问答、开发集基线 | Swin 主结果与 QASPER 外部结果分开报告 |

现有 Swin 12 开发题＋8 冻结测试题保持原定义。QA、标准答案、gold evidence 不进入索引；公开基准与本地冻结集分别保存。SciRIFF/QASPER 按论文与来源问题去重。实施采用 QASPER 两个小型官方 Parquet 传输 shard，最终只输出所选论文，未下载原 test；Vue/FastAPI 技术选择沿用原计划。

**2026-09-16 P2.2实施更新：** 已消费Docling／现有代码配置结构，生成Swin 1,602块和独立QASPER 2,357块，原文、位置、上下文和重建验收通过。详见 [分块交付说明](p2-chunking-guide.md)。下一节点P2.3实际Embedding输入核验和Qdrant索引；PaperQA2继续留在P2.5接入与P4领域改造，Kotaemon留在P3/P5。
