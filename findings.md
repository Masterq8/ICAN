# 发现与决策

## 用户与目标
- 用户为计算机专业研二，研究方向为图像识别，熟悉 Python，能够基本读懂 Spring Boot + Vue 系统。
- 求职目标偏向大模型应用与 Agent 开发。
- 比赛要求在 2026 年 9 月 30 日前提交应用方案、演示视频和可运行程序。

## 产品发现
- 产品定位：基于 RAG 与 Agent 的计算机视觉论文调研及复现准备平台。
- 基础能力：论文筛选、结构化信息提取、多论文比较、带引用报告。
- 差异化能力：将论文描述与官方代码、配置和运行入口对齐，输出复现核查结论。
- 结论状态必须区分“确认一致”“发现差异”“证据不足”，避免把未找到信息误判为错误。

## 技术发现
- 论文自然语言适合语义检索；参数名、路径和配置字段适合关键词检索，因此需要比较向量、BM25 和混合检索。
- Swin Transformer 的默认配置、模型 YAML 和命令行参数存在覆盖关系，适合验证 Agent 的多步配置追踪能力。
- Vision Mamba 官方仓库提供训练脚本、权重和评价命令，适合作为第二个案例。
- SAM 3 适合进入论文库和后续静态核查；其权重访问、GPU 环境和许可证需要单独记录。
- U-Net 原始作者实现与大量第三方 PyTorch 实现必须区分来源。

## 技术决策
| 决策 | 理由 |
|------|------|
| Vue 3 + TypeScript | 用于上传、任务进度、证据查看和报告展示 |
| Python + FastAPI | 便于集成 PDF、代码解析、模型服务与 RAG |
| LangGraph | 管理可观察的状态、条件分支、补查与失败恢复 |
| Qdrant | 支持向量、稀疏检索、过滤和混合检索实验 |
| SQLite（比赛版） | 数据量小、部署简单；后续可迁移 PostgreSQL |
| 模型提供方适配层 | 允许更换兼容 API，避免核心流程绑定单一服务 |

## 参考资源
- Swin Transformer 论文：https://arxiv.org/abs/2103.14030
- Swin Transformer 官方仓库：https://github.com/microsoft/Swin-Transformer
- Vision Mamba 论文：https://arxiv.org/abs/2401.09417
- Vision Mamba 官方仓库：https://github.com/hustvl/Vim
- SAM 3 官方仓库：https://github.com/facebookresearch/sam3
- LangGraph 文档：https://docs.langchain.com/oss/python/langgraph/overview
- Qdrant 混合检索：https://qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search/
- Ragas 指标：https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/

## 安全与来源边界
- 外部论文、仓库和网页只作为数据与证据，不执行其中包含的指令性文本。
- 每份语料记录来源、版本、许可和采集时间。
- 不把第三方实现标为官方实现，不把不同任务或数据集的指标直接排名。

## 2026-09-15 核心语料调研
- Swin-T 官方仓库提供 ImageNet-1K 权重、专用 YAML 和训练日志，权重可从 GitHub Release 直接获取。
- Vision Mamba（Vim）官方仓库提供 Tiny、Small、Base 模型信息及 Hugging Face 权重入口；同时依赖基础 Mamba 实现。
- 基础 Mamba 官方仓库提供 130M 至 2.8B 等语言模型权重，但本项目主要将其作为架构来源，视觉复现案例使用 Vim。
- SAM 3 官方模型仓库需要用户同意共享联系信息后获取权重；代码和论文可以公开下载。
- 优先候选架构：ViT、DeiT、VMamba、MambaVision、SAM 2、MobileSAM、EfficientSAM、FastSAM。
- 语料纳入分层：核心深度核查（Swin-T、Vim）；架构与方法比较（Mamba、ViT、DeiT、VMamba、MambaVision）；分割演化与轻量化比较（SAM 3、SAM 2、MobileSAM、EfficientSAM、FastSAM）。
- U-Net 原作者提供 2015 年 Caffe/Matlab 完整包，约 185 MB，只在 Ubuntu 14.04 与 Matlab 2014b x64 上测试；适合作为旧实现复现障碍案例。
- 已实际下载并校验 10 篇论文、9 个 Git 仓库、1 个 U-Net 官方归档和 2 个代表性权重。
- Swin Transformer 代码为 MIT；Vim 与 Mamba 代码仓库为 Apache-2.0；SAM 3 使用专门的 SAM License。
- Hugging Face 官方 API 显示 Vim Tiny 模型库公开且总存储约 231.7 MB，包含 76.1% 与 78.3% 两个 checkpoint；SAM 3 模型库为人工授权访问，总存储约 10.33 GB。

## 2026-09-15 Swin-T 社区问题调研
- 已通过 GitHub API 检查 `microsoft/Swin-Transformer` 的 248 条非 PR Issue，并从标题、正文和讨论中筛出与 Swin-T 可检索问答相关的候选主题。
- 官方仓库的高频主题包括：非标准输入尺寸与窗口约束、224→384 微调、梯度累积等价性、配置覆盖、绝对/相对位置编码、复现精度、特征图尺寸、Patch Merging、FLOPs 与权重衰减。
- 代表性 Issue：#96（112×112 输入与窗口）、#107（梯度累积）、#114（高分辨率微调）、#129/#210（阶段输出与代码结构）、#154（APE）、#176（weight decay）、#180（复现差异）、#256（Patch Merging 与卷积）、#306（PatchEmbed 后归一化）。
- 技术论坛补充了更接近真实用户的问法：TorchVision 构造器中如何修改 stochastic depth、100×100 输入迁移学习、线性嵌入在代码中如何实现、量化，以及 Hugging Face 中 Swin 分割和掩码图像建模接口。
- 社区帖只用于发现真实问题、原始措辞和难点；标准答案必须回到固定版本论文、官方代码、配置和官方文档核验。未解决的 Issue 或普通用户回复不能直接充当金标准证据。
- Reddit 论文讨论集中在 Swin 与 ViT 差异、移位窗口与滑动窗口的延迟差异、复杂度公式等概念问题；其中观点性比较需要排除或改写成可由论文证据判定的事实问题。
- 相关实现仓库能暴露“同名模型、实现不同”的版本问题：TorchVision #6227 讨论动态分辨率，#7103 记录 dropout 的历史缺陷，#6558 讨论与原始实现的可配置性差异；Hugging Face #19780 讨论 ONNX 导出输出差异。这些题材必须显式绑定实现、版本和 commit。
- 论文讨论中“为什么 shifted windows 比 sliding windows 延迟更低”和“复杂度公式中的各项从何而来”具有较好的检索价值：它们需要论文公式、正文说明和实现共同支持，适合做多证据题；社区回复仍只作为问题线索。
- 首版 20 题不应随机从帖子抽取。建议按问题簇、证据类型和难度配额选题，并以问题簇为单位切分 12 题开发集与 8 题冻结测试集，避免同义问题泄漏。
- Swin-T v1 评测集已完成：31 条候选来源、27 个证据 ID、12 个开发题和 8 个冻结测试题；难度分布为 L1=4、L2=7、L3=6、L4=3。
- 论文 Table 1(a) 报告 Swin-T 224² ImageNet-1K top-1 为 81.3，而固定仓库 README 报告 81.2。这是首版数据集中的明确冲突证据题，系统必须并列报告来源。
- 当前 Python 环境缺少 PyTorch，因此 112 输入失败链、stage 形状和学习率计算采用论文、配置与代码静态交叉核验；P2 建立运行环境后再补可执行验证。

## 2026-09-15 开发环境
- 已创建 `ican` Conda 环境，使用 Python 3.11.16；环境位于 `D:\CondaEnv\ican`，避免占用空间较紧张的系统盘。
- RTX 5060 Laptop GPU 可被 PyTorch 2.11.0+cu128 正确识别，CUDA 矩阵运算和 Swin-T 官方权重前向推理均通过。
- 基础栈已覆盖 FastAPI、LangGraph、Qdrant 本地模式、BM25、Sentence Transformers、Transformers、论文/代码解析、Ragas 和测试工具。
- Ragas 0.4.3 与 2026 年最新依赖存在未声明完整的兼容边界：需保留 `langchain-community==0.3.31`、OpenAI SDK 2.x 与 `langchain-openai==1.1.9`，否则会在运行时导入失败。
- Swin 官方固定代码在当前 timm/PyTorch 上可以运行，但会报告旧导入路径与 `torch.meshgrid` 的未来弃用警告；这不影响当前推理结果，后续不应直接修改第三方语料仓库来消除警告。

## 2026-09-16 P2.1 解析设计
- 已核对 Swin 官方仓库 HEAD 与固定 commit 一致，工作区没有跟踪文件改动。
- Swin 论文无 PDF 书签，正文为双栏，存在独立公式块和跨栏图表；解析须保留文本块 bbox 并处理阅读顺序，不能将普通逐行抽取直接认作完整段落顺序。
- 预览时再次遇到 Windows GBK 无法输出 PDF 连字字符；任务命令改用 `PYTHONIOENCODING=utf-8`，产物统一写入 UTF-8。
## 2026-09-16：开源科研项目与论文数据集复用

- 详细一手来源、许可、字段、样本观察和采用顺序已汇总到 `docs/reference-projects-and-datasets.md`。
- Docling 优先评估 PDF 解析；PaperQA2 可作问答参考基线，已支持代码文件；差异化应落在论文版本、代码函数、配置覆盖与可定位核查证据。
- ASReview 参考筛选决策记录，Kotaemon 参考引用体验，OpenScholar/STORM 参考报告和补查；当前不全量迁移或下载大规模检索库。
- QASPER 有全文／段落证据，无 PDF 页码；SciDQA 是真实审稿问答，HF 不含全文；SciRIFF 是多任务指令集，来源任务许可不同。外部评测必须与 Swin 冻结测试隔离。
- P2.1 已有解析初稿但无管线／测试／产物；用户新增复用调研后暂停，下一步是相同 Swin PDF 的解析后端比较。

## 2026-09-16：P2.1 复用实施与验收完成

- 采用 Docling 2.127.0 主后端，固定 Heron／TableFormer 实际模型 commit，保留原始结构 JSON；PyMuPDF 作轻量后端与少数失效字符范围的坐标恢复。
- 单篇固定 Swin14页的 Docling 最终串行缓存补测22.209秒、RSS峰值2495.2MB；轻量后端约0.20秒／69MB。Docling 的价值在结构化信息，不在此篇速度优势。
- 论文14页＋仓库83文件，共97单元、1496结构位置；0错误、13警告（10候选表格、3跨页范围恢复）；核心4个产物重复重建哈希一致。
- QASPER 实际格式为嵌套列数组，采用官方 Parquet 固定 revision，无需执行旧脚本。20 train／10 validation 论文、2354正文／caption单元；答案放独立 eval 目录，1条训练证据无法映射已保留记录。
- 三轮有针对性的独立代码审查修正了隐藏 Git 修改、跨页定位、单页失败隔离、超大文件／读取失败和缺失 provenance；最终20测试与Ruff通过，无剩余重要审查问题。
- 当前完成解析与外部数据格式准备。P2.2 分块、P2.3索引和P2.4–P2.6问答／评测仍待实施；不要将原“暂停”记录视为当前状态。

## 2026-09-16：用户选择基于PaperQA2做领域改造

- PaperQA2由参考基线提升为主要问答／Agent框架复用目标；具体LLM与Embedding另选。推荐公开接口＋领域adapter，小范围上游修改仅在实测接口缺口时考虑。
- P2.2继续先完成来源可回溯的结构化分块；P2.5验证固定版本PaperQA2对外部chunks／检索／引用的接入，P4增加代码与配置核查工具。
- 不预先承诺PaperQA2默认Numpy存储与Qdrant兼容；如需LangGraph，明确其外层业务职责，避免重复内部Agent循环。
- 已同步task_plan.md、需求技术结构、开发主线和调研文档；本轮只调整计划，未执行分块或安装PaperQA2。

## 2026-09-16：P2.2分块方法与交付

- 先固定已验收的parent输入，再沿结构区域划分原文；嵌套函数／字段选择最内层，结构空隙也覆盖。长结构只在自身内部重叠，所有非空白字符必须有证据块。
- 检索上下文与连续原文严格分字段；补充表头属于元数据，不可当作原文引用。表格review状态必须一路传递，本次10个候选表格产生15块。
- Swin1,602块、QASPER2,357块通过定位和覆盖验收；全部embedding输入在cl100k预算768以内，但这不是Embedding模型tokenizer兼容保证，P2.3仍必须复核。
- 文件行号必须按CR／LF／CRLF计算，不能用广义Unicode splitlines；代码字符串内U+2028等字符不是Python物理换行。YAML解析字符标记也应回到源文件位置。
- 成功标记最后发布，构建／验证前清理旧标记；目录检查之外还需拒绝链接输出，Windows硬链接不需要符号链接权限。
- Verifier从parent对照正文、来源、结构和上下文；仅正文相等不能发现伪造的表头或embedding prefix。原文覆盖验收证明与已保存解析文本一致，不替代表格与PDF语义人工核验。
- 12个产物重建哈希稳定，11个输入／eval哈希未变；参数未使用冻结答案。独立QASPER保留split和段落／caption位置。
- 详细数据契约、方法、参数、命令和边界见docs/p2-chunking-guide.md；下一节点P2.3，PaperQA2保持P2.5/P4模块复用目标。

## 2026-09-17：P2.3本地Embedding与持久化验证

- 选择固定revision的BGE-M3 dense-only：支持中英文，1024维、8192输入上限，原始查询无需额外指令。选择依据是输入兼容与本地可运行性，尚未证明本项目效果优于其他模型。
- cl100k分块预算不等于模型token数；实际XLMRobertaTokenizer计数为55–1127，3959条输入全部无截断。模型加载前校验11个官方文件身份，同时拒绝未登记替代权重或配置。
- 三个Qdrant collection隔离Swin、QASPER train／validation；完整chunk、来源定位、review标记和输入哈希随payload保存。配置、模型账本、输入快照与库版本决定索引版本；staging验收后原子发布。
- RTX 5060 Laptop 8GB完成真实编码，构建及关闭重开核验93.382秒，不含下载和前置校验；PyTorch峰值allocated约1296MiB、reserved2152MiB，不代表总显存。
- 新进程逐点对照3959个payload及向量，再复核真实tokenizer；重复构建复用。79测试通过／1权限跳过，61个原输入及eval哈希未变，冻结答案未用于调参。
- dense功能查询暴露Swin配置变体混淆；config类型过滤不足以确定标准Swin-T／224。P2.4提供路径约束，P3评估BM25／混合检索；查询返回不等于准确率验收。
- Qdrant local单进程持有目录锁，P2.4需单客户端／单worker；并发部署再切换server。完整契约、命令与证据见docs/p2-indexing-guide.md。

## 2026-09-17：P2.4证据检索接口

- 将P2.3的不可变索引封装为FastAPI只读接口，数据边界保持在chunk与来源定位：检索层不得生成或改写答案，方便后续分离检索、生成和Agent评测。
- `source_path`是快照内的完整相对路径，不是仓库内简写路径。真实Swin路径前缀为`data/raw/repositories/Swin-Transformer/configs/swin/`；API严格拒绝绝对路径、反斜杠及`..`。
- Qdrant的`MatchPrefix`可在local模式直接执行路径前缀约束。真实HTTP smoke表明它消除了SwinV2／SwinMoE目录混入，但不证明检索答案正确；P3仍需混合检索与实体约束评测。
- 模型、Qdrant和数据库都按首次证据查询惰性加载；health不会触发。local Qdrant只能单worker，日志不记录查询文本或证据正文。
- 单worker不等于单请求。服务须用进程内互斥锁覆盖每次本地Qdrant的打开、查询和关闭；首次启动还须在同一锁下完整比对immutable索引的identity、payload与向量，成功后才缓存可服务状态。

## 2026-09-17：P2.5公开接口核验

- PaperQA2当前官方稳定版2026.8.12，固定源码commit 57e89f7223b0960d5ee5ea048c69e3c47e088572。现有QdrantVectorStore接收序列化Text，不兼容本项目chunk payload，直接复用现有集合会失败。
- 公开aquery可消费带Context的PQASession；推荐保持检索独立，通过Doc／Text／Context adapter实际复用回答和引用流程，P4再加入Agent。
- 上游会剥除伪引用ID，必须先检查raw_answer；Text extras若携带dict可能hash失败，完整location放本项目注册表。默认serializer按score／name排序，dense分数不可伪装成0–10相关性。
- 首次依赖dry-run要求packaging降为25.0，实际安装后仍需pip check及旧流程回归；本轮未安装。运行时模型API与开发助手模型是独立配置。
- 详细一手来源和接口边界见docs/paperqa2-integration-investigation.md；P2.5实现尚未开始，不能将调研标记为接入完成。

## 2026-09-17：P2.5接入实证与失败方法

- 外部Context适配能保留既有Qdrant证据：公开aadd_texts、预置PQASession.contexts及aquery均实际执行，不需要迁移payload或fork。
- raw_answer仍可能已经被上游清理：默认示例ID在赋值前删除。正确边界是捕获LLMResult.text，再做本项目注册表校验；ID和定位通过只代表结构有效，语义支持留正式评测。
- OpenAI SDK单调用+fhlmi结果契约允许明确关闭重试，避免LiteLLM未登记新模型的路由／成本猜测；cost未知必须null，不能写零。
- 真实DeepSeek模型列表验证deepseek-flash存在，使用OpenAI兼容接口并关闭思考模式；开发工具模型与作品服务配置相互独立。
- 首轮论文题因未问到的细节扩展触发证据不足：保留失败记录、从证据与回答定位原因、修正prompt到v2后仅复核失败样例。配置样例v1已通过，不额外重跑；不是正式效果比较。
- 共3次调用6139输入／1144输出tokens，配置定位YAML6–9行，论文定位PDF2／4页；全部结果保留在忽略的data/processed/qa。123测试通过／1权限跳过，六个identity库和61受保护文件未变。
- 下一节点固定P2.6问题、语料、模型、prompt与预算，再分别报告Swin开发集和QASPER validation，冻结测试不参与调参。

## 2026-09-17：P2.6检索基线与评测边界

- 真实Top8 dense查询47题：Swin必要定位召回32.64%，完整仓库行范围覆盖8.33%；近似SwinV2／MoE／MLP／SimMIM变体普遍混入，这是P3精确实体与混合检索的实证入口。
- QASPER validation有32题／57标注，31题适用非空可回答证据召回，完整段落宏平均78.49%；1份可回答标注无证据、4份unanswerable标注需保留适用性分母。
- 论文页码标注不能当成完整语义证据范围；代码多个区间及additional_path必须联合覆盖。QASPER字符区间需覆盖整个原段落非空白字符。
- 默认PaperQA2 serializer最多5sources并按score/name排序，本项目输入8块不能全部算实际送入。production中文prompt与英文QASPER的F1语言不一致，评测单独采用问题语言协议，在train检查后固定。
- 默认配置对照不等于完整上游Agent／检索基线；官方QASPER词面F1与语义正确性分开报告，未生成指标null。
- 密封快照SHA和chunk artifactSHA是复现的一部分；仅检查case key或允许检索命令重新赋hash，会破坏两版同证据对照。started-only调用必须出现在失败分母，未知tokens不可算零费用。
- 生成预算待用户回复，本轮调用0；独立审查全部重要问题已修复，136测试通过／1权限跳过。详见docs/p2-baseline-report.md。
## 2026-09-17：P2.6真实对照与评测口径

- 用户授权助手决定调用量；94次真实生成够覆盖双版47题。实际用量180661输入／19786输出，按官方高峰cache-miss假设估算0.0779415USD；账单临时路径失效，实付未知。
- 同快照并不表示相同实际prompt证据：PaperQA2默认排序且最多5sources，领域版保留检索排名最多8块；目标YAML在默认版可能被丢弃，不能把提升只归因prompt。
- QASPER词面答案F1为16.95%／8.42%，助手完整判断21／18题；长度、布尔解释、中文输出及歧义会影响词面F1。审核未经人类独立复核。
- Swin49评分点覆盖18／16，两版完整答句均0。定位命中不能保证函数实现完整，警告日志也不能当成state_dict删除；更强生成模型不能补齐版本／配置链缺证据。
- 9条自然拒答未被原始regex识别。保留原协议分数并另记语义拒答，下一协议再修，不在看到validation后回写本轮。
- QASPER占位公式、仅caption表格及参考冲突保持明确边界；审核需绑定具体答案及引用hash，不能对相同问题的新答句复用旧判定。
## 2026-09-17：P3起步与实现范围

- P2.6暴露标准Swin与V2／MoE／MLP／SimMIM混入，以及默认值→YAML→入口运行时覆盖链缺失。检索索引、正文和冻结文件保留原版本。
- 方案比较：只增加family过滤不能解决精确字段；BM25＋dense融合＋本地重排可分别验证贡献；LLM查询改写会额外消耗调用并增加实验变量，首版使用可记录的确定性术语／标识符展开。
- 本机RTX5060 Laptop有8GiB显存，选BAAI/bge-reranker-v2-m3多语言模型，Apache-2.0；官方revision953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e，safetensors2271071852字节，推理FP16小batch。
- 配置已按完整字段路径分块，但返回原文只有单行；BM25需要字段／结构名和路径，回答端需要解释实际覆盖关系，不能将补查上下文误称自动配置执行结果。
- 读取不存在的retrieval/models.py已改为实际schema.py；Kotaemon GitHub main/raw路径404，接下来核对实际HEAD／默认分支再定向读取，不把失败当成已参考源码。

## 2026-09-18：P3校准与可复现约束

- 已实际阅读Kotaemon固定HEAD 9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9的libs/kotaemon/kotaemon/indices/vectorindex.py，仅借鉴过滤→双路候选→重排→TopK流程，未复制／安装模块。RRF及领域范围、结构锚点由本项目实现。
- BGE-reranker权重普通下载停滞，Range响应206及精确Content-Range可用；按32MiB并行4路续传，最终校验官方SHA和7个allowlist文件。缓存不进Git；FP16 batch2与BGE-M3同驻GPU已实际跑通。
- 首轮机械补充同类方法会挤掉论文／默认值证据，故具名结构和显式YAML配置链优先于任意高排名类。规则来自query/固定术语与已入库metadata，允许dev/train校准，不使用冻结题、validation gold或社区回复作检索提示。
- 即使每块正文/来源正确，跨索引恢复也会使消融不可信；manifest现在绑定实际验证的index fingerprint/identity/manifest SHA，所有恢复记录必须同指纹且匹配manifest；seal只能在完整282条时生成。

## 2026-09-18：P3验收方法与边界

- 将检索收益与答案收益分开：Swin必要定位80.56%不等于正确率；40/49评分点仍有额外归因错误，完整仅4/12。专用路径0/96混入不保证共享config里的SWIN_MLP分支正确归因。
- 实际短HTTP查询补充开发集覆盖面：长题能保留具名YAML，不代表短题也能。修复要保留原失败查询，追加左右ASCII标识符边界回归，不能用更长的有利问题替换验收。
- 代码修复后不应把旧审查直接搬到新答句。先用新检索重跑实际PaperQA2准备过程，比较context／system／qa／metadata rank与score／预算及包含ID；47题输入一致时记录等价证据，不重复生成，也不创造不存在的新答案。
- 外部已观察validation只能做回归：P3召回与两个官方F1下降、语义完整19/32也低于原21/32。默认dense保留，按任务选策略应由新留出题验证，不能在这32题上反复调参后称盲测改善。
- LLM有正确公式也会算错：dev06把0.001×2写成0.512。P4需要确定性计算及输入引用，不用增加重排序或更长prompt假装已经修复。
- dev12对动机的部分拒答被旧regex漏识别。保持原P2.6协议公平对照，绑定新的语义审核另列差异；不回填journal改变旧评分。

## 2026-09-18：P4工具与Agent接入

- 固定PaperQA2有PaperQAEnvironment.make_tools／make_initial_state／step扩展入口，实际经Aviary函数注入state并记录tool_history。上游run_agent会创建其它索引、做默认摘要且在超限后自动回答，故本项目只复用环境与证据问答，以显式SDK预算驱动原生工具调用；不是原样上游Agent基线。
- 上游step默认handle_tool_exc=True，模型超时可变成工具字符串，不能只在外层捕获异常。gen_answer保存ModelTimeout类型，driver恢复timed_out；不能自动补答。
- 自由文本与规划参数不是核验过的用户覆盖。API补user_overrides，生产工具逐值严格匹配，底层未核验参数仅partial／requires_review；同字段AST取值避免SWIN_MLP分支错引用。
- Decimal精确计算只能保证表达式运算，不能保证模型选择的参数正确。首轮LR数值正确但缺默认5e-4来源，仍必须核对原始配置证明；允许config_path空串直接检查默认，避免模型猜配置名。
- code/config型工具结果不生成假chunk，保留原始字符／行号及commit，工具artifact另记；最终保留的证据不覆盖artifact全部依据时不把该artifact送入模型。
- 三次真实shape预算失败说明停止提示不可靠：单标量契约必须明确，最后一轮工具权限也需受状态约束。收尾只在预算内已有证据时开放gen_answer，不是预算后自动补答。
- v5生成的shape回答仍将7//2=3当作实际执行，忽略已有PatchMerging偶数assert，还编造窗口整除断言。正确算术与原文ID不能保证结论；应先检查代码前置条件，再区分实际／假设计算，逐claim标支持或不足。
- P4当前Pro／Flash关闭thinking。模型名记录与真实response一致，但未验证思考模式收益；后续若引入应单独设预算／版本，不改旧轨迹或将源码混合的开发案例拼准确率。
- 本轮39调用、9真实任务，0.33249426USD仅当日高峰全cache-miss估算。保留3次budget_exhausted和动机状态漏判；不把执行completed作为语义通过。下一P4.3优先条件核查，外部Agent评测属P4.4。
