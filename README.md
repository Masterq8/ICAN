# 复现有据 · ICAN

面向计算机视觉论文调研与复现准备的 RAG／Agent 项目，用于 ICAN 比赛与大模型应用开发实践。

## 当前进度

已完成 **P2.3：Embedding 与持久化索引**：

- Swin 固定版本论文与官方仓库解析：97 个单元。
- Swin 结构分块：1,602 块，保留物理页、代码行、来源版本与原文范围。
- QASPER 独立外部样本分块：2,357 块，正文与答案隔离。
- 固定本地BGE-M3，3,959个1024维向量分别进入Swin／QASPER train／validation的3个Qdrant collection。
- 实际tokenizer最长输入1,127 tokens，无截断；独立进程逐点核对与重复运行复用通过。
- 79 项测试通过；1 项真实符号链接测试因 Windows 权限跳过。
- 定位、原文覆盖、token 预算与重复重建哈希验收通过。

下一节点为 **P2.4：只返回证据的检索接口**。PaperQA2在P2.5／P4接入并做论文、代码、配置证据适配。FastAPI检索、问答、Agent和网页尚未完成；现有功能查询不代表正式基准得分。

## 文档入口

- [任务计划](task_plan.md)
- [需求与技术方案](docs/requirements-spec.md)
- [开发主线](docs/development-roadmap.md)
- [问题与解决方案](docs/problem-solution-log.md)
- [开源项目与数据集复用](docs/reference-projects-and-datasets.md)
- [解析说明](docs/p2-parsing-guide.md)
- [分块说明与验收](docs/p2-chunking-guide.md)
- [Embedding与索引说明](docs/p2-indexing-guide.md)
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
```

分块配置固定输入 manifest 哈希。若重新生成的解析输入与当前快照不一致，先核验差异，再建立新的配置／输出版本，不跳过校验。冻结测试文件不得用于调参；QASPER 原始 test 未下载。

Swin 的 10 个表格仍为待核验解析候选，相关 15 个分块保留核验标记。分块验证不替代表格与 PDF 的语义核对。

## 第三方资源

各代码、论文、权重和数据使用各自许可证；来源、版本与访问条件见 [语料清单](docs/corpus-manifest.md) 和 `data/catalog/`。本项目尚未指定公开开源许可证。
