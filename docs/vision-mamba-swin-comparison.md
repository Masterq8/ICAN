# Vision Mamba 与 Swin-T：来源可核查比较卡

**比较对象：** 固定 `hustvl/Vim` commit `dd0358ad1e42701f22afbefa0717cc8825cf9f45` 中的 `vim_tiny_patch16_224_bimambav2_final_pool_mean_abs_pos_embed_with_midclstok_div2`，以及固定 `microsoft/Swin-Transformer` commit `f82860bfb5225915aca09c3227159ee9e1df874d` 中的 `swin_tiny_patch4_window7_224`。论文分别为 [Vision Mamba](https://arxiv.org/abs/2401.09417) 的本地固定 PDF 与 [Swin Transformer](https://arxiv.org/abs/2103.14030) 的 arXiv v2。证据 ID、原文短锚点和完整 Vim v2 索引块 ID 见 [`vision_mamba_evidence.json`](../data/eval/vision_mamba_evidence.json)；Swin 既有证据定义见 [`swin_evidence.json`](../data/eval/swin_evidence.json)。

这张卡比较原文陈述及固定实现，不是一次统一硬件、权重和训练配方下的性能复测。PDF 页码均为文件物理页。

| 维度 | Swin-T：固定模型 | Vim-Ti：固定模型 | 可比结论与边界 |
|---|---|---|---|
| 架构 | 4 个 stage，深度 `[2,2,6,2]`；4×4 patch 后通过三次 PatchMerging 形成层级特征。连续块使用规则窗口与移位窗口注意力，窗口边长 7。见论文第3–4页 `P01/P02`、配置 `R02`、代码 `R08/R18`。 | 16×16 patch 后直接堆叠 24 个 Vim 块，Tiny 隐层维度 192；固定工厂选 `bimamba_type="v2"`。块内做正反向状态空间扫描，固定 `if_divide_out=True` 时在第245行合并后除以2；分类 token 位于序列中间。见 Vim 论文第4页 `VP02/VP03`，代码 `VR03/VR05/VR09/VR10`。 | 二者都把图像转为 token，但 Swin 的多尺度窗口注意力与此处 Vim-Ti 的单尺度双向 SSM 是不同的信息传播方式。Vim 论文附录的四阶段 **Hier-Vim** 是另一变体，不能写成固定 Vim-Ti（`VP11/VP12`）。 |
| 复杂度 | 论文第4页给窗口注意力 `Ω(W-MSA)=4hwC²+2M²hwC`，其中 `h×w` 是该 stage 的 token 网格，`M=7` 为窗口边长；固定 `M,C` 时对 `hw` 线性（`P02`）。 | 论文第5页把全局注意力 `4LD²+2L²D` 与 SSM `3L(2D)N+L(2D)N` 对比；此处用 `L` 重命名原文的序列长度 `M`，避免与 Swin 的窗口边长混淆。固定 `D,N` 时 SSM 对 `L` 线性（`VP04/VP05/VP06`）。 | 两篇论文的公式都显示各自指定条件下随 token 数线性增长。Vim 的式子比较对象是**全局注意力**，不能据此推出它比 Swin 的窗口注意力更快或更省显存。实际吞吐还依赖 token 数、模型宽度、实现和硬件。 |
| 224 输入处理 | patch size/stride=4，首个网格 `56×56=3136`；后续 stage 为 `28×28、14×14、7×7`。固定 `PatchEmbed` 对输入高宽做等于配置值的断言（`P01/R05/R18`）。 | 普通工厂 patch size/stride=16，网格 `14×14=196`，加单个分类 token 为 197；长序列微调工厂保留 patch size=16、stride 改为 8，网格 `27×27=729`，加 token 为 730。固定 `PatchEmbed` 也断言输入高宽（`VP09/VR01/VR02/VR03/VR05/VR06`）。 | token 数、patch 粒度、stage 组织不同，不能把两个首层 token 数直接当作同等计算量。Vim 的 `†` 长序列阶段是 224 图像上更密的 patch 提取，并非默认把输入改为 384。 |
| ImageNet-1K 实验设置与结果 | Swin 自身论文第6页 Table 1(a) 报 Swin-T 224²、**29M** 参数、**4.5G** FLOPs、top-1 **81.3%**（`P07`）；第9页描述 AdamW、batch 1024、初始 LR `10^-3`、wd 0.05、300 epoch、20 epoch warm-up，且不用 EMA（`P05`）。 | Vim 论文第5页 Table 1 报 Vim-Ti 224²、**7M** 参数、top-1 **76.1%**；`Vim-Ti†` 仍列 224²、7M，长序列微调后 **78.3%**（`VP07`）。第6页描述基准训练 AdamW、batch 1024、初始 LR `10^-3`、wd 0.05、300 epoch、**使用 EMA**；`†` 另有 30 epoch、stride 8、LR `10^-5` 的阶段（`VP08/VP09`）。 | 数据集、输入尺寸和 top-1 指标名称一致，但参数量、结构及训练阶段不同；仅可并列报告各论文结果，不能据此作受控架构排名。Vim 的 Table 1 不给出与 Swin Table 1 同口径的 FLOPs。 |

## 变体和数字冲突的处理

- Vim 第13–14页附录将 **Hier-Vim-T** 列为四阶段 `[2,2,5,2]`、30M 参数、top-1 82.5%（`VP11/VP12/VP13`）。这是从 Swin 层级结构构造的另一模型，不能把 82.5% 写进固定 Vim-Ti 的信息卡。
- Vim 附录 Table 7 引用 Swin-T 为 **28M / 81.2%**（`VP13`）；Swin 原论文 Table 1(a) 报 **29M / 81.3%**（`P07`）。两个来源的值按出处分别保留。当前比较卡采用各模型原论文的主表；未重新训练或裁定这些数字为何有差异。
- Vim 论文第1页图1文字中的 1248×1248 图像 2.8 倍速度和 86.8% 显存节省，比较对象是 **DeiT**（`VP14`），且是特定高分辨率特征提取场景，不能转述为相对 Swin 的提升。
- Vim `if_bidirectional=False` 关闭的是外层成对执行层的分支；固定工厂的 `bimamba_type="v2"` 仍在 Mamba 块内部使用正反向路径；`if_divide_out=True` 实际执行第245行合并语句（`VR05/VR07/VR08/VR09/VR10`）。固定工厂虽设 `final_pool_type='mean'`，有分类 token 时先返回中间 token（`VR03/VR04/VR05`）。

## 索引证据定位

下表给出比较卡主要证据在 **v2 索引**中的完整块 ID。Vim 的全部 24 项来源及短锚点以 JSON 证据地图为准；Swin 的 `Pxx/Rxx` 含义沿用既有冻结证据地图，本表只补充新的 v2 块定位，不修改原冻结文件。

| 证据 | 原始位置 | v2 `chunk_id` |
|---|---|---|
| Vim `VP03` | PDF 第4页，§3.4 | `chunk:a18d168456a6ed716d521d561708ffbc3b8c1ad3e2003ddafbf1c72db89c4d21` |
| Vim `VP04` | PDF 第5页，式(5) | `chunk:9b78f26461356d222184bfbf8292e8a902e41cf5f21b1398ba5a39e5be0c1120` |
| Vim `VP05` | PDF 第5页，式(6) | `chunk:0dcf7d9bfb52ba56b415bee88ba6a7e631c67f48c362a375ba0f1c903d5cf239` |
| Vim `VP07` | PDF 第5页，Table 1 | `chunk:5d9e2a8b10f5d2e4dbc65221adba3a24017b1a9b47e95337bcd517599c7b910e` |
| Vim `VP08` | PDF 第6页，§4.1 | `chunk:e24a2e1ab049796cc68912e99746da8c56d7448bfd459c5a8f06c115c66f8397` |
| Vim `VP09` | PDF 第6页，§4.1 | `chunk:fa976ece7506b0d2f22b4912eef220ada406a94cfe79f4219af08c4e28a74a36` |
| Vim `VP11` | PDF 第13页，Hier-Vim | `chunk:26df11280a05d955be90cf312d658548a19f60f18048ac8d5f07aaf033246c8c` |
| Vim `VP12` | PDF 第13页，Table 6 | `chunk:1adf734994fa7f2512be29b3b97df079ba08380ddf5dfbfd405e12f204ca8d7a` |
| Vim `VP13` | PDF 第14页，Table 7 | `chunk:87feb423dc8071be484090a2c22f0da47ad259add0d830d0b89277295cd1f8a5` |
| Vim `VP14` | PDF 第1页，图1文字 | `chunk:7bd5b6d358054e3d9aeafe01a8d4b995655df3bacda891c5245b3fd0f58a0947` |
| Vim `VR01` | `vim/models_mamba.py:42–53` | `chunk:2d616a3885912603ce4876f30615eec007d829156cea2b8a65067383f0c79fdc` |
| Vim `VR03` | `vim/models_mamba.py:385–447` | `chunk:4062512784dab558569673614716852845f528822ff756bae5e8f428fc3b4181` |
| Vim `VR05` | `vim/models_mamba.py:555–566` | `chunk:a9f6e493af646b60ee3e1154902d6500d3e475a96fa16b94d106d22898cdeab3` |
| Vim `VR06` | `vim/models_mamba.py:568–579` | `chunk:5e8453868df844e44c73cefe37d6fd3f02af82e5c2273601a19c7bcec1bc45ea` |
| Vim `VR09` | `mamba_simple.py:168–244` | `chunk:9381d5c68e99b315dd90723f2a8d939faae862c2fef60030396c3cbf00733598` |
| Vim `VR10` | `mamba_simple.py:242–245` | `chunk:274210b5f1a8458a4b8683cf2daa6827584cd7a2643b66bc5f06bfc70dc7d467` |
| Swin `P01` | PDF 第3页，§3.1 | `chunk:d30829fffd1f82ddad3bf87b42364e1e5aee61ccd89564678cff59c21e46e588` |
| Swin `P02` | PDF 第4页，式(2) | `chunk:f208b66d33349483d3e44a183d3676eb7cc5262286990fbfafd7592fba1d8192` |
| Swin `P05` | PDF 第9页，Appendix A2.1 | `chunk:e995602c7dba196a81771ccf400135c98f4cfd278755fe8ece91b3a72827efe1` |
| Swin `P07` | PDF 第6页，Table 1(a) | `chunk:97ef175046ac3da6716bafc3eae4c18ec83867eda47988ad3a95034070da4f6b` |
| Swin `R05` | `models/swin_transformer.py:448–475` | `chunk:0f147af11e9a6ff4998760e94c3ac3788b3378c4171e6c0a8a7fea6f113d30db` 与 `chunk:2cefb942b7528d2af811a6af15ca38bd2efdacc4e2bbbafd5650866e4f5a752e` |
| Swin `R18` | `models/swin_transformer.py:512–565` | `chunk:a75612ae170b7a8096fde151c103c5a46099ac862695b02151073712cfa97765` |

## 用法

8 道 Vim 开发题在 [`vision_mamba_dev.jsonl`](../data/eval/vision_mamba_dev.jsonl)。在项目根目录执行 `conda run -n ican python scripts/validate_vision_mamba_dev.py`，先核验固定源、页/行、索引块和题目证据闭包；再用 `vision_mamba_v1` 集合做开发调试。题目、答案和比较卡均是 gold/说明材料，**不得加入 RAG 检索集合**，也不是 P6 冻结集。
