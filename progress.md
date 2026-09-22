# 进度日志

## 会话：2026-09-15

### P0：立项与文档体系
- **状态：** complete
- 已确认软件赛道、网页形态、RAG + Agent 主线和 Swin-T 首个案例。
- 已建立持久化计划、发现记录和进度日志。
- 已建立问题解决日志、开发路线图和需求规格说明书。

### P1：首个语料集与标准答案
- **状态：** complete
- 已下载并校验 10 篇论文、9 个 Git 仓库、2 个代表性权重和 1 个 U-Net 原作者归档，总计约 653 MB。
- 已固定仓库 commit，记录代码许可、权重访问条件、文件大小和 SHA-256。
- 已建立 `data/catalog/models.json` 机器可读目录与 `docs/corpus-manifest.md` 人工清单。
- 已筛选 ViT、DeiT、VMamba、MambaVision、SAM 2、MobileSAM、EfficientSAM、FastSAM 和 U-Net 等候选。
- 已检查 Swin 官方仓库 248 条非 PR Issue，并补充调研 TorchVision、Hugging Face、SwinIR、PyTorch Forums 与论文讨论。
- 已建立 `docs/swin-t-evaluation-methodology.md`，记录首轮 27 个真实候选来源、证据分级、质量门禁、20 题配额和 12/8 分组冻结规则。
- 深挖配置、resume 和微调主题后，机器可读候选池扩展到 31 条真实来源。
- 已建立 27 个统一证据 ID，完成 12 个开发题和 8 个冻结测试题；每题包含标准答案、claims、必要证据、评分点、来源 URL 和泄漏分组。
- 已生成数据集 manifest 与 SHA-256，冻结测试集状态为 `frozen`。
- 下一动作：进入 P2，搭建 PDF/代码解析、分块和基础检索索引，只用开发集调试。

### P2：开发环境
- **状态：** complete
- 已创建 `ican` Conda 环境（Python 3.11.16），安装 PyTorch 2.11.0+cu128、TorchVision 0.26.0+cu128 及 RAG/Agent/解析/后端/测试依赖。
- 已生成直接依赖清单、CUDA 专用清单与完整精确版本锁文件，并注册 `Python (ican)` Jupyter 内核。
- 已解决 Ragas、LangChain Community、Instructor 与 OpenAI SDK 的运行时兼容问题。
- 已增加可重复运行的环境冒烟脚本。
- 下一动作：实现只索引语料、不索引答案的 PDF/代码结构化分块管线。

## 创建的文件
- `task_plan.md`
- `findings.md`
- `progress.md`
- `docs/problem-solution-log.md`
- `docs/development-roadmap.md`
- `docs/requirements-spec.md`
- `docs/swin-t-evaluation-methodology.md`
- `docs/swin-t-evidence-map.md`
- `docs/swin-t-evaluation-set-v1.md`
- `data/eval/swin_candidates.jsonl`
- `data/eval/swin_evidence.json`
- `data/eval/swin_dev.jsonl`
- `data/eval/swin_test.jsonl`
- `data/eval/swin_eval_manifest.json`
- `environment.yml`
- `requirements/torch-cu128.txt`
- `requirements/ican.txt`
- `requirements/ican-lock.txt`
- `docs/environment-setup.md`
- `scripts/smoke_environment.py`

## 验证结果
| 检查项 | 预期 | 状态 |
|------|------|------|
| 三份用户要求的文档存在 | 问题日志、开发主线、需求文档均可独立维护 | 通过 |
| 路线图有节点与交付物 | 每个节点均含完成标准和产物 | 通过 |
| 需求文档突出 AI 核心作用 | RAG、Agent、证据校验均有独立说明 | 通过 |
| 使用说明完整 | 覆盖建库、筛选、问答、核查、报告 | 通过 |
| 核心论文文件 | 10 个文件均具有 `%PDF-` 文件头 | 通过 |
| 核心权重文件 | 2 个权重均为完整 PyTorch ZIP 格式并完成 SHA-256 | 通过 |
| U-Net 原作者归档 | GZip 文件头有效，`tar -tzf` 可正常列出内容 | 通过 |
| 模型目录 JSON | 可被 PowerShell `ConvertFrom-Json` 解析 | 通过 |
| 关键代码路径 | Swin 配置、Vim 脚本、Mamba 模块、SAM 3 训练文档均存在 | 通过 |
| 社区来源覆盖 | 官方 Swin Issue 14 条、相关实现 Issue 5 条、论坛/论文讨论 8 条 | 通过 |
| 评测方法边界 | 明确社区来源不作为金标准，并定义证据闭包和版本约束 | 通过 |
| 开发/测试切分 | 12/8 配额按问题簇切分，禁止同义题与同证据跨集合 | 通过 |
| JSON/JSONL 结构 | 31 条候选、27 个证据、20 个正式问题均可解析 | 通过 |
| 必要证据引用 | 20 题引用的 evidence ID 全部存在 | 通过 |
| 难度分布 | L1=4、L2=7、L3=6、L4=3 | 通过 |
| 泄漏分组 | 20 个 leakage_group 全部唯一 | 通过 |
| 运行时模型验证 | Swin-T 官方权重严格加载并在 CUDA 上输出 `(1, 1000)` | 通过 |
| Python 依赖一致性 | `pip check` 无损坏依赖 | 通过 |
| 环境核心导入 | RAG、Agent、Web、解析、视觉和评测模块全部可导入 | 通过 |
| 本地 RAG 组件 | PDF、Qdrant、BM25、LangGraph、FastAPI 冒烟测试 | 通过 |

## 错误日志
| 时间 | 错误 | 尝试次数 | 解决方案 |
|------|------|---------|---------|
| 2026-09-15 | `G:\ICAN` 尚不是 Git 仓库 | 1 | 本次仅创建文档，不擅自初始化仓库 |
| 2026-09-15 | PowerShell 文件统计命令出现空管道语法错误 | 1 | 改为先收集循环输出，再格式化 |
| 2026-09-15 | 仓库元数据脚本再次使用同类错误管道写法 | 2 | 后续统一将 `foreach` 输出赋给变量 |
| 2026-09-15 | 页面工具拒绝 Hugging Face API 查询 URL | 1 | 改用 `curl` 读取官方 API，成功获取元数据 |
| 2026-09-15 | 关键路径检查第三次触发同类 PowerShell 管道错误 | 3 | 改用显式数组收集，修正版检查通过 |
| 2026-09-15 | `findings.md` 补丁上下文标题不匹配 | 1 | 重新读取文件，以实际末行作为追加位置 |
| 2026-09-15 | 方法文档首稿引用了错误的 Swin 论文文件名 | 1 | 列出论文目录核对并修正为磁盘真实名称 |
| 2026-09-15 | 系统未安装 `pdftotext` | 1 | 使用已安装的 pypdf 按页抽取论文文本 |
| 2026-09-15 | pypdf 输出触发 GBK UnicodeEncodeError | 1 | 设置 `PYTHONIOENCODING=utf-8` 后抽取成功 |
| 2026-09-15 | `rg` 正则表达式缺少闭合括号 | 1 | 简化为多个普通关键词后成功检索 |
| 2026-09-15 | Windows 通配符路径未被 `rg` 展开 | 1 | 使用 `Get-ChildItem -Filter` 获取真实文件名 |
| 2026-09-15 | 当前 Python 环境没有 PyTorch | 1 | 保留静态交叉核验结果，P2 安装依赖后补运行时验证 |
| 2026-09-15 | Ragas 0.3.1 导入已被 LangChain Community 0.4 移除的 VertexAI 模块 | 1 | 升级 Ragas 并追踪依赖约束；发现仍存在相同导入 |
| 2026-09-15 | Ragas 0.4.3 与最新 LangChain Community/OpenAI SDK 仍有隐式冲突 | 2 | 固定已验证组合并重跑 `pip check`、全模块导入与冒烟测试，全部通过 |
| 2026-09-15 | Conda 拉取元数据时发生一次 SSL EOF | 1 | 保留 SSL 校验并让 Conda 自动重试，环境随后创建成功 |
| 2026-09-15 | `<3` 约束经 `.bat` 被解析成重定向并生成空文件 `2` | 1 | 改为直接调用环境 Python，使用 PowerShell 单引号；已删除空文件 |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | P2：基础RAG，P2.3持久化索引已完成，下一节点P2.4证据检索接口 |
| 我要去哪里？ | 基础 RAG → 改进 RAG → Agent → 网页 → 评测交付 |
| 目标是什么？ | 9 月 30 日前交付可演示的计算机视觉科研 Agent |
| 我学到了什么？ | 见 `findings.md` |
| 我做了什么？ | 见本文件会话记录 |
## 会话：2026-09-16，用户新增开源复用调研

- 暂停 P2.1 解析实现；现有配置、schema 与 parsers 属于未验收初稿，未生成解析产物。
- 检索并核验 GitHub 科研问答、筛选、报告、PDF 解析及复现评测项目；并行核验 8 个 Hugging Face 候选数据集的一手卡、许可与代表样本。
- 新增 `docs/reference-projects-and-datasets.md`，包含推荐模块、实际字段、适用限制、复用方法和具体交付顺序。
- 更新任务计划、P2.1 实施说明、开发主线想法收件箱和问题日志。
- 本轮未安装新增库、未全量下载数据、未运行解析比较；下一步先比较 PyMuPDF／Docling，随后补齐 P2.1。
- 核验冻结测试集 SHA-256 仍为 `5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2`，与原记录一致。

### P2.1：解析复用与交付完成

- 本次用户要求按调整计划执行。完成同篇 Swin PDF 的 PyMuPDF／Docling比较，选 Docling主后端＋PyMuPDF定位恢复；模型与新增库已下载并固定版本。
- 创建本项目 Git 仓库与 `feature/p2-ingestion` 分支，原始下载、缓存、处理产物和环境密钥进入 ignore；未提交或推送。
- 补齐来源契约、解析 adapter、版本校验／文件枚举管线、命令行入口、外部数据转换和独立产物验收。
- 生成 `data/processed/swin/v1/`：85条来源记录、97单元（14论文页＋83文件）、0错误／13警告、1496结构位置。
- 生成 QASPER隔离样本：20训练论文＋10验证论文、2354正文／caption单元；问题和gold标注只存eval侧，未下载原test。
- 核验核心4个Swin产物重复重建SHA一致；原始材料、源仓库commit和冻结测试集保持不变。
- 验证：20项pytest通过、Ruff检查通过、pip check通过；环境冒烟、CUDA与Swin官方权重前向再次通过。独立审查最终无剩余重要问题。
- 文档：`docs/parser-comparison.md`、`docs/p2-parsing-guide.md`；更新调研、需求变更、路线、计划和问题解决日志。
- 下一节点：P2.2结构化分块，再到Embedding／Qdrant。PaperQA2与其他完整应用保留各自后续参考节点；当前未运行问答或外部基准评分。

### 计划调整：PaperQA2作为主要问答／Agent复用目标

- 按用户最新指示调整task_plan.md，明确各参考项目／数据集的复用方式、开发节点和实际状态。
- P2剩余任务拆为P2.2–P2.6及交付条件；下一节点P2.2结构化分块，当前仍为pending，本轮不执行代码。
- PaperQA2由参考基线提升为主要问答／Agent框架复用目标；P2.5固定版本并验证外部chunk、检索与代码／配置引用adapter，P4再增加领域核查工具。
- Kotaemon留在P3/P5；Docling解析、Qdrant检索、Vue/FastAPI接口保持契约边界；LangGraph只在需要时编排外层业务流程。
- 同步记录调研文档、需求和路线图变更；不将框架选择等同于已选LLM／Embedding，不将计划接入标记为已完成。

### P2.2：结构化分块实施与验收完成

- 使用writing-plans／executing-plans落实已确认节点，新增chunk契约、token预算、结构区域、固定输入校验、构建管线及CLI；消费既有Docling结构，没有重新解析PDF。
- Swin 97单元生成1,602块：论文243、代码375、配置894、文档90。10个表格形成15块，全部保留待核验标记。
- 独立QASPER 2,354单元生成2,357块：train 1,659／validation 698，paragraph 2,162／caption 195；段落与caption位置保留，无虚构PDF页或原文件哈希。
- 原文连续切片与embedding上下文分开；哈希、页／物理行、bbox来源、结构／表头、768 token总预算和64 token重叠上限验收通过，覆盖全部1,214,454个非空白字符。
- 60项pytest通过，1项真实符号链接因Windows权限跳过；模拟链接与实际NTFS硬链接用例通过。改动范围Ruff／格式检查通过；全目录扩展检查发现旧smoke_environment.py导入排序问题，与本节点无关，未改动该文件。
- 12个产物重建SHA一致，11个输入及eval文件未变；解析manifest和Swin冻结集符合原固定哈希。物理行辅助函数修正后对现有Swin重新算结构，0处差异。
- 按requesting-code-review进行三轮针对性只读审查，修正标题祖先、链接输出、行偏移／Unicode行、上下文验收和失败标记；最终无剩余重要发现。
- 新增docs/p2-chunking-guide.md，完成实施计划复选框，更新主计划、路线、需求变更、参考调研与问题日志。
- 下一节点P2.3：固定Embedding模型及revision，核验真实tokenizer和模板，建立隔离Qdrant持久化索引。PaperQA2接入仍在P2.5/P4，当前没有生成答案或基准得分。

### GitHub私有仓库备份（2026-09-16）

- 按用户授权上传当前项目到https://github.com/Masterq8/ICAN，仓库为private。
- 新增README和.gitattributes，保存67个源码／配置／文档／来源及评测文件；原始模型、第三方仓库、权重、缓存、processed产物和索引继续忽略。
- 初始提交ac298469f77c301dc854a9cb193f358a665987d0已推送main，origin/main已设为跟踪分支；本地Git历史额外备份于.git/ican-p2.2.bundle。
- 复用Git Credential Manager设备登录解决私有仓库访问，访问token未写入项目；13个数据／配置提交blob与原文件字节一致，冻结集哈希未变。
- 本次仅备份及文档完善，P2.3仍为下一开发节点。

### 2026-09-17：P2.3 Embedding与Qdrant索引验收完成

- 固定BAAI/bge-m3 revision `5617a9f61b028005a4858fdac845db406aefb181`，11个模型文件身份核验通过；模型账本纳入仓库，约2.29GB模型与索引保持忽略。
- 实际tokenizer复核3959条输入，最长1127 tokens、0截断；RTX 5060 Laptop以float16编码，保存1024维float32归一化向量。
- 建立swin_v1 1602点、qasper_train_v1 1659点、qasper_validation_v1 698点，版本指纹为`3fcc38131d303a03b83cbe0dea77dc74b83398f597aee10e6a4fb1fbae9eaa87`。
- 持久化后重新打开逐点比较payload、向量、ID与集合；独立CLI复核实际tokenizer及两条功能查询通过。重复构建返回reused，未重新编码。
- 79项pytest通过、1项Windows真实符号链接权限跳过；独立审查修正模型替代文件及eval完整性检查，最终无剩余重要发现。61个阶段前输入与eval文件哈希未变。
- 新增docs/p2-indexing-guide.md及下载／构建／验收脚本，更新计划、路线、需求和问题日志。
- 功能查询发现仅按config类型过滤会混入SwinV2／SwinMoE变体，待P2.4路径限制与P3混合检索处理；不报告gold正确率。
- 下一节点P2.4：返回可回溯证据的检索接口；PaperQA2接入仍在P2.5/P4。

### 2026-09-17：P2.4检索证据接口完成

- 新增只读FastAPI端点`POST /v1/evidence/search`，请求支持collection、来源类型和安全POSIX路径前缀；响应只含原始证据、来源版本、页码／行号、review标记与分数。
- 服务惰性加载固定BGE-M3，先核验索引manifest和collection；无效请求／collection为422，索引不可用为不泄露内部路径的503。`GET /health`不加载模型。
- 实际HTTP验证显示config类型过滤仍混入SwinV2／SwinMoE；加入真实快照路径前缀后5条结果均在标准`configs/swin/`目录。该结果只验证检索约束，不构成gold正确率。
- P2.5前保留边界：不含回答、摘要、报告、Agent或PaperQA2。开始Agent规划或回答生成前提醒用户切换最高阶模型。
- 独立审查发现并修正同worker并发Qdrant目录争用、以及首次服务未完整验证索引identity／payload／向量的问题；新增并发及篡改回归后，检索测试22项通过。
- 后续复核补充首次并发BGE-M3重复加载风险，已以encoder专属锁修正；五并发请求仅构造一个模型实例。

### 2026-09-17：P2.5开始，官方接入核验

- 用户已按此前提醒切换开发助手模型；本次进入P2.5前置调研。
- 创建codex/p2-5-paperqa2分支；下载只读上游tag v2026.08.12，commit 57e89f7223b0960d5ee5ea048c69e3c47e088572，参考源码不纳入RAG证据。
- 核验aadd_texts、外部Context、aquery、引用格式化及用量统计接口；上游已有QdrantVectorStore，但payload与本项目不同，选择公开Context adapter方向。
- pip dry-run成功解析paper-qa==2026.8.12，发现packaging需由26.3降至25.0；尚未安装，现有环境和索引未变。
- 新增接入核验文档与P2.5设计草案；下一步审阅设计，再按已选当前会话连续执行方式形成计划与实现。
- 已向用户询问作品运行的生成模型服务和预算；未使用开发工具配置中的凭据，未发送生成请求。

### 2026-09-17：P2.5实现与真实功能验收完成

- 用户批准设计并提供DeepSeek服务配置；密钥仅保存本机忽略的.env，未进入代码／记录。当前会话连续执行。
- 安装固定paper-qa2026.8.12及21个新增／变更包，保存前后环境锁；packaging26.3降至25.0，pip check通过，六个索引identity库版本未变。
- 实际复用公开Doc／Text／Context／PQASession及Docs.aadd_texts／aquery；保留原始位置、版本和核验状态，无隐式embedding／summary／补取证据。
- 新增POST /v1/qa/answer，原始LLM引用校验、合法引用编号、证据不足／无效引用／待人工核验状态，以及token和版本元数据。OpenAI SDK单次调用桥接fhlmi结果，关闭重试／fallback，输出最多1536tokens、生成超时90秒。
- 真实检索与真实PaperQA2离线HTTP样例通过。真实DeepSeek先运行论文／配置各一次；配置通过并定位YAML6–9行，论文因主动扩展缺失细节附加证据不足标记而失败。保留v1记录，prompt升级v2后仅追加论文一次，answered并定位PDF第2、4页。
- 合计3次真实生成，6139输入／1144输出tokens；费用未提供为null。未读取冻结gold或运行正式评分；配置通过样例为v1，论文通过样例为v2。
- 独立只读审查发现上游在raw_answer前删除示例引用；已用CapturedAnswerModel捕获未经修改文本并新增回归，复查确认修复。
- 最终123项pytest通过，1项Windows符号链接权限跳过；22项QA测试、scoped Ruff／format、pip check通过。61个受保护文件哈希未变，现有索引版本保持不变。
- 完成问答使用说明、接入报告、问题日志、计划和复用记录；下一节点P2.6开发集基线与独立QASPER结果，批量真实评测前明确预算。P4再做Agent工具规划，P5网页产品化。

### 2026-09-17：P2.6评测管线及本地检索完成，生成预算待选择

- 用户授权开始P2.6，创建codex/p2-6-evaluation分支，固定设计／实现计划。
- 复用官方QASPER evaluator commit afd0fb96bf78ce8cd8157639c6f6a6995e4f9089及Apache-2.0许可；gold用于离线评分，生成case不携带答案／证据标签。
- 固定Swin dev12题、QASPER train格式3题、validation32题。47次dense查询完成；Swin不按gold指定路径，QASPER按原paper_id限制给定论文。
- Top8 Swin定位召回32.64%、必要仓库完整行范围覆盖8.33%；QASPER validation31适用题完整段落召回78.49%，24/32题完整覆盖至少一组非空标注。Swin变体混入已按开发题记录，未用gold改写检索结果。
- preflight快照经固定输入／正文来源复核复用至最终p26-v2，保存初始provenance和密封SHA，避免反复加载／检索。sealed快照不能重新封存覆盖。
- 新增预算累计、started fsync／永久跳过、单写者锁、未知用量与中断失败分母；实际输入ID遵从默认serializer最多5与领域版8。评测领域版仅改答句语言指令，生产prompt不变。
- 136pytest通过／1Windows权限跳过，13评测测试通过；pip check／Ruff通过，61受保护hash未变。独立审查及复核修复全部重要发现。
- 已向用户询问本轮94次双版／47次领域版／暂不生成预算；尚无回复，本轮生成0。答案F1、引用语义、用量成本与逐题审核待执行；P2.6仍in_progress。

### 2026-09-17：P2.6双版真实生成及助手审核完成

- 用户提供费用CSV并明确授权助手决定次数；临时路径失效且文件搜索无结果，记录来源限制。选择94次累计预算，不再询问预算确认。
- 固定p26-v2同一快照，先train3、Swin dev12、再QASPER validation32，两版各一次。94started／94completed，零服务错误，无重试／辅助模型调用。
- 总输入180661、输出19786tokens。核验官方价格，按高峰且全部输入cache-miss估算0.0779415USD，实付cost保持null；未读取账单，不把估算标成实付。
- QASPER validation官方答案F1领域版16.95%／默认版8.42%，段落证据F1 47.41%／22.25%；词面分数不是语义正确率。
- 根助手审Swin24及train6，独立审查助手审validation64，共94条理由。Swin评分点18/49／16/49，两版完整答句均0；QASPER完整判断21/32／18/32，两版各5题参考歧义。未有人类独立复核。
- 发现9条语义拒答／记录标记不一致，保留原始评分协议，并单列审核；未观察validation后修改生成、gold或封存检索。配置链、目标入口、caption／公式及标注冲突作为后续问题记录。
- 新增离线审核合并脚本及6项完整性回归；审核绑定输入／检索／journal／判定文件SHA，94条无漏题／重复。独立复查补强started／completed唯一性、键集合及每条一次调用检查，CLI共享单写者锁。可读报告、审核理由与汇总入库，原始run继续忽略。
- P2.6交付完成，下一节点P3混合检索／重排；本节点不再追加付费调用。
- 最终完整测试142通过／1Windows符号链接权限跳过，19项评测回归在完整测试内通过，scoped Ruff／format通过；61受保护输入和本轮生成代码／prompt协议未变。最终独立审查无剩余重要发现，本地提交保存，不额外push。
### 2026-09-17：开始P3混合检索与重排序

- 用户明确开始P3，继续当前会话执行。读取规划／现有检索与问答契约、P2.6失败记录，工作区干净。
- 运用brainstorming梳理过滤、混合检索和LLM改写三种路线；基于已有授权选择可审计的模型范围＋BM25／dense融合＋本地重排。用writing-plans形成详细计划后按executing-plans连续实现。
- 联网核验官方BGE-reranker模型与固定revision，准备本地小batch推理，避免重排序API费用。P3评测新建run，不覆盖P2.6结果；validation已观察，继续作为固定回归样本，不称新盲测。

### 2026-09-18：继续P3开发集校准

- 完成 BM25／RRF／范围过滤／本地重排／API 接入；模型7文件2293259337字节核验完成，固定公开revision及SHA账本入库。普通HTTP大权重未写入，206范围探测成功后改32MiB分段续传，最终assembled SHA核对上游。
- 实际GPU同时加载BGE-M3及reranker成功。首轮15题×6组共90记录、生成0；Swin raw重排定位召回69.44%，结构补充版64.58%，发现机械 sibling 扩展挤掉部分证据。
- 保留首轮run；仅依据dev/train新增尺寸与显式YAML/BASE闭包、具名结构及默认值/merge锚点，建立新run重新校准。中文紧接.yaml的边界错误已由回归测试定位并修复；未读取冻结题。
- 独立审查补充端到端过滤覆盖、索引身份绑定、恢复快照单指纹、sealed缺失派生组不可改写检查。首次全目录pytest误收集raw第三方测试；新增pytest.ini仅收集本项目tests，不安装第三方测试依赖。此前完整项目测试167通过／1权限跳过，新范围与账本测试继续追加。

### 2026-09-18：P3评测与交付收尾

- 继续被中断的当前会话；保留校准run、P2.6基线与全部journal，不重试已开始的付费请求。最终六组检索282条，以同一48候选重排派生raw组，生成调用0。
- Swin dev定位召回32.64%→80.56%，必要仓库完整行范围8.33%→31.94%；变体专用路径64/96→0/96，不包含共享文本内的分支描述。最终策略仍不是所有指标最优，hybrid完整行范围34.03%更高。
- 新adapter回答47次全部完成、无错误／重试；新审核47条绑定输入／检索／journal／判定SHA。Swin评分点18/49→40/49、完整0→4题，部分6／错误2；算术错误与第三PatchMerging缺证据明确保留。
- QASPER validation完整段落召回78.49%→75.27%，答案F1 16.95%→11.79%，段落Evidence F1 47.41%→37.23%；助手完整21→19题，5份参考歧义保留。不以语言因素解释全部回退，不观察validation后改gold／prompt／参数，API默认dense继续保留。
- 实际HTTP发现短YAML链遗漏字段，补具名字段锚点；独立复核指出英文后缀可误匹配，补左右ASCII边界与3个回归，中文紧邻正例仍通过。每次源码身份变更另建检索run，最终p3-final-v3；新检索与已生成v1的47题实际准备输入一致，无付费追加。
- 本轮150081输入／7048输出tokens，沿用9月17日cache-miss价格假设估算0.0534819USD；实付null。冻结题仅SHA，61份受保护材料及P2.6原retrieval／journal SHA不变。
- 完整178测试通过／1Windows权限跳过，20份改动范围文件Ruff／format通过；两项真实HTTP验证通过，无生成调用。更新需求／主线／复用／问题日志和可读报告；本地保存到codex/p3-hybrid-retrieval，不自动push或启动P4。Agent规划前提醒用户使用最高阶模型。

### 2026-09-18：开始P4.1–P4.2

- 用户开始P4并授权按需重复调用Flash／Pro；models接口确认两者可用，只使用本机.env既有密钥。核验9月18日官方工具协议及价格，选择Pro规划／Flash回答，累计付费上限40。
- 设计细分P4.1工具、P4.2规划／任务API、P4.3科研业务输出、P4.4扩展验收；当前连续完成前两节点，其他保持后续。新分支codex/p4-agent-tools，设计／计划已提交87bc3a0。
- 静态工具按精确AST字段、BASE闭包和原块定位记录配置链；真实语料查DROP_PATH_RATE得到0.2及5个原始依据，默认BASE_LR得到0.0005。不执行仓库代码。Decimal计算得到0.002，拒绝代码、非有限值、巨大／极小指数等。
- 实际复用PaperQAEnvironment／Aviary step执行和状态历史，原Docs.aquery生成；38项初步关联测试通过。第一条LR真实任务3规划／1回答、18291输入／522输出，算得0.002但默认值引用不完整，保留首轮，未标成完整引用改善。
- 独立审查定位回答超时被上游handle_tool_exc吞成failed、畸形调用KeyError、模型参数冒称user_argument；均修复并补回归。结构化user_overrides强制参数匹配，非核验底层参数标partial；另限制输入长度与CLI标量。36项Agent离线测试通过，独立复核无剩余重要发现。
- 已运行修复后LR一次，保留p4-acceptance-v1；增加输入边界后以p4-acceptance-v2顺序执行最终4开发案例，共用global40 journal不重置、不自动重试。源／模型／token及原始答句继续单独保留，最终语义判定待逐条审核。

### 2026-09-18：P4.1–P4.2交付与未通过项

- 完成9真实任务，累计39/40调用：33Pro规划、6Flash回答，246287输入／6295输出tokens，usage全部返回；无SDK重试或模型请求错误。估算按当日高峰全cache-miss价格0.33249426USD，实付null，剩余1次未使用。
- v2学习率0.002有默认值及公式引用；配置静态0.1→0.2正确，但最终merge实现原文未入选；动机答案明确不足且引用正确SWIN分支，现有状态却漏判。三项不称完整rubric或完整支持率。
- shape v2整除未支持、v3tuple误传、v4继续计算均按5轮预算停止，保留不同源码轨迹。扩展整数整除／取模、单标量文档和预算内收尾；非法额外补查不会触发自动回答。
- shape v5主动第4轮gen_answer，执行completed但语义错误：将第三次PatchMerging前7×7偶数断言故障归因为第四stage窗口。原文ID有效，计算7//2正确，也不能证明代码可执行。明确列为未通过，未花剩余1调用修饰答案。
- 新实际答句／引用逐条助手核查，原文及source身份与固定chunk一致；摘要绑定任务、源码、manifest及journal SHA，保留混合版本标记。未跑全12dev／外部Agent评测，不使用冻结题或旧审核替代。
- 完整227测试通过／1权限跳过、49Agent回归通过，15个改动范围源码文件Ruff／format通过；61受保护材料、P2.6和P3原retrieval／journal及282条sealed检索哈希均不变。
- 核心独立审查重要发现已修复；最终整除／收尾变更自查及回归通过，后续独立审查器触及额度，未取得第三轮结论。文档明确工程基础complete，P4整体in_progress；P4.3先断言／逐claim核查，再科研业务输出，P4.4扩展评测与P5网页pending。

### 2026-09-18：P4.3科研结论核查与审计记录

- 完成四类结构化Claim：精确引文、Decimal算术、静态代码前置条件与推断。只允许`supported`、`blocked_by_precondition`、`insufficient_evidence`、`requires_review`四种状态；不把引用存在当作自由文本语义已证明。
- 原始Swin `PatchMerging.forward`实测H=W=7：第337行L条件未绑定保留不足，第338行`H % 2 == 0 and W % 2 == 0`确定为假，因此“可继续合并”返回`blocked_by_precondition`。不执行仓库代码，未调用付费模型。
- 新增UUID追加式筛选与结构化提取revision、Markdown报告，以及统一ResearchService的四个Agent工具／四个FastAPI入口。Agent仅可使用当前证据池；报告保留阻断和不足项目。
- 完整239项项目测试通过、1项跳过；61项Agent／科研测试通过。Ruff及format检查通过；61项保护账本、冻结Swin测试、P2/P3五项封存产物与journal哈希均未变，暂存文件凭据扫描为零。P4付费journal仍为39/40。

### 2026-09-18：P4.4独立Agent回归

- 新建p4-v2独立journal，硬上限32次；固定4个Swin开发案例和4个按QASPER validation问题ID SHA排序的外部回归案例。冻结Swin test只核验SHA，未解析或评分；任何开始的案例不重试。
- 实际25次调用全部有terminal usage：19 Pro、6 Flash、107250输入／3277输出token，实际费用null。5题completed、1题insufficient_evidence、1题no_progress、1题budget_exhausted；6条生成答案的引用范围均符合原请求。
- 审计failed：shape最后轮仅开放gen_answer但模型仍请求calculate／read，安全拒绝并停止，未出现blocked_by_precondition；动机最后轮继续search，未出现requires_review。保留全部轨迹和剩余7次预算，不为通过验收而重试或替换案例。
- 完整244项目测试通过／1跳过；P4.4 runner、manifest、journal配对、范围和Claim缺失均有本地测试。下一步需单独设计强制Claim阶段的Agent调度修复，不能将本次失败称为P4.3真实Agent合规。

### 2026-09-18：P4.5必经核查控制与两项失败验收

- 新verified配置继续复用PaperQAEnvironment，严格submit_claims经ResearchService核查后才允许一次Docs.aquery；显式必需Claim类型、最终上下文引用守恒、review／不足状态传播与workflow_stages已实现。
- 独立复核发现无证据收尾仍能调查，已修复并回归；最终轮只开放提交，单工具API明确指定名称。非法工具或非法草稿不会自动回答。
- 两个既有开发案例各一次，新p4-v3独立8次预算实际6次Pro、0次Flash，68116输入／2175输出token，usage齐全、费用null，无重试。shape仍忽略命名提交工具，motivation提交inference带quote；均无核查产物／答案，真实验收failed。
- 真实运行后以oneOf补齐类型分支schema，新增离线回归；补丁未实测，不改manifest／journal。末轮独立复核无重要或严重问题，29项Agent测试通过。
- 最终草稿已与调查历史隔离，保留完整请求／原文／产物，不追加规划调用；原生回归与独立复核30项Agent测试通过，无重要发现。此补丁仍仅离线验证。
- 全量255测试通过／1权限跳过，13文件Ruff与格式通过；61保护材料、冻结test SHA、5项P2/P3封存文件均不变，旧P4 journal仍39／25次。
- 修正README、需求和主线的完成口径：自动筛选／字段提取／综合报告与网页仍待交付。P4.5整体in_progress，新补丁真实验证后接P4.6产品链路。详见docs/p4-verified-workflow-report.md。

### 2026-09-19：P4.5新协议验收、P4.6自动科研与P5网页首版

- 按既定顺序完成真实SDK请求 mock、一次中性 DeepSeek Pro 工具选择、新目录／源码身份／独立预算的 Swin 新题。中性工具提交成功；新科研题完成提交、核查和回答，但遗漏 `L` 绑定的代码结论为 `insufficient_evidence`，整体不计正确，不重跑同题。
- P4.6 接入限定语料论文发现、每篇一次模型筛选／实验字段提取、追加式记录和多论文可比性报告。首轮独立 smoke 3/3 `ToolInputError` 原样封存；单独诊断样本与网页两篇新 train 论文均成功。模型稳定性与字段语义分类仍未验收。
- P5 Vue 网页已能检索 Swin／QASPER train、查看证据、生成自动卡、人工追加修订、恢复已存卡、比较并下载 Markdown、触发 Swin Agent。浏览器实际验证两篇新论文卡、修订版本和不可比报告；报告不自动排名。第二个视觉案例和在线部署仍待后续。
- 当前全量 Python 回归 269 通过／1 跳过；本轮 15 个 Python 变更文件的 Ruff 格式与静态检查、Vue/TypeScript 生产构建均通过。原冻结测试、P2/P3 和旧 P4 运行继续保持封存；新数据均进版本化独立目录或忽略的运行目录。
