# P2.1：解析层使用说明

## 目标与复用边界

本节点产物供 P2.2 分块消费，尚未生成向量索引或问答服务。

- PDF 主后端复用 **Docling**：布局、阅读顺序、章节、表格候选及结构化 JSON。安装使用 `docling-slim` 的 PDF 与本地模型 extras，无需 OCR／办公文档 extras。
- **PyMuPDF** 保留轻量备选；Docling 跨页字符范围失效时，仅从原 PDF 对应页与坐标区域恢复文本，并记录警告。
- 本项目实现 adapter、来源哈希／commit 校验、Python AST 符号范围、YAML 字段行号、文件枚举、失败隔离和可重建管线。
- 根据后续用户选择，PaperQA2在P2.5/P4作为主要问答／Agent框架复用目标，通过领域adapter针对论文—代码—配置核查改造；原版保留对照参考。Kotaemon在P3/P5参考检索与引用体验，ASReview参考筛选记录，OpenScholar/STORM补充报告流程。P2.1没有安装这些完整应用，下一步仍是P2.2分块。

## 环境与版本

使用 `ican` 环境。新增入口依赖已写入 `requirements/ican.txt`，完整已安装版本写入 `requirements/ican-lock.txt`。

- docling-slim 2.127.0
- docling-core 2.96.1
- docling-parse 7.20.0
- docling-ibm-models 4.0.2

实际模型版本固定在 `ican/ingestion/docling_models.py`，不依赖可变的 main/tag：Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；TableFormer 来源 `fc0f2d45e2218ea24bce5045f58a389aed16dc23`。文件位于 `data/cache/docling/`，目录与文件哈希记录在 `data/catalog/docling-models.json`。

开源组件依据其原许可复用：[Docling 代码 MIT](https://github.com/docling-project/docling)、[Heron 模型 Apache-2.0](https://huggingface.co/docling-project/docling-layout-heron)、[Docling 模型卡](https://huggingface.co/docling-project/docling-models)按具体模型列出 CDLA-Permissive-2.0／Apache-2.0。PyMuPDF 的安装元信息为 AGPL／商业双许可；对外分发时按最终应用的许可安排核验。来源和说明不改变团队自建模块的贡献边界。

## 执行命令

PowerShell：

```powershell
conda activate ican
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest tests -q
python scripts/parse_swin.py
python scripts/prepare_qasper.py --train-count 20 --validation-count 10
python scripts/verify_ingestion.py
```

也可将 `python` 替换成 `D:/CondaEnv/ican/python.exe`。首次执行模型准备和 QASPER 准备需要网络；后续使用固定 revision 的本地缓存。

比较脚本：

```powershell
python scripts/compare_parsers.py --backend pymupdf --output data/processed/parser-comparison/pymupdf-final
python scripts/compare_parsers.py --backend docling --output data/processed/parser-comparison/docling-final --condition 'model cache warm; includes imports and initialization'
```

两个后端应串行执行，测量时避免其他 GPU 任务；具体结果见 `docs/parser-comparison.md`。

`parse_swin.py --backend pymupdf` 会按同一配置重建输出；保留两套结果时应使用另一份配置并指定不同的 `output_dir`，不要让比较产物覆盖生产解析产物。

## 输入与输出

明确来源列表：`configs/ingestion/swin-v1.json`，只允许 `data/raw/` 内的固定 Swin PDF 与仓库。PDF 哈希不匹配或 commit 不一致时拒绝来源。仓库对允许文件逐一比较固定提交 blob，仅容许 CRLF/LF 检出转换；未跟踪文件不纳入。读取失败隔离，超过 2MiB 或扩展名不允许的文件跳过并记录。

输出目录：`data/processed/swin/v1/`。

| 文件 | 用途 |
|---|---|
| `sources.jsonl` | 论文、仓库及文件来源；版本、原始哈希、来源 URL、解析状态 |
| `parsed_units.jsonl` | PDF 物理页或完整文件文本；文本哈希、结构字符范围、页码／行号／坐标 |
| `*.docling.json` | 保留 Docling 原始文档结构、引用指针、表格单元格和 provenance |
| `parse_failures.jsonl` | 失败及警告，包括待核验表格与跨页定位恢复 |
| `parse_report.json` | 数量、后端版本、跳过原因与核心产物哈希 |
| `review_samples.md` | 论文页、模型函数、配置字段和配置加载函数的定位抽查样本 |
| `verification_report.json` | 原始文件／文本哈希、页码、行号、坐标、冻结集与外部集隔离验收 |

仓库顶层 `raw_sha256` 是纳入文件路径／哈希清单的哈希，`metadata.hash_kind` 明确标记；文件记录的 `raw_sha256` 才是原始文件字节哈希。读取失败的文件哈希为空并标记 unavailable。退出码 0 表示无错误，警告仍须处理；有错误时退出非零，成功单元仍保留供排查，不应把失败报告对应的产物直接索引。

## 位置语义与局限

- `page` 是物理 PDF 页码，从 1 开始；bbox 统一为左上原点。
- 代码行号从 1 开始；`char_start/char_end` 是解析文本中的 Python 字符偏移，end 不包含末端字符。保留仓库文本的原始换行。
- 跨页段落按 provenance 的字符范围分到对应页；同页多个 bbox 保留在结构 metadata，外层 bbox 是联合区域。
- Docling 的表格与表头关系均是候选，`review_required` 为 true；不能把“提取到表格”当成“数值关系已正确”。本轮已观察到表头错误，后续引用关键数值仍需对照原 PDF。
- 此语料扩展名只覆盖 Python、YAML/JSON、Markdown、Shell、TXT 与 LICENSE。C++/CUDA 内核文件当前跳过；需要内核实现问答时须显式扩展来源与验收。
- 整体 Docling 转换失败仍会拒绝论文来源；adapter 的单页失败会保留其他成功页并记录错误。

## QASPER 外部样本

复用官方转换后的 Parquet，固定 dataset revision `06806e4608976fc2fac0a090ac425d5b2b29caf4` 与 card revision。无需执行旧数据集脚本，兼容本环境 datasets 5。两份传输 shard 合计约 19MB，输出仅选择 20 篇原 train 和 10 篇原 validation 论文；没有下载原 test。

- 可索引正文：`data/processed/qasper_external/v1/{train,validation}_corpus.jsonl`。
- 问题／答案／gold evidence：`data/eval/qasper_external/v1/{train,validation}_questions.jsonl`。
- 来源、选择规则、论文 ID、数量、哈希：`data/catalog/qasper-external.json`。
- 位置使用原章节／段落索引或 caption 索引，无 PDF 页码。保留原文与占位符；空段不输出，但不重排原段落 ID。
- 训练样本 51 问题／51 个答案标注，验证样本 32 问题／57 个答案标注；正文与 caption 共 2,354 单元。训练有 1 条未匹配证据，不补造原文；验证证据均匹配。未匹配和歧义在答案记录中显式保留。
- QASPER 与 Swin 各自建库、各自评测，不合并总分；正文进入索引，答案与标签只供 evaluator 使用。该节点只准备格式，尚未运行外部问答评测。
