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
| 我在哪里？ | P2：基础 RAG，P2.2结构化分块已完成，下一节点P2.3索引 |
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
