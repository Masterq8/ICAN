# P2.3：Embedding 与持久化索引

## 1. 模型与复用边界

采用[BAAI/bge-m3官方模型](https://huggingface.co/BAAI/bge-m3)，固定revision `5617a9f61b028005a4858fdac845db406aefb181`，MIT许可。复用现有Sentence Transformers接口，生成dense向量；官方支持的sparse和ColBERT能力没有在本节点启用，不安装完整FlagEmbedding应用。

选择理由：项目包含中文问题与英文论文，需要跨语言检索；8192输入容量能容纳本次现有分块。multilingual-E5-base更小，但512限制可能要求重分块；远程服务需要另行配置密钥和预算。没有依据本项目正式得分宣称BGE-M3优于其他模型。

| 设置 | 固定值 |
|---|---|
| 编码 | Sentence Transformers；官方CLS pooling；dense-only |
| 维度／距离 | 1024／Cosine |
| 推理／落盘 | CUDA float16／归一化float32向量 |
| batch size | 8 |
| 输入上限 | 8192，包含特殊token |
| 文档模板 | `chunk.embedding_text`，直接使用既有上下文＋连续原文 |
| 查询模板 | 原始字符串；BGE-M3无需额外查询指令 |

这些字段固定在`configs/indexing/v1.json`，不把PaperQA2当作Embedding模型。PaperQA2接入仍在P2.5，Kotaemon混合检索参考仍在P3。

## 2. 模型文件与校验

`scripts/prepare_embedding_model.py`只从固定revision下载11个dense所需文件。当前官方checkpoint为`pytorch_model.bin`，未重复下载ONNX、sparse和ColBERT附加权重。

- 路径：`data/cache/embedding/bge-m3/<revision>/`。
- 账本：`data/catalog/embedding-model-bge-m3.json`。
- 大文件检查上游LFS SHA-256，小文件检查上游git blob身份；账本保存每个文件的实际SHA-256与体积。
- 运行前重新检查大小与哈希；拒绝目录中未列入配置的模型／配置文件，HF自身`.cache`元数据除外。显式选择已核验的PyTorch checkpoint，禁用远程自定义模型代码。
- 不通过删改数据或跳过验证修复哈希不匹配；恢复固定文件或建立经过核验的新版本。

## 3. 输入与tokenizer

索引入口`ican/indexing/inputs.py`只加载指定chunk manifest的allowlist，核对分块文件、配置、验收报告、parent文本与定位契约。7个评测文件只检查固定SHA-256，其问题、答案和gold evidence不进入编码输入。

首轮真实tokenizer检查：3959个分块，使用固定模型的`XLMRobertaTokenizer`，包含特殊token的长度范围55–1127，全部低于8192。该结果与P2.2的cl100k计数不同；P2.2最大768只是该节点预算，不能当作Embedding tokenizer长度。

编码前以`truncation=False`逐条计数，超出上限直接失败，要求显式重分块；编码输出逐批检查形状、有限值和非零范数，再转为float32归一化。不静默换模型、精度、批量或截断正文。

## 4. 三个collection与版本目录

| Collection | 来源 | 输入数量 |
|---|---|---:|
| `swin_v1` | Swin论文／代码／配置／文档 | 1602 |
| `qasper_train_v1` | QASPER train正文／caption | 1659 |
| `qasper_validation_v1` | QASPER validation正文／caption | 698 |

一个本地Qdrant数据库内保存三个独立collection。QASPER split没有混入Swin，也不交叉到另一个split。

版本路径：`data/indexes/bge-m3/v1/<fingerprint>/`。完整SHA-256指纹来自配置、模型账本、分块及parent快照和运行库版本。改变模型、精度、模板、语料或库版本会得到不同目录，而不是复用旧collection。

构建先写短名称的独立staging目录，所有写入／关闭／重新打开检查通过后才原子发布。失败保留staging内的`build_report.json`，不发布成功manifest。相同指纹已有索引时，检查存储、映射、payload、向量和输入身份后复用，不覆盖旧版。

## 5. 产物与数据契约

| 文件／目录 | 用途 |
|---|---|
| `qdrant/` | 本地持久化数据库 |
| `points.jsonl` | 稳定UUID5 point ID、collection、完整chunk、embedding输入哈希及实际token数 |
| `vectors.npy` | 对应points顺序的1024维归一化float32向量 |
| `token_report.json` | 实际token长度、collection分布、tokenizer／pooling信息和0截断记录 |
| `index_manifest.json` | 输入／模型／运行库身份、配置、编码设置、向量与映射文件哈希 |
| `build_report.json` | 构建状态、耗时、数量与本机资源观察 |
| `verification_report.json` | 重新打开数据库逐点验收结果 |
| `smoke_queries.json` | `--smoke`生成的人工中英文功能查询与引用位置 |

UUID5由collection和chunk ID确定。payload保存完整chunk，包括原文范围、论文物理页、文件行、来源版本／哈希、QASPER段落／caption位置、bbox来源与待核验标记。

引用应显示`payload.chunk.text`；`embedding_text`包含补充上下文，不能当作原文。Swin10个表格对应15个待核验分块，这些标记在索引中保留。向量化成功不等于完成表格与PDF的语义核对。

## 6. 运行与独立验收

在项目根目录执行：

```powershell
conda activate ican
python scripts/prepare_embedding_model.py
python scripts/build_index.py
python scripts/verify_index.py --smoke
```

本机也可直接调用`D:\CondaEnv\ican\python.exe`。模型已下载后，构建和验收都从固定本地目录加载，`local_files_only=True`。通过`--config`使用其他已核验配置。

`verify_index.py`运行于新的进程，重查原输入与模型、打开关闭后的Qdrant、逐点比对全部payload及向量、检查集合维度／距离／数量／split，再以真实tokenizer复核每条token数。过滤到指定ID的self-vector查询验证数据库评分与定位，避免重复原文产生同分排名的误判。

`--smoke`附加两条人工功能查询：英文shifted window及中文窗口大小，分别限制论文／配置来源。查询不是冻结题或QASPER标准问题，不计入正确率、Recall@K等正式得分。

```powershell
python -m pytest tests -q
python -m ruff check ican/indexing scripts/prepare_embedding_model.py scripts/build_index.py scripts/verify_index.py tests/test_indexing.py
```

单元测试使用fake encoder验证输入拒绝、存储、隔离和失败状态；真实模型与GPU的集成验收另以构建／验收报告作为证据，不能用fake通过代替真实向量化。

## 7. 使用限制与下一节点

Qdrant local适合当前约4000点的开发集，单一数据库目录只能由一个进程持有锁。构建、验收和后续服务必须顺序访问并关闭客户端，不能让多个FastAPI worker同时打开同一local目录；需要多人并发时再切换Qdrant server，通过相同collection／payload契约迁移。

本节点没有FastAPI检索端点、回答生成、重排或正式基准分数。下一节点**P2.4：只返回证据的检索接口**，固定查询编码契约、读取对应版本、提供来源／位置／分数，并为P2.5 PaperQA2 adapter准备输入。

## 8. 本机真实构建记录（2026-09-17）

- 版本目录：`data/indexes/bge-m3/v1/3fcc38131d303a03b83cbe0dea77dc74b83398f597aee10e6a4fb1fbae9eaa87/`。
- 模型11文件合计2,293,331,623字节，官方身份校验通过；模型权重和索引继续由git忽略。
- 三个collection共3959点，数量与上述输入表相同；每点保存完整chunk。
- 真实GPU为RTX 5060 Laptop 8 GB，float16编码＋float32落盘。构建／重新打开验证耗时93.382秒（计时从模型加载前开始，不含下载和前置输入校验）。
- PyTorch统计峰值：allocated 1296.39 MiB、reserved 2152 MiB；这两项是张量／缓存分配统计，不是整机或进程总显存。
- 最长实际输入1127 tokens，0截断。所有数据库payload、向量和集合数量／配置与编码输入对照通过；独立CLI验收与功能query结果见该版本的verification_report.json／smoke_queries.json。
- 软件版本：torch2.11.0+cu128、Transformers5.17.0、Sentence Transformers6.0.1、Qdrant Client1.19.0；详细身份保存在index manifest。
- 独立进程重新打开／实际tokenizer／2条功能查询验收通过；再次运行构建验证并复用同一版本，未重新编码。61个原输入及eval文件的SHA-256与阶段前快照相同。
- 79项pytest通过，1项真实符号链接因Windows权限跳过；改动范围Ruff与格式检查通过。独立只读审查修正替代权重与eval完整性校验，最终无剩余重要发现。

### 功能查询暴露的已知检索问题

“Swin-T的窗口大小配置是多少？”在仅限制source_type=config时，前三条包含SwinV2、SwinMoE和其他输入分辨率变体。它们来自真实官方仓库，但不能直接当作标准Swin-T／224配置的答案。dense相似度和来源类型约束不足以确定模型变体，需在P2.4暴露collection／类型／路径限制，并在P3评估BM25／混合检索。此处保留原始结果，不换样例掩盖问题，也不报告gold准确率。
