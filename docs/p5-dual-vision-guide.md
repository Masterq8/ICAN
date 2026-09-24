# P5 双视觉论文案例使用说明

## 当前语料

网页研究卡支持三个集合：

| 集合 | 内容 | 索引点数 |
|---|---|---:|
| `swin_v1` | Swin Transformer 固定论文与源码 | 1,602 |
| `vision_mamba_v1` | Vision Mamba（Vim）论文与固定源码 | 9,869 |
| `qasper_train_v1` | QASPER train 方法示例 | 1,792 |

Vision Mamba 使用论文 `arXiv:2401.09417` 和 `hustvl/Vim` commit `dd0358ad1e42701f22afbefa0717cc8825cf9f45`。它与 VMamba 是不同模型；本集合只索引 Vim。每条论文证据保留 PDF 页码，代码证据保留仓库路径和行号。

现已补充 [8 道 Vim 开发题](../data/eval/vision_mamba_dev.jsonl)、[来源证据地图](../data/eval/vision_mamba_evidence.json)和 [Swin-T 逐项比较卡](vision-mamba-swin-comparison.md)。问题和标准答案留在 `data/eval`，不进入检索索引。可在项目根目录运行 `conda run -n ican python scripts/validate_vision_mamba_dev.py`，核对固定源哈希、PDF 页码、代码行与 v2 证据块。

## 本地启动

```powershell
cd frontend
npm run build
cd ..
conda activate ican
python scripts/serve_api.py
```

在页面顶部的语料选择中选 `Vision Mamba (Vim)` 或 `Swin Transformer`，输入研究问题后检索候选论文。选择论文可打开候选证据；再选择“从原文生成”创建筛选与实验信息卡。生成过程会调用配置的 DeepSeek 模型，并遵循本机 `.env` 里的模型预算。复查信息卡时，可打开证据页码／代码位置、同论文搜索并保存人工修订。

如不希望发生模型调用，可选择“读取已存卡”查看已有记录；新语料暂无历史记录时会明确提示。两篇论文分别生成信息卡后勾选并使用报告功能做字段对照。Swin 与 Vim 的任务、数据集、指标或输入设置通常不同，报告应显示为“不可直接排名”，用于并排比较原文陈述与证据位置。

## 构建产物与重建

新增材料使用独立的 v1 解析配置；共用的产品索引配置为 v2，旧 P4.6 评测产物保持原样。全新克隆时，先按[README数据恢复](../README.md#数据恢复与运行)下载并准备 Swin、QASPER、BGE-M3 与 v1 解析／分块产物。Vim PDF 和仓库未纳入 Git：从[arXiv PDF](https://arxiv.org/pdf/2401.09417)保存到`data/raw/papers/vision_mamba_2401.09417.pdf`，再按固定commit获取官方代码：

```powershell
git clone https://github.com/hustvl/Vim data/raw/repositories/Vim
git -C data/raw/repositories/Vim checkout dd0358ad1e42701f22afbefa0717cc8825cf9f45
```

先解析 Vim，再用组合v2配置重建所有三个分块数据集与索引：

```powershell
conda run -n ican python scripts/parse_swin.py --config configs/ingestion/vision-mamba-v1.json
conda run -n ican python scripts/chunk_corpus.py --config configs/chunking/v2.json
conda run -n ican python scripts/verify_chunks.py --config configs/chunking/v2.json
conda run -n ican python scripts/build_index.py --config configs/indexing/v2.json
```

成功索引指纹：`9ac56ab768fe11b9a49b281f729856c8be506a8678ebcaf0b7014d4d97d175dd`。构建报告位于 `data/indexes/bge-m3/v2/<fingerprint>/build_report.json`；产品 API 通过 `configs/indexing/v2.json` 读取索引。原 `configs/indexing/v1.json` 和 P4.6 结果保留作历史快照。

提醒：`scripts/serve_api.py` 当前默认读取索引v2，因此仅完成README里的旧v1恢复步骤时，网页检索还不能启动；必须完成本节的Vim恢复、v2分块和v2索引步骤。

## 当前边界

- 自动信息卡的字段抽取仍未通过 P4.6 工具提交质量门；生成结果需要人工审阅，不能当作完整或无误的论文事实。
- 研究卡对照保留字段与证据，不会把不同任务条件的模型自动排成性能名次。
- `/v1/agent/run` 仍限定 Swin 专项核查；Vision Mamba 当前支持网页论文检索、证据定位、自动／人工研究卡与跨论文报告，不复用 Swin 专属配置核查断言。
- Vim 开发题与比较卡是经固定来源核查的调试、展示材料；它们没有经过 P6 冻结评测，也不代表模型能自动回答全部题目。比较卡将 Vim-Ti、长序列微调版和 Hier-Vim 分开，并对不同训练条件标明不可直接排名。
