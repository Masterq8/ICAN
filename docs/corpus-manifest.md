# 语料与模型资源清单

> 状态值：`planned`、`downloaded`、`verified`、`gated`、`skipped`。commit、哈希和文件大小在下载后填写。

## 核心语料

| ID | 名称 | 角色 | 论文 | 官方代码 | 权重入口 | 权重访问 | 本地状态 |
|----|------|------|------|----------|----------|----------|----------|
| C01 | Swin Transformer / Swin-T | 首个深度核查案例 | https://arxiv.org/abs/2103.14030 | https://github.com/microsoft/Swin-Transformer | https://github.com/SwinTransformer/storage/releases/download/v1.0.0/swin_tiny_patch4_window7_224.pth | 公开直链 | verified |
| C02 | Vision Mamba / Vim | 第二个深度核查案例 | https://arxiv.org/abs/2401.09417 | https://github.com/hustvl/Vim | https://huggingface.co/hustvl/Vim-tiny-midclstok | 公开；含 76.1 与 78.3 两个 Tiny checkpoint | verified |
| C03 | Mamba | Vim 的基础架构与依赖来源 | https://arxiv.org/abs/2312.00752 | https://github.com/state-spaces/mamba | https://huggingface.co/state-spaces | 公开模型集合；比赛版不下载语言模型权重 | verified |
| C04 | SAM 3 | 分割方向复杂案例 | https://arxiv.org/abs/2511.16719 | https://github.com/facebookresearch/sam3 | https://huggingface.co/facebook/sam3 | 人工授权；模型库约 10.33 GB | gated |

## 相似架构候选

| ID | 名称 | 类别 | 论文 | 官方或作者代码 | 权重情况 | 建议优先级 |
|----|------|------|------|----------------|----------|------------|
| A01 | ViT | 视觉 Transformer 基线 | https://arxiv.org/abs/2010.11929 | https://github.com/google-research/vision_transformer | 官方提供多组预训练与微调权重 | 高，已下载论文与代码 |
| A02 | DeiT | 数据高效视觉 Transformer | https://arxiv.org/abs/2012.12877 | https://github.com/facebookresearch/deit | 官方仓库含预训练模型 | 高，已下载论文与代码 |
| A03 | VMamba | 纯视觉状态空间模型 | https://arxiv.org/abs/2401.10166 | https://github.com/MzeroMiko/VMamba | 仓库提供模型入口 | 高，已下载论文与代码 |
| A04 | MambaVision | Mamba-Transformer 混合骨干 | https://arxiv.org/abs/2407.08083 | https://github.com/NVlabs/MambaVision | Hugging Face 预训练权重 | 高，已下载论文与代码 |
| A05 | SAM 2 | 图像与视频提示分割 | https://arxiv.org/abs/2408.00714 | https://github.com/facebookresearch/sam2 | Tiny 至 Large 公开权重 | 高，已下载论文与代码 |
| A06 | MobileSAM | 轻量 SAM | https://arxiv.org/abs/2306.14289 | https://github.com/ChaoningZhang/MobileSAM | 仓库含 MobileSAM 权重 | 中 |
| A07 | EfficientSAM | 高效 SAM | https://arxiv.org/abs/2312.00863 | https://github.com/yformer/EfficientSAM | 作者仓库提供权重入口 | 中 |
| A08 | FastSAM | CNN Segment Anything | https://arxiv.org/abs/2306.12156 | https://github.com/CASIA-IVA-Lab/FastSAM | Model Zoo 提供权重 | 中 |
| A09 | U-Net | 经典编码器—解码器分割架构 | https://arxiv.org/abs/1505.04597 | https://lmb.informatik.uni-freiburg.de/people/ronneber/u-net/ | 原作者归档含训练网络与 Caffe/Matlab 依赖 | 高，论文与 2015 官方包已下载 |

## 纳入建议

- 比赛版实际建库优先纳入 C01–C04 与 A01–A05，共 9 篇核心论文。
- A06–A08 用于展示轻量化路线，可在时间允许时纳入。
- 不下载所有权重；核心核查依赖论文、配置与代码，权重只下载一个可演示的小型代表版本。
- 所有 Git 仓库保存下载时 commit；所有 PDF 和实际下载权重计算 SHA-256。

## 固定的代码版本

| 仓库 | commit | 本地相对路径 | 代码许可 |
|------|--------|--------------|----------|
| Swin-Transformer | `f82860bfb5225915aca09c3227159ee9e1df874d` | `data/raw/repositories/Swin-Transformer` | MIT |
| Vim | `dd0358ad1e42701f22afbefa0717cc8825cf9f45` | `data/raw/repositories/Vim` | Apache-2.0 |
| mamba | `e9594ce1c732d97440f0332fdc43170a2294dbfa` | `data/raw/repositories/mamba` | Apache-2.0 |
| sam3 | `660a5e9e1b8b4c02c0ad97229b88a09a6e4ff5b7` | `data/raw/repositories/sam3` | SAM License |
| vision_transformer | `64801f1b3b367b3611cc27a3d45cc22870a36fb3` | `data/raw/repositories/vision_transformer` | Apache-2.0 |
| deit | `7e160fe43f0252d17191b71cbb5826254114ea5b` | `data/raw/repositories/deit` | Apache-2.0 |
| VMamba | `2ed52ead062a51a64521ed3871d52914bf532876` | `data/raw/repositories/VMamba` | 见仓库 LICENSE |
| MambaVision | `7860a506b2eb844eaaae676f08461ce8c3c26f43` | `data/raw/repositories/MambaVision` | 见仓库 LICENSE；权重另有许可 |
| sam2 | `2b90b9f5ceec907a1c18123530e92e794ad901a4` | `data/raw/repositories/sam2` | Apache-2.0，另含第三方 BSD 文件 |

## 已下载权重

| 模型 | 文件 | 大小 | SHA-256 | 说明 |
|------|------|------|--------|------|
| Swin-T | `swin_tiny_patch4_window7_224.pth` | 109.05 MB | `9F71C168D837D1B99DD1DC29E14990A7A9E8BDC5F673D46B04FE36FE15590AD3` | ImageNet-1K，官方 GitHub Release |
| Vim-Tiny | `vim_t_midclstok_76p1acc.pth` | 109.69 MB | `FEDB1E60267F3BC7B2A8443F2DDEAD8D39E019D10247A87252162B3789801FD5` | ImageNet-1K，官方 Hugging Face |

## 已下载论文

| 文件 | 大小 | SHA-256 |
|------|------|--------|
| `swin_transformer_2103.14030.pdf` | 1.30 MB | `DFDC7631FE2A35BB5892080B9C0EEADC4432D55CF1856F84BC88802EFA877A7C` |
| `vision_mamba_2401.09417.pdf` | 1.07 MB | `15C3CCF7340A412E6CE408526C03A67E412D9BB4958E6C0BFE310394B6337444` |
| `mamba_2312.00752.pdf` | 1.11 MB | `ADF70ED1803C85B1899DEC3E21F3AF0B124411439E8654B840EA65F7B9F52B2E` |
| `sam3_2511.16719.pdf` | 33.88 MB | `19E8A44E7FC33BC6CF237F6B4AC3948A79B33F7FFC62D09012FCAC6FC9FB016F` |
| `vit_2010.11929.pdf` | 3.57 MB | `8CE7B83971A14508CA711A27C875C9B6914C4F6767CF3150FB1CA6C07AA056D6` |
| `deit_2012.12877.pdf` | 0.53 MB | `A0FBDD27C115594326FD75B3A0F569FB94CBF0B5C34C84FDC204D993064188BB` |
| `vmamba_2401.10166.pdf` | 3.09 MB | `A003346525C77909E2A9C096B7D5BC8E4D7E2049DEB1B597618B76F9E144A015` |
| `mambavision_2407.08083.pdf` | 14.70 MB | `DD89DE18B35CAAE38F8CB13FA98F5B84211F58108CA423C6C2E6B24F3285AFBC` |
| `sam2_2408.00714.pdf` | 12.12 MB | `664F5C4254DB441569ECFE36A2A2FA91A1ECEC5F4D31B3BCC5D451193EFC2C0D` |
| `unet_1505.04597.pdf` | 1.57 MB | `A3172B2124F38E260DC2C7ED968D87C31BC94DBC19A42A7AB3DCBD7534319C44` |

## 其他已下载素材

| 文件 | 大小 | SHA-256 | 用途 |
|------|------|--------|------|
| `u-net-release-2015-10-02.tar.gz` | 184.32 MB | `260C51948E9E0F3FE1F1282DBEDAF2CA69BEA38B8392EF8DF6D751E58B234740` | 原作者 2015 Caffe/Matlab 代码、已训练网络与依赖归档 |

## 本地目录约定

```text
data/
  raw/
    papers/          # 官方论文 PDF
    repositories/    # 浅克隆的官方/作者仓库
    weights/         # 仅保存选定的演示权重
  catalog/           # 机器可读元数据
  eval/              # 开发集与冻结测试集
```
