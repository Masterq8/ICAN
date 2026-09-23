# 复现有据 · ICAN

面向计算机视觉论文调研与复现准备的 RAG／Agent 项目，用于 ICAN 比赛与大模型应用开发实践。

## 当前进度

**P2 基础 RAG、P3 混合检索与重排序已完成；P4/P5 已有可操作的本地首版。** 网页支持限定语料检索、自动实验信息卡、人工追加修订、已存卡恢复、来源证据查看、多论文可比性报告与 Swin Agent 核查。P4.5 真实流程完成结构化提交和逐条核查，但独立新题仍因证据不足未通过答案质量验收；P4.6 首轮 3 例自动卡失败，后续 3 个独立样本成功。原文匹配不等于字段归类正确，模型稳定性与准确性仍在验证。

2026-09-23 定向验收：8 篇新 QASPER train 各调用一次，2/8 工具提交成功，6 篇因重复字段名被拒绝，P4.6 质量未通过。已补充具体错误诊断和字段规则；随后完成16次Pro辅助逐条AI复核，支持55/59、归类52/59、缺失14/16，人类确认仍待完成。详见[复核裁定](docs/evaluation/p46-quality-v1/review-adjudication.md)。见[质量报告](docs/evaluation/p46-quality-v1/report.md)与[人工复核工作表](docs/evaluation/p46-quality-v1/human-review.md)。

以下保留P2节点的交付与验证记录：

- Swin 固定版本论文与官方仓库解析：97 个单元。
- Swin 结构分块：1,602 块，保留物理页、代码行、来源版本与原文范围。
- QASPER 独立外部样本分块：2,357 块，正文与答案隔离。
- 固定本地BGE-M3，3,959个1024维向量分别进入Swin／QASPER train／validation的3个Qdrant collection。
- 实际tokenizer最长输入1,127 tokens，无截断；独立进程逐点核对与重复运行复用通过。
- 79 项测试通过；1 项真实符号链接测试因 Windows 权限跳过。
- 定位、原文覆盖、token 预算与重复重建哈希验收通过。
- FastAPI `POST /v1/evidence/search` 支持collection、来源类型和安全路径前缀过滤，只返回可定位证据；真实Swin配置路径约束验证通过。
- P2.4完成后完整测试：101项通过，1项真实符号链接测试因Windows权限跳过。

- 固定PaperQA2 2026.8.12，实际复用公开对象及 `Docs.aquery`；新增 `POST /v1/qa/answer`，返回答案、原文引用、页／行、版本和用量。
- DeepSeek真实功能样例已运行：配置题定位到YAML第6–9行，论文题定位到PDF第2、4页；保留首轮论文失败及prompt调整记录。
- P2.5完整测试：123项通过，1项Windows符号链接权限跳过；独立审查确认引用清理漏洞修复。

当前开发与真实验收结果见[任务计划](task_plan.md)、[Agent科研使用说明](docs/p4-research-guide.md)及[P4.5交付报告](docs/p4-verified-workflow-report.md)。P4.4原失败记录保留，不以新结果覆盖。

## 本地网页演示

先按[环境说明](docs/environment-setup.md)恢复原始语料和索引，并在本机 `.env` 配置 DeepSeek 凭据。查询论文与查看证据不消耗付费模型；生成实验卡或运行 Agent 会消耗模型调用。网页只开放 Swin 固定论文与 QASPER train 方法示例，不读取冻结测试答案或 QASPER validation 标注。

```powershell
cd frontend
npm install
npm run build
cd ..
python scripts/serve_api.py --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000`。输入问题并选择语料，勾选候选论文后点击“从原文生成”；已有记录可用“读取已存卡”恢复，不消耗模型调用。筛选决定和字段可人工修订，新版本保留旧记录。至少两篇已有信息卡时可生成对照报告并下载 Markdown。右侧证据面板显示原文、路径、版本与位置。报告遇到任务、数据集、指标或输入条件不同或缺失时不自动排名。

**P2.6完成：** 47题检索、94次双版真实生成与94份助手语义审核。QASPER validation答案F1领域版16.95%／默认版8.42%；Swin评分点覆盖18/49／16/49，存在变体混入和配置链缺证据。语义审核未有人类独立复核；实际费用未知，按指定官方价格假设估算0.0779415美元。指标口径与逐题理由见[基线报告](docs/p2-baseline-report.md)及[审核记录](docs/evaluation/README.md)。

## 文档入口

- [任务计划](task_plan.md)
- [需求与技术方案](docs/requirements-spec.md)
- [开发主线](docs/development-roadmap.md)
- [问题与解决方案](docs/problem-solution-log.md)
- [开源项目与数据集复用](docs/reference-projects-and-datasets.md)
- [解析说明](docs/p2-parsing-guide.md)
- [分块说明与验收](docs/p2-chunking-guide.md)
- [Embedding与索引说明](docs/p2-indexing-guide.md)
- [检索接口说明](docs/p2-retrieval-guide.md)
- [PaperQA2问答配置、接口与验收](docs/p2-qa-guide.md)
- [开发集与外部基线报告](docs/p2-baseline-report.md)
- [混合检索与重排序使用说明](docs/p3-retrieval-guide.md)
- [P3检索消融与回答对照](docs/p3-retrieval-report.md)
- [Agent科研使用说明](docs/p4-research-guide.md)
- [P4.5必经核查工作流报告](docs/p4-verified-workflow-report.md)
- [P4.6/P5 科研工作台使用说明](docs/p46-web-guide.md)
- [P4.6 与 P5 设计及验收顺序](docs/superpowers/plans/2026-09-19-research-product-sequence.md)
- [环境说明](docs/environment-setup.md)

## 环境与测试

```powershell
conda env create -f environment.yml
conda activate ican
python -m pip install -r requirements/torch-cu128.txt
python -m pip install -r requirements/ican-lock.txt
python -m pytest tests -q
```

CUDA 依赖基于当前 Windows／NVIDIA 开发机，其他平台需调整 PyTorch 安装方式。源码可直接从项目根目录运行。

## 数据恢复与运行

仓库保存源码、配置、文档、来源清单和评测定义。原始 PDF、第三方代码仓库、权重、模型缓存、处理产物和向量索引由 `.gitignore` 排除。

恢复 Swin 原始材料时，按 `configs/ingestion/swin-v1.json` 的路径、论文版本、SHA-256 与仓库 commit 下载；Docling 模型准备方法见解析说明。QASPER 样本由以下脚本恢复：

```powershell
python scripts/prepare_qasper.py
python scripts/parse_swin.py
python scripts/verify_ingestion.py
python scripts/chunk_corpus.py
python scripts/verify_chunks.py
python scripts/check_chunk_rebuild.py
python scripts/prepare_embedding_model.py
python scripts/build_index.py
python scripts/verify_index.py --smoke
python scripts/verify_retrieval_api.py
python scripts/verify_paperqa2.py
```

分块配置固定输入 manifest 哈希。若重新生成的解析输入与当前快照不一致，先核验差异，再建立新的配置／输出版本，不跳过校验。冻结测试文件不得用于调参；QASPER 原始 test 未下载。

Swin 的 10 个表格仍为待核验解析候选，相关 15 个分块保留核验标记。分块验证不替代表格与 PDF 的语义核对。

## 第三方资源

各代码、论文、权重和数据使用各自许可证；来源、版本与访问条件见 [语料清单](docs/corpus-manifest.md) 和 `data/catalog/`。本项目尚未指定公开开源许可证。

## P4 Agent

P4.1／P4.2的工具、任务API与预算操作见[Agent使用说明](docs/p4-agent-guide.md)，真实结果见[验收报告](docs/p4-agent-report.md)。P4.3已补上结论条件核查、可追加的筛选／结构化提取记录和报告，使用方式见[科研核查说明](docs/p4-research-guide.md)。112输入尺寸的历史自由文本回答仍保留为失败轨迹；P4.4再做新的模型预算与外部回归。
