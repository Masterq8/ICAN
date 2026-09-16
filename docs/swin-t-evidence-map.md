# Swin-T 评测集证据地图

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 标注日期 | 2026-09-15 |
| 论文 | `swin_transformer_2103.14030.pdf`（arXiv v2 / ICCV 2021，14 页） |
| 官方实现 | `microsoft/Swin-Transformer` |
| 固定 commit | `f82860bfb5225915aca09c3227159ee9e1df874d` |
| 用途 | `swin_dev.jsonl` 与 `swin_test.jsonl` 的统一证据 ID |

## 1. 证据使用规则

- `Pxx` 表示论文证据，页码按 PDF 文件页码计数。
- `Rxx` 表示固定 commit 的仓库证据，行号按当前快照计数。
- 社区 Issue 和论坛只保存于 `question_provenance`，不作为标准答案的必要证据。
- 一个问题的 `required_evidence` 是支持完整答案的最小集合；只召回其中一部分不算证据闭包完整。
- 行号可用于人工核验；后续分块时还要保存符号名，避免代码增删导致只靠行号失效。

## 2. 论文证据

| ID | PDF 页码 | 章节/位置 | 支持内容 |
|----|----------|-----------|----------|
| P01 | 3 | Section 3.1 | 4×4 patch 的原始维度、线性嵌入、Patch Merging 的 2×2 拼接和 4C→2C 投影 |
| P02 | 4 | Section 3.2，Eq. (1)–(3) | MSA/W-MSA 复杂度；固定 M 时线性复杂度；连续块交替 W-MSA 与 SW-MSA |
| P03 | 5 | Section 3.2，Figure 4 / Eq. (4) | cyclic shift、attention mask、相对位置偏置、不同窗口尺寸微调时的双三次插值 |
| P04 | 5 | Section 3.3 | Swin-T 的 C=96、depths={2,2,6,2}、默认 M=7 |
| P05 | 9 | Appendix A2.1 | 224 训练设置、随机深度比例、较大分辨率微调策略 |
| P06 | 10 | Table 7 | 224 输入下四个 stage 的下采样倍率、分辨率、通道和 block 数 |
| P07 | 6 | Table 1(a) | 论文报告 Swin-T 224² ImageNet-1K top-1 为 81.3 |
| P08 | 8 | Table 4 / 讨论 | relative position bias、absolute position embedding 与 shifted window 消融 |

## 3. 仓库证据

所有路径均相对于 `data/raw/repositories/Swin-Transformer/`。

| ID | 文件与行号 | 符号/位置 | 支持内容 |
|----|------------|-----------|----------|
| R01 | `config.py:24-32,63-84,151-168` | 全局默认配置 | 单卡 batch=128、image size=224、drop path=0.1、patch=4、APE=False、PATCH_NORM=True、base LR=5e-4、accumulation=1 |
| R02 | `configs/swin/swin_tiny_patch4_window7_224.yaml:1-9` | Swin-T YAML | drop path=0.2、embed dim=96、depths、heads、window=7 |
| R03 | `config.py:268-311` | `_update_config_from_file` / `update_config` | BASE→当前 YAML→`--opts`→专用命令行参数的覆盖顺序 |
| R04 | `models/build.py:34-52` | `build_model` | DATA 与 MODEL 配置如何传入 `SwinTransformer` |
| R05 | `models/swin_transformer.py:448-475` | `PatchEmbed` | 固定输入尺寸断言；Conv2d patch projection；flatten/transpose；可选 LayerNorm |
| R06 | `models/swin_transformer.py:315-350` | `PatchMerging` | H/W 偶数断言；四路切片拼接；LayerNorm；4C→2C Linear |
| R07 | `models/swin_transformer.py:100-155` | `WindowAttention` | 相对位置偏置表、QKV、attention 加偏置及输出投影 |
| R08 | `models/swin_transformer.py:205-245,248-294,397-406` | `SwinTransformerBlock` / `BasicLayer` | shift 大小、mask、cyclic shift；偶数块 shift=0、奇数块 shift=window//2 |
| R09 | `models/swin_transformer.py:409-423,548-563` | `BasicLayer.forward` / layer 构造 | 前三个 BasicLayer 在 blocks 后执行 PatchMerging，最后一层不下采样 |
| R10 | `main.py:125-145` | auto-resume / checkpoint loading | auto-resume 可改写 RESUME；RESUME 有值时加载 checkpoint；PRETRAINED 仅在无 RESUME 时加载 |
| R11 | `main.py:193-205` | `train_one_epoch` | loss 除以累积步数；每 N 个 micro-batch 更新梯度和 scheduler |
| R12 | `main.py:319-339` | 启动与 LR 缩放 | 每个 rank 的种子、`cudnn.benchmark=True`、按单卡 batch×world size×累积步数线性缩放 LR |
| R13 | `optimizer.py:19-39,59-81`; `models/swin_transformer.py:580-586` | 参数分组 | 一维参数、bias、skip 名称和相对位置偏置不做 weight decay |
| R14 | `utils.py:45-126` | `load_pretrained` | 删除位置索引/mask；位置参数插值；分类头不匹配时的映射或重置 |
| R15 | `data/build.py:125-161` | `build_transform` | 训练与验证变换；crop 与直接 resize 分支 |
| R16 | `README.md:110-118` | 预训练模型表 | 仓库表报告 Swin-T 224² ImageNet-1K top-1 为 81.2，并关联权重/config/log |
| R17 | `get_started.md:207-214` | Fine-tuning on higher resolution | 官方给出的 224→384 微调命令示例 |
| R18 | `models/swin_transformer.py:448-565` | stage resolution/channel 构造 | patch resolution、每层通道 `embed_dim*2^i`、分辨率 `/2^i`、前三层 PatchMerging |
| R19 | `models/swin_transformer.py:161-172,300-309` | `flops()` | QKV、attention、输出投影、窗口数与每窗口 FLOPs 的代码计算 |

## 4. 关键配置链

### 4.1 Swin-T drop path

`config.py 默认 0.1 (R01) → Swin-T YAML 设为 0.2 (R02) → YAML 后的命令行覆盖仍可继续修改 (R03) → build_model 传入模型 (R04)`

因此，使用该 Swin-T YAML 且没有后续覆盖时，生效值是 0.2。

### 4.2 学习率运行时计算

`BASE_LR 默认值 (R01) → YAML/命令行覆盖 (R03) → BASE_LR × 单卡 batch × world size / 512 → 若 accumulation>1 再乘 accumulation (R12)`

问题必须明确单卡 batch、进程数和累积步数；否则不能给出唯一数值。

### 4.3 checkpoint 与 pretrained

`AUTO_RESUME 查找输出目录 → 找到时写入 MODEL.RESUME → 有 RESUME 就加载 checkpoint → 仅 PRETRAINED 有值且 RESUME 为空时加载预训练权重 (R10)`

## 5. 人工推导记录

### 5.1 224 输入的四级分辨率

- PatchEmbed：224/4=56，通道 96。
- 三次 PatchMerging：56→28→14→7，通道 96→192→384→768。
- 与论文 Table 7（P06）和构造代码（R18）一致。

### 5.2 112 输入为何失败

- PatchEmbed 得到 112/4=28。
- 前两次 PatchMerging 得到 28→14→7。
- 第三个 PatchMerging 接收 7×7，触发 H/W 必须为偶数的断言（R06）。
- 这说明只修改 `DATA.IMG_SIZE=112` 并保留四级结构不足以运行。

### 5.3 batch=128、8 进程、accumulation=2 的 LR

`5e-4 × 128 × 8 / 512 × 2 = 0.002`。这里的 batch 是单 GPU batch（R01），公式来自 R12。

### 5.4 Patch Merging 与 Conv2d

四路 2×2 切片拼接后的 `Linear(4C,2C)` 可在权重按拼接顺序重排后表示为 kernel=2、stride=2 的卷积。但完整官方模块在 Linear 前还有依赖当前样本统计的 `LayerNorm(4C)`（R06），所以“整个 PatchMerging 等同于一层裸 Conv2d”不成立。

## 6. 已确认的冲突与不足

- **指标冲突：** 论文 Table 1(a) 为 81.3（P07），固定 commit README 为 81.2（R16）。评测答案应并列报告，不能擅自选择其一。
- **动机不足：** 代码能确认 `PATCH_NORM=True` 且 PatchEmbed 后执行 LayerNorm（R01/R05），但固定论文和代码没有明确说明加入这一层的作者动机。该问题的正确状态为 `insufficient`。
- **复现归因不足：** 只有最终精度而没有命令、日志、环境和数据处理信息时，不能从论文与仓库唯一判断复现偏差原因。

