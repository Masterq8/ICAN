# Swin-T RAG 评测集 v1

| 项目 | 内容 |
|------|------|
| 数据集版本 | v1.0 |
| 构建日期 | 2026-09-15 |
| 开发集 | 12 题 |
| 冻结测试集 | 8 题 |
| 问题来源 | GitHub Issue、PyTorch Forums、论文讨论 |
| 金标准来源 | Swin v1 论文与固定官方仓库 commit |

> 本文用于人工审阅。完整题干、标准答案、claim、评分点、来源 URL 和证据 ID 以 `data/eval/swin_dev.jsonl`、`data/eval/swin_test.jsonl` 为准。本文以及两个 JSONL 文件不得进入被评测的 RAG 索引。

## 1. 开发集

### swin_dev_01：Linear Embedding

- **问题：** 论文中的 linear embedding 在代码中由什么实现，224 输入时输出形状是什么？
- **标准答案：** 使用 kernel=stride=4 的 Conv2d 同时完成 4×4 切块和到 96 维的投影，然后 flatten、transpose，并按配置执行 LayerNorm；输出为 `B×3136×96`。
- **必要证据：** P01、R02、R05。

### swin_dev_02：W-MSA/SW-MSA 交替

- **问题：** 连续 blocks 如何交替窗口，window=7 时 shift 和 mask 如何设置？
- **标准答案：** 偶数索引 block 的 shift=0，奇数索引为 `7//2=3`；只有移位 block 建立 mask，并做 cyclic shift 和 reverse shift。
- **必要证据：** R08。

### swin_dev_03：patches_resolution

- **问题：** `patches_resolution` 是否等于 window size，它在 224 配置下是多少？
- **标准答案：** 它是 `img_size//patch_size` 得到的 token 网格，值为 56×56；四个 stage 依次使用 56、28、14、7，window size 是独立的 7。
- **必要证据：** R01、R02、R05、R18。

### swin_dev_04：112×112 输入失败

- **问题：** 只把 IMG_SIZE 改为 112 能否保留原结构直接运行？
- **标准答案：** 不能。分辨率链为 28→14→7，第三次 PatchMerging 接收 7×7，触发 H/W 必须为偶数的断言。
- **必要证据：** R05、R06、R09、R18。

### swin_dev_05：Drop Path 配置覆盖

- **问题：** 使用 Swin-T YAML 时最终 DROP_PATH_RATE 是 0.1 还是 0.2？
- **标准答案：** 是 0.2。0.1 是全局默认值，Swin-T YAML 后合并并覆盖为 0.2；题设没有再提供命令行覆盖。
- **必要证据：** R01、R02、R03、R04。

### swin_dev_06：运行时学习率

- **问题：** BASE_LR=5e-4、单卡 batch=128、8 进程、累积 2 步时最终 LR 是多少？
- **标准答案：** `5e-4×128×8/512×2=0.002`。
- **必要证据：** R01、R12。

### swin_dev_07：RESUME/PRETRAINED 优先级

- **问题：** 同时设置 RESUME 和 PRETRAINED 时加载哪个，AUTO_RESUME 找到文件后如何处理？
- **标准答案：** RESUME 优先；PRETRAINED 只在 RESUME 为空时加载。AUTO_RESUME 找到 checkpoint 会改写 RESUME。
- **必要证据：** R10。

### swin_dev_08：梯度累积等价性

- **问题：** batch=128 与 batch=64、累积 2 步是否完全等价？
- **标准答案：** 在样本、模型状态、随机操作且无 micro-batch 依赖等条件一致时，平均梯度可数学对应；代码执行 loss/2 并每两步更新，同时按有效 batch 缩放 LR。随机操作、浮点顺序和分布式执行使其不能保证运行轨迹完全一致。
- **必要证据：** R11、R12。

### swin_dev_09：Weight Decay 参数组

- **问题：** 哪些参数进入 weight_decay=0 的组，相对位置偏置是否在其中？
- **标准答案：** 一维参数、bias、skip list 和 skip keywords 命中的参数不衰减；absolute position embedding 和 relative position bias table 都被显式跳过。
- **必要证据：** R13。

### swin_dev_10：位置参数插值

- **问题：** 不同 window/token 网格微调时，预训练加载器如何处理位置张量？
- **标准答案：** 删除并重建位置索引、relative coords 和 attention mask；相对位置偏置长度变化且 heads 相同时做双三次插值；APE 网格变化时也做二维双三次插值。
- **必要证据：** P03、R14。

### swin_dev_11：Stage 边界差异

- **问题：** 为什么 hook 整个 BasicLayer 时前三个返回值像是下一 stage？
- **标准答案：** 论文把 Patch Merging 画在下一 stage 开始；代码在当前 BasicLayer 的 blocks 后执行 downsample，因此整个 BasicLayer 的返回值已经下采样。
- **必要证据：** P01、R09、R18。

### swin_dev_12：PatchNorm 动机

- **问题：** 为什么 PatchEmbed 后加入 LayerNorm，固定语料能否证明作者动机？
- **标准答案：** 证据只能确认 PATCH_NORM 默认开启以及 LayerNorm 的位置；Swin v1 论文和固定代码没有给出专门动机或消融，应回答证据不足。
- **必要证据：** P01、R01、R04、R05。

## 2. 冻结测试集

### swin_test_01：W-MSA 复杂度

- **问题：** W-MSA 的复杂度公式是什么，为什么固定 M 时对 patch 数线性？
- **标准答案：** `4hwC²+2M²hwC`；固定 M 时两项均对 hw 一次增长。代码用窗口数乘每窗口 QKV、attention 和输出投影 FLOPs，对应同一公式。
- **必要证据：** P02、R19。

### swin_test_02：四个 Stage 规格

- **问题：** 标准 Swin-T 四个 stage 的分辨率、通道、depths 和 heads 是什么？
- **标准答案：** 分辨率 56/28/14/7，通道 96/192/384/768，depths `[2,2,6,2]`，heads `[3,6,12,24]`。
- **必要证据：** P04、P06、R02、R18。

### swin_test_03：运行时动态输入

- **问题：** 按 img_size=224 构建的模型能否直接接收 256 或 100 的 tensor？
- **标准答案：** 不能；PatchEmbed 首先断言运行时 H/W 必须与构建时 `self.img_size` 完全相等。
- **必要证据：** R05。

### swin_test_04：完整配置优先级

- **问题：** 默认值、BASE YAML、当前 YAML、`--opts` 和专用参数的优先级是什么？
- **标准答案：** 从低到高依次为全局默认值、递归 BASE、当前 YAML、`--opts`、代码显式处理的专用命令行参数。
- **必要证据：** R03。

### swin_test_05：随机种子与确定性

- **问题：** 入口设置了哪些随机源，能否保证 bitwise 完全一致？
- **标准答案：** 使用 `SEED+rank` 设置 torch、CUDA、NumPy 和 Python random，并开启 `cudnn.benchmark=True`；代码没有证明完整确定性，不能断言 bitwise 一致。
- **必要证据：** R12。

### swin_test_06：分类头不匹配

- **问题：** 预训练分类头类别数不匹配时如何加载？
- **标准答案：** 21841→1000 使用 `map22kto1k.txt` 选择 head 行；其他不匹配将当前 head 置零、删除 checkpoint head 键并以 strict=False 加载其余参数。
- **必要证据：** R14。

### swin_test_07：Patch Merging 与卷积

- **问题：** 完整 PatchMerging 是否完全等价于 kernel=2、stride=2 的 Conv2d？
- **标准答案：** 四路拼接后的纯 Linear 可在重排权重后表示为该卷积；完整模块在线性层前还有 LayerNorm，因此不等价于一层裸 Conv2d。
- **必要证据：** P01、R06。

### swin_test_08：81.2/81.3 指标冲突

- **问题：** Swin-T 224² ImageNet-1K top-1 应写 81.2 还是 81.3？
- **标准答案：** 论文 Table 1(a) 为 81.3，固定 commit README 为 81.2。报告必须并列标注来源；以仓库 checkpoint 为复现对象时可采用其 81.2 口径，同时保留论文差异。
- **必要证据：** P07、R16。

## 3. 使用约束

- 开发阶段只能使用 `swin_dev.jsonl` 调整分块、检索、reranker 和提示词。
- `swin_test.jsonl` 只在阶段验收运行；测试问题、答案和本文不得被索引。
- Required Evidence Recall 必须按完整证据集合计算。
- `conditional`、`conflicting`、`insufficient` 是答案的一部分，不能在评分时统一当作普通生成题。

