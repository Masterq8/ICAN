# Swin-T 第一版 RAG 问题集：社区调研与构建方法

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 调研日期 | 2026-09-15 |
| 目标产物 | 20 个带标准答案与必要证据的问题 |
| 数据划分 | 12 个开发题、8 个冻结测试题 |
| 当前状态 | 31 条候选来源、20 个正式题目和答案均已完成；测试集已冻结 |
| 固定实现 | `microsoft/Swin-Transformer` commit `f82860bfb5225915aca09c3227159ee9e1df874d` |

## 1. 本轮先解决什么

本轮不直接凭经验编写 20 道题，而是先从真实社区问题中建立候选池，再规定如何把候选问题转化为可评测的 RAG 样本。

社区帖子承担两项作用：

1. 证明问题真实出现过，并保留用户原始表达、上下文和常见误解。
2. 帮助确定题目类型、难度和检索路径。

社区回复不默认等于标准答案。标准答案必须由固定版本的论文、官方仓库代码、配置、官方训练日志或相应框架的官方文档支持。

## 2. 调研范围与方法

### 2.1 GitHub Issue

- 使用 GitHub API 获取 `microsoft/Swin-Transformer` 全部 Issue，排除 API 同时返回的 Pull Request。
- 本轮共检查 248 条非 PR Issue。
- 使用主题词做第一轮筛选：`input size`、`window`、`config`、`checkpoint`、`pretrain`、`fine-tune`、`batch`、`learning rate`、`reproduce`、`feature map`、`FLOPs`、`Patch Merging`、`normalization`、`AMP`、`distributed` 等。
- 对候选 Issue 读取正文和前若干条讨论，判断它是 Swin-T 本身的问题、其他 Swin 变体的问题，还是某个框架实现的版本问题。
- 补充检查 TorchVision、Hugging Face Transformers 和 SwinIR 等相关实现仓库，用于识别同名模型在不同实现中的行为差异。

### 2.2 技术论坛与论文讨论

- PyTorch Forums：收集迁移学习、输入尺寸、构造参数、线性嵌入和量化等使用者问题。
- Hugging Face Forums：收集任务头、语义分割和掩码图像建模等接口问题。
- Reddit `r/MachineLearning`：收集 shifted window、复杂度和 Swin/ViT 差异等论文理解问题。
- 论坛检索只用于发现问题。凡是带观点、预测或框架版本依赖的内容，都必须在入选前改写成可验证的事实问题，或直接排除。

## 3. 已核验的候选来源池

下表记录问题来源，不是最终 20 题。`优先`表示适合第一版；`条件`表示必须缩小范围或绑定版本；`排除`表示当前语料无法形成可靠标准答案。

### 3.1 官方 Swin 仓库

| 来源 | 社区问题主题 | 初判 | 转化时需要的金标准证据 |
|------|--------------|------|--------------------------|
| [Issue #96](https://github.com/microsoft/Swin-Transformer/issues/96) | 112×112 等非标准输入与 window size | 优先 | 模型尺寸断言、窗口划分代码、输入预处理 |
| [Issue #107](https://github.com/microsoft/Swin-Transformer/issues/107) | 梯度累积与大 batch 是否等价 | 优先 | loss 缩放、optimizer step、LR 运行时缩放代码 |
| [Issue #114](https://github.com/microsoft/Swin-Transformer/issues/114) | 从 224 权重微调到 384 的设置 | 优先 | `get_started.md`、384 配置、权重加载中的插值逻辑 |
| [Issue #117](https://github.com/microsoft/Swin-Transformer/issues/117) | 不同输入/window size 微调时的位置参数尺寸 | 优先 | `load_pretrained` 的删除、重建和插值分支 |
| [Issue #129](https://github.com/microsoft/Swin-Transformer/issues/129) | 代码中的 stage 组织和论文图示差异 | 优先 | 论文架构图、`BasicLayer` 与 `PatchMerging` 调用顺序 |
| [Issue #148](https://github.com/microsoft/Swin-Transformer/issues/148) | 训练日志、配置缺失与不收敛 | 条件 | 固定模型、命令、日志和配置；避免泛化为复现承诺 |
| [Issue #154](https://github.com/microsoft/Swin-Transformer/issues/154) | 默认关闭 APE 是否合理 | 优先 | 配置默认值、相对位置偏置代码、论文消融或维护者说明 |
| [Issue #165](https://github.com/microsoft/Swin-Transformer/issues/165) | FLOPs 代码与公式理解 | 条件 | 论文复杂度公式、对应 `flops()` 实现；需人工复算 |
| [Issue #171](https://github.com/microsoft/Swin-Transformer/issues/171) | 是否提供 ImageNet-22K 预训练 Swin-T | 条件 | 固定日期的 README 模型表；答案有时间依赖 |
| [Issue #176](https://github.com/microsoft/Swin-Transformer/issues/176) | 某些参数为何不做 weight decay | 优先 | optimizer 参数分组代码、模型的 no-weight-decay 列表 |
| [Issue #180](https://github.com/microsoft/Swin-Transformer/issues/180) | 无法复现论文精度 | 条件 | 论文指标、官方日志和完整配置；不能把推测写成原因 |
| [Issue #216](https://github.com/microsoft/Swin-Transformer/issues/216) | 配置合并后的运行状态 | 优先 | 配置递归合并、`--opts` 与专用参数的执行顺序 |
| [Issue #210](https://github.com/microsoft/Swin-Transformer/issues/210) | 四个 stage 的中间特征尺寸 | 优先 | 论文层级结构、`BasicLayer` 输出位置与下采样顺序 |
| [Issue #256](https://github.com/microsoft/Swin-Transformer/issues/256) | Patch Merging 与 stride-2 卷积的关系 | 条件 | 张量重排、Linear 和 LayerNorm 代码；限定“线性部分”等价范围 |
| [Issue #306](https://github.com/microsoft/Swin-Transformer/issues/306) | PatchEmbed 后为何有归一化 | 条件 | 代码能确认“有无”，但“为何”若论文无证据应标证据不足 |
| [Issue #360](https://github.com/microsoft/Swin-Transformer/issues/360) | `patches_resolution` 与 window size 的区别 | 优先 | `PatchEmbed` 初始化、变量定义与传播路径 |
| [Issue #144](https://github.com/microsoft/Swin-Transformer/issues/144) | ImageNet-22K 权重微调和分类头 | 优先 | 分类头类别数不匹配的映射与重置代码 |
| [Issue #378](https://github.com/microsoft/Swin-Transformer/issues/378) | resume 后训练状态变化 | 优先 | AUTO_RESUME、RESUME 与 PRETRAINED 控制流 |

### 3.2 相关实现仓库

| 来源 | 社区问题主题 | 初判 | 使用边界 |
|------|--------------|------|----------|
| [TorchVision #6227](https://github.com/pytorch/vision/issues/6227) | TorchVision Swin 是否支持动态分辨率 | 条件 | 只能考 TorchVision 指定版本，不能代替微软原始实现 |
| [TorchVision #7103](https://github.com/pytorch/vision/issues/7103) | eval 模式下 dropout 的历史缺陷 | 条件 | 必须绑定受影响的 commit/版本和修复状态 |
| [TorchVision #6558](https://github.com/pytorch/vision/issues/6558) | MLP 激活函数是否可配置 | 条件 | 用于比较实现差异，不能把 API 差异说成架构差异 |
| [Transformers #19780](https://github.com/huggingface/transformers/issues/19780) | Swin 图像分类导出 ONNX 后输出差异 | 排除 | 当前核心语料未固定该库版本和 ONNX 环境 |
| [SwinIR #13](https://github.com/JingyunLiang/SwinIR/issues/13) | W-MSA 与 SW-MSA 的 mask 使用 | 条件 | 只可作为问题线索；答案回到原始 Swin 论文和实现 |

### 3.3 技术论坛与论文讨论

| 来源 | 社区问题主题 | 初判 | 使用边界 |
|------|--------------|------|----------|
| [PyTorch Forums：修改 Swin 参数](https://discuss.pytorch.org/t/change-parameters-for-swin-transformer/199173) | 预训练模型怎样修改 stochastic depth | 条件 | 绑定 TorchVision 版本；可转为配置覆盖或权重兼容题 |
| [PyTorch Forums：非标准输入](https://discuss.pytorch.org/t/swin-transformer-for-image-classification/181995) | 100×100 图像如何用于 Swin-T 迁移学习 | 优先 | 回到固定实现检查尺寸约束，不能直接采用无回复帖子结论 |
| [PyTorch Forums：Linear Embedding](https://discuss.pytorch.org/t/what-is-the-linear-embedding-layer-in-swin-transformer/205045) | 论文中的线性嵌入在代码里是什么 | 优先 | 论文描述与 `PatchEmbed.proj` 联合取证 |
| [PyTorch Forums：量化](https://discuss.pytorch.org/t/how-to-quantize-a-swin-transformer-model-to-reduce-its-size/154643) | Swin 如何量化 | 排除 | 当前固定语料和产品范围不足以给出稳定标准答案 |
| [Hugging Face Forums：Swin 分割](https://discuss.huggingface.co/t/swin-transformer-for-segmentation/24831) | 分割任务头与 SimMIM/BEiT 的区别 | 条件 | 涉及库的历史接口；第一版优先保留架构事实，排除过时 API 状态 |
| [论文讨论：shifted 与 sliding window](https://www.reddit.com/r/MachineLearning/comments/qc4ph5/) | 两种窗口机制的连接方式与实际延迟 | 优先 | 标准答案仅使用论文正文、公式和实现；论坛解释不是证据 |
| [论文讨论：复杂度公式](https://www.reddit.com/r/MachineLearning/comments/p7a5aq/) | W-MSA 复杂度各项来源 | 条件 | 必须人工推导并让公式与符号定义对应 |
| [论文讨论：Swin 与 ViT 的采用差异](https://www.reddit.com/r/MachineLearning/comments/1b3bhbd/) | 为什么下游工作常选择 ViT 或 Swin | 排除 | 范围过大且含主观判断，无法由当前固定语料唯一回答 |

## 4. 从社区问题到评测题的转换流程

### 第一步：保留来源问题

保存帖子 URL、仓库、Issue 编号、标题、发布日期、正文摘要和采集日期。原帖仅作为 `question_provenance`，不可混入待检索的核心语料，避免系统直接背出社区答案。

### 第二步：原子化

一个正式题目只考一个主要判断。若帖子同时询问输入尺寸、窗口大小和权重兼容，拆成多个候选；最终只选择证据边界清楚的一项。题干必须明确模型变体、任务、实现和版本。

### 第三步：判断能否形成金标准

候选题需同时满足：

1. 可由当前固定语料回答，或应明确回答“证据不足”。
2. 结论在指定论文版本和 commit 下唯一、可复核。
3. 能标出必要证据，而不只是相关证据。
4. 不依赖下载完整 ImageNet、长时间训练或特定 GPU 才能确定。
5. 不要求预测未来、解释作者未披露的动机或评价主观优劣。

### 第四步：建立证据闭包

“证据闭包”指足以支持完整答案的最小证据集合。每条金标准证据必须保存：

- `source_id` 和来源类型；
- 论文版本或仓库 commit；
- PDF 页码/章节，或代码路径、起止行号、符号名；
- 它支持的具体 claim；
- 证据角色：`required`、`supporting` 或 `conflicting`。

配置类问题通常至少需要两段证据：声明默认值或 YAML 覆盖的配置，以及计算最终运行值的代码。只命中其中一段，不算完整召回。

### 第五步：先写证据表，再写标准答案

标注顺序固定为：`claim 列表 → 必要证据 → 条件和冲突 → 标准答案 → 问题题干`。这样可以减少先入为主和无证据补写。答案中的每个可核查 claim 都要映射到至少一个证据 ID。

### 第六步：分配答案状态

- `supported`：固定语料足以给出确定答案。
- `conditional`：答案只在指定实现、版本、配置或输入条件下成立。
- `conflicting`：权威来源之间存在实际冲突，答案需要并列说明。
- `insufficient`：现有权威语料不足以回答；标准行为是拒绝补写并指出缺少什么。

### 第七步：难度标注

- `L1 单证据定位`：一个权威片段即可回答。
- `L2 同源多跳`：需要同一仓库中两个以上文件或配置层级。
- `L3 跨源核对`：需要论文与代码、README 与日志等共同取证。
- `L4 冲突/不足判断`：相关内容很多，但仍需判断证据不充分或版本不适用。

## 5. 20 题的配额设计

### 5.1 内容配额

| 问题簇 | 开发集 | 冻结测试集 | 合计 |
|--------|--------|------------|------|
| 架构机制与张量变化 | 2 | 2 | 4 |
| 输入尺寸、patch 与 window 约束 | 2 | 1 | 3 |
| 配置继承与运行时计算 | 3 | 1 | 4 |
| 训练与复现设置 | 2 | 1 | 3 |
| 预训练、微调与 checkpoint | 1 | 1 | 2 |
| 官方实现与框架实现差异 | 1 | 1 | 2 |
| 冲突或证据不足 | 1 | 1 | 2 |
| **合计** | **12** | **8** | **20** |

### 5.2 难度配额

- L1：4 题，用于验证基础定位和引用格式。
- L2：7 题，用于验证代码、配置的同源多步检索。
- L3：6 题，用于验证论文—代码联合取证。
- L4：3 题，用于验证冲突处理和拒答能力。

### 5.3 划分规则

- 按问题簇切分，不做逐题随机切分。同义问题、同一 Issue 的拆分问题、相同证据闭包只能出现在一个集合。
- 开发集可以反复运行并用于调整分块、召回、reranker 和提示词。
- 冻结测试集在题目、答案、证据和评分规则完成双检后生成哈希；M2 基线完成前不用于提示词调优。
- 冻结测试失败案例只记录错误类型，不立即改题；下一数据集版本再把对应问题簇纳入开发集。

## 6. 数据字段

每行 JSONL 至少包含：

```json
{
  "id": "swin_<split>_<nn>",
  "split": "dev | test",
  "question": "<完成证据标注后再填写>",
  "question_provenance": {
    "url": "<社区帖子 URL>",
    "source_type": "github_issue | forum | paper_discussion",
    "captured_at": "2026-09-15"
  },
  "scope": {
    "paper_version": "arXiv:2103.14030v2",
    "repo_commit": "f82860bfb5225915aca09c3227159ee9e1df874d",
    "implementation": "microsoft/Swin-Transformer"
  },
  "category": "<问题簇>",
  "difficulty": "L1 | L2 | L3 | L4",
  "answer_status": "supported | conditional | conflicting | insufficient",
  "gold_answer": "<标准答案>",
  "gold_claims": [],
  "required_evidence": [],
  "supporting_evidence": [],
  "negative_evidence": [],
  "grading_points": [],
  "leakage_group": "<同义问题簇 ID>",
  "annotation_notes": ""
}
```

`negative_evidence` 保存“看起来相关但不足以支持答案”的片段，可用于评估 reranker 和引用忠实度。

## 7. 标注质量门禁

正式问题进入数据集前必须全部通过：

- 有可访问的真实社区来源，且保留采集日期。
- 模型、实现、任务和版本范围明确。
- 标准答案没有采用未经核验的社区回复。
- 每个 claim 都有必要证据或明确的证据不足说明。
- 代码证据绑定 commit、路径、行号和符号名。
- 论文证据绑定固定版本和 PDF 页码。
- 答案包含成立条件，不把局部等价写成完全等价。
- 与另一划分不存在同义题、同证据闭包或同一帖子拆分造成的泄漏。
- 一名标注者完成初标后，隔一轮按证据重新复核；有争议的题先移出，不凑数。

## 8. 评测口径

将检索与生成分开评分：

1. **Required Evidence Recall@K**：必要证据中有多少被 Top-K 完整召回。
2. **Evidence Set Exact Match**：是否找齐该题的最小证据闭包。
3. **Claim Correctness**：标准答案评分点覆盖率，允许同义表达。
4. **Citation Support Precision**：生成答案所引用的片段是否实际支持对应 claim。
5. **Answer Status Accuracy**：是否正确输出 supported、conditional、conflicting 或 insufficient。
6. **Abstention Accuracy**：证据不足题是否拒绝补写，以及是否指出缺失证据。

报告 dense、BM25、hybrid、hybrid + rerank 四种方案在同一数据版本上的结果，并保留模型、索引参数、提示版本、运行时间和成本。

## 9. 执行结果与后续

已完成：

1. 建立 31 条机器可读候选来源并记录纳入、保留或排除原因。
2. 建立 27 个统一证据 ID，并核验论文页码、代码路径和行号。
3. 完成 12 个开发题与 8 个冻结测试题，每题包含标准答案、claims、必要证据、评分点和来源 URL。
4. 完成 JSON/JSONL、证据引用、配额、唯一 ID 和 leakage group 检查。
5. 生成 `swin_eval_manifest.json`，记录文件 SHA-256 和冻结状态。

后续进入 P2：建立 PDF/代码解析、分块和基础索引，只使用开发集调试；冻结测试集仅用于阶段验收。

## 10. 当前固定语料中的主要证据入口

- 论文：`data/raw/papers/swin_transformer_2103.14030.pdf`
- 官方仓库：`data/raw/repositories/Swin-Transformer/`
- Swin-T 配置：`configs/swin/swin_tiny_patch4_window7_224.yaml`
- 默认配置与覆盖：`config.py`
- 训练与运行时缩放：`main.py`
- 架构实现：`models/swin_transformer.py`
- 参数分组：`optimizer.py`
- 输入预处理：`data/build.py`
- 官方使用说明：`get_started.md`
