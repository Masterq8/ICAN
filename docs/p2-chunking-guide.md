# P2.2：结构化分块交付与使用说明

## 1. 本节点完成了什么

已将验收后的 Swin 论文、官方代码、配置、Markdown，以及隔离的 QASPER 正文转换为可定位分块。本节点消费 Docling 的结构与位置，不再次解析 PDF。没有调用生成模型，也尚未接入 PaperQA2 或建立向量索引。

输入契约为 `ParsedUnit`／QASPER corpus record，输出契约为 `ican/chunking/schema.py` 中的 `Chunk`。可运行入口为 `scripts/chunk_corpus.py`；参数和输入快照固定在 `configs/chunking/v1.json`。

## 2. 实际产物

| 数据集 | 输入单元 | 输出块 | 分布 | 最大 embedding tokens |
|---|---:|---:|---|---:|
| Swin | 97：14 个论文页、83 个文件 | 1,602 | 论文 243、代码 375、配置 894、文档 90 | 764 |
| QASPER external | 2,354：20 train／10 validation 论文 | 2,357 | train 1,659、validation 698；paragraph 2,162、caption 195 | 765 |

目录分别为：

- `data/processed/swin/chunks/v1/`
- `data/processed/qasper_external/chunks/v1/`

两个目录均交付以下文件：

| 文件 | 用途 |
|---|---|
| `chunks.jsonl` | 正文片段、上下文、来源和定位；唯一可索引数据文件 |
| `chunk_manifest.json` | 配置、输入 manifest 和文件哈希、tokenizer 版本、产物哈希、index allowlist |
| `chunk_report.json` | 实际数量、类型、预算和覆盖验收结果 |
| `chunk_failures.jsonl` | 本次构建失败记录；成功时为空 |
| `review_samples.md` | 按来源／结构类型选择的原文定位抽查样本 |
| `verification_report.json` | 从落盘产物核验正文、位置、上下文和冻结集哈希 |
| `rebuild_verification.json` | 重建前后产物、输入和 eval 文件的哈希对比 |

生成失败时不发布成功 manifest；重建开始时清除旧的验证／重建标记。输出文件预先检查符号链接和硬链接，拒绝覆盖链接到其他文件的目标。

## 3. 分块方法与参数

1. **固定输入。** 只读配置指定的已通过解析验收文件；校验输入 manifest、文件和每个 parent 文本的 SHA-256。不扫描 raw，不将社区回复、项目文档或标准答案加入证据库。
2. **保留结构。** 论文按已有章节、文本、公式、caption、表格等结构处理；章节上下文按物理页顺序继承。未编号小标题保留所属编号章节，新的同级编号标题替换旧分支。该规则是首版启发式，其他论文编号方式需要补充样例后扩展。
3. **嵌套结构只保留一次正文。** Python 选择最内层函数／类剩余区域，装饰器和模块级内容保留；YAML 选择最内层字段并附祖先路径；Markdown 保留标题层级，忽略代码围栏里的伪标题。结构间的非空白内容也必须覆盖。
4. **连续原文拆分。** 短结构直接保留；长结构优先沿换行／词边界拆分，必要时沿 Unicode 字符边界拆分。仅同一长结构允许重叠，逐块保存实际重叠范围和 token 数，不截掉剩余正文。
5. **上下文另存。** 来源、版本、标题、章节／函数／字段路径进入 `embedding_context`；`text` 始终是 parent 的连续切片。表头补充进入 `metadata.table_header_context`，没有重复插入正文，也没有在本版自动拼入 embedding 输入。
6. **落盘后验收。** 原文切片、ID 和哈希、位置、坐标来源、核验标记、token 预算、重叠和所有非空白字符覆盖都必须通过。结构上下文和表头也与 parent 对照。

| 参数 | v1 值 | 含义 |
|---|---|---|
| tokenizer | `tiktoken / cl100k_base` | 本节点的预算计数器，literal special-token 字符串按普通文本处理 |
| max_tokens | 768 | 完整 `embedding_text` 的最大 token 数 |
| max_context_tokens | 128 | 上下文前缀上限；超出时保留完整字段元数据并标明 prefix 被缩短 |
| overlap_tokens | 64 | 同一超长结构内的实际原文重叠上限 |

正文预算从总预算扣除上下文与拼接余量，拼接后再次检查实际 token 数。本次两个数据集的上下文缩短数均为 0。

**cl100k_base 不是选定的 Embedding 模型 tokenizer。** P2.3 必须用实际模型 tokenizer 检查输入上限，明确输入模板并生成索引 manifest；不能让模型静默截断这些分块。修改配置或输入时使用新版本输出目录，并重新验收。

配置采用细粒度字段块，因此产生 894 块；首版没有把短字段重新合并。这是保留精确字段证据的基线策略，其检索效果尚未评测。若后续需要补齐相邻字段／父级配置，应在检索层依据 parent 和范围扩展，并记录实际取用内容。

## 4. Chunk 字段及引用方式

| 字段 | 语义 |
|---|---|
| `chunk_id` | 由 dataset、split、parent ID、范围和正文哈希生成的稳定 ID；不是上游 PaperQA2 citation ID |
| `parent_unit_id`、`parent_input_path` | 回到明确解析／正文单元 |
| `source_type`、`source_path`、`source_url`、`source_version` | 论文版本或仓库 commit 等来源身份 |
| `source_sha256`、`parent_text_sha256`、`text_sha256` | 原始来源、parent 提取文本、chunk 文本哈希；QASPER 无原 PDF hash 时 `source_sha256=null` |
| `char_start`、`char_end`、`text` | parent 文本的 Python Unicode 字符范围 `[start,end)`；不是字节或 PDF 整文偏移 |
| `location` | PDF 物理页；文件原始行号；或 QASPER paper／section／paragraph／caption 索引 |
| `structure_kind`、`structure_name`、`context_path` | 片段所属结构和层级 |
| `provenance` | 与片段相交的 parent 结构、范围、bbox 和后端原始元数据 |
| `review_required` | 当前表格结构候选是否需要核验 |
| `embedding_context`、`embedding_text` | 检索输入前缀及前缀＋原文；引用展示应使用 `text` |
| `metadata` | region 范围、实际重叠、prefix 缩短标记、表头上下文和 parent 元数据等 |

基本定位操作：加载 `parent_input_path` 对应 parent ID，检查 `parent.text[char_start:char_end] == chunk.text`。文件行号按 CR／LF／CRLF 物理换行计算，保留原 CRLF；字符串内 U+2028 等 Unicode 分隔符不增加文件行号。非整文件 parent 也保留其原始起始行偏移。

论文 bbox 继承自相交结构，是可回查的区域级定位；不能把它称为每个被引用字符的精确坐标。跨页结构已在 P2.1 分配到物理页，不在这里合成只有一个页码的跨页 chunk。

## 5. 表格和 QASPER 的边界

Swin 的 10 个待核验表格产生 15 个 table chunk，全部 `review_required=true`。分块验收证明其内容与**已保存的解析候选**一致，不证明表格表头和值已与 PDF 完成语义核对。后续答案依赖这些表格时必须显式核验或报告待确认状态。

QASPER 与 Swin 分开保存，train／validation 论文 ID 不交叉，split 保留。QASPER 使用原段落或 caption 位置，没有 PDF 页码和 PDF 原文件哈希；以数据 revision、正文文件哈希和 parent 文本哈希追踪。正文与人工答案仍处于 processed／eval 两侧，转换和分块都不读取答案。冻结 Swin 答案只做文件哈希检查，不用于分块参数选型。

## 6. 使用与重建

在 `G:\ICAN` 中运行：

```powershell
conda activate ican
python scripts/chunk_corpus.py
python scripts/verify_chunks.py
python scripts/check_chunk_rebuild.py
```

也可用本机环境的完整解释器路径 `D:\CondaEnv\ican\python.exe`。通过 `--config` 指定另一份版本配置；相对路径从项目根目录使用。

第一条生成并在写出前检查数据不变量；第二条从落盘产物与 manifest 验收；第三条要求已有完整已验证产物，重新生成／验证并比较哈希。失败会返回非零，按失败清单或异常修正后重新生成。

验证命令：

```powershell
python -m pytest tests -q
python -m ruff check ican/chunking ican/ingestion/parsers.py scripts/chunk_corpus.py scripts/verify_chunks.py scripts/check_chunk_rebuild.py tests/test_chunking.py tests/test_chunk_pipeline.py
```

本节点验收：60 项测试通过，1 项真实符号链接测试因 Windows 权限跳过；模拟符号链接检查和实际 NTFS 硬链接回归通过。落盘验证覆盖 364,966 个 Swin 和 849,488 个 QASPER 非空白字符。重建 12 个产物哈希一致，11 个解析输入／eval 文件哈希未变；输入 manifest 仍符合配置中的固定 SHA-256。

## 7. 复用与下一节点

Docling 在 P2.1 提供文档结构和 provenance，P2.2 通过本项目 adapter 消费这些结构并建立统一证据契约。PaperQA2 是 P2.5／P4 的主要问答和 Agent 复用目标，本节点保留其后续 adapter 所需的原始来源字段，尚未验证具体上游接口。Kotaemon 继续用于 P3 检索／P5 界面参考。

下一节点 **P2.3：固定 Embedding 模型及 revision，核验真实 tokenizer 与输入模板，建立隔离且可持久化的 Qdrant 索引**。索引入口必须检查成功 manifest、产物哈希和对应验证报告，不索引报告、样本或 eval 文件。
