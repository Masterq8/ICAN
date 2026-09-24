# Vision Mamba 来源问题集与 Swin 比较设计

## 目标与范围

完成 `task_plan.md` 中 P5 第四优先剩余交付：建立少量可核查的 Vision Mamba（Vim）问题、标准答案和必要证据；形成与固定 Swin-T 案例在架构、复杂度、输入处理、实验设置四个维度的比较卡。此次材料是开发集和产品展示依据，不进入 Swin 8 题冻结测试或 P6 最终评测。

## 已确认的来源边界

- Vim：`arXiv:2401.09417`，本地 PDF SHA-256 `15c3ccf7340a412e6ce408526c03a67e412d9bb4958e6c0bfe310394b6337444`；`hustvl/Vim` commit `dd0358ad1e42701f22afbefa0717cc8825cf9f45`。
- Swin：`arXiv:2103.14030v2`，`microsoft/Swin-Transformer` commit `f82860bfb5225915aca09c3227159ee9e1df874d`。沿用已有 Swin 证据地图和冻结问题集，不修改其字节。
- 主比较对象为官方 `vim_tiny_patch16_224_bimambav2_final_pool_mean_abs_pos_embed_with_midclstok_div2` 与 `swin_tiny_patch4_window7_224`。Vim-Ti、长序列微调版和附录 Hier-Vim 分开标注。

## 方案选择

1. 仅写叙述式比较文档：最快，但难以验证引用和复用到 RAG 开发集。
2. **采用：独立问题 JSONL、证据地图、可机检的来源校验及逐项比较卡。** 便于追溯原文和作为后续开发样本，又不提前运行冻结评测。
3. 新建 Vim 冻结基准并做模型评测：会提前扩大 P6 范围，也缺少独立评测题来源，因此留待后续版本。

## 数据与交付

- `data/eval/vision_mamba_dev.jsonl`：8 个 Vim 专项开发题，沿用 Swin 的 `question`、`gold_answer`、`gold_claims`、`required_evidence` 等字段，并显式标记开发用途和固定实现。问题覆盖 patch/token 数、分类 token、双向扫描控制流、长序列步幅、复杂度、训练与结果、变体边界。
- `data/eval/vision_mamba_evidence.json`：每个 `VPxx` / `VRxx` 证据含来源版本、PDF 物理页或固定源码行、至少一个实际索引 `chunk_id` 和原文短锚点。比较卡复用现有 Swin 证据 ID，并另列其 v2 索引块位置。
- `docs/vision-mamba-swin-comparison.md`：同口径比较卡。每项先列两个固定对象的事实及证据，随后写出可比较结论和限制。性能数字仅按各自论文报告记录，不做训练设置不一致的模型排名；所有速度、显存数字必须标明论文的比较对象与条件。
- `scripts/validate_vision_mamba_dev.py`：只读校验固定哈希、问题 ID 和证据闭包、页码/代码行与索引块来源及短锚点，拒绝跨模型或其他 Vim 变体的证据误绑。
- `docs/p5-dual-vision-guide.md`、`task_plan.md`、`progress.md`：更新交付和使用边界。

## 核查规则

1. 社区讨论可用于以后发现问题，本轮标准答案只依据固定 PDF 与官方仓库。问题集不宣称是从社区 Issue 采集。
2. PDF 页码为文件物理页；代码行号以固定 commit 的原文件为准；索引块必须来自当前 v2 `vision_mamba_v1` 或 `swin_v1` 的受限来源。
3. 每个结论拆成原子 claim。`required_evidence` 指向能支撑全部 claim 的最小证据集合。若同一证据含图表或复杂排版，人工核对 PDF 页面，避免仅凭解析表格下结论。
4. Vim 论文对全局注意力的复杂度比较与 Swin 的窗口注意力不是同一个比较实验。两者在固定窗口和状态维度时对图像 token 数均可线性增长，但常数、全局信息路径和吞吐不可据此排序。
5. Vim 论文 Table 1 的 Vim-Ti 76.1 与带 `†` 的 78.3 对应不同训练阶段；附录 Table 7 的 Hier-Vim-T 不能代替 Vim-Ti。Swin 自身论文与 Vim 附录引用的 Swin-T top-1 数值如有差异，分别注明出处，不合并成单一“实测值”。

## 验收

- 8 题均具备可追溯答案、至少一个必要证据 ID；所有引用由只读校验脚本通过，PDF 表格关键值另经物理页面核对。
- 四维比较每一栏有双方来源和明确的可比性判断；不混入 VMamba、Hier-Vim、Swin-V2 或未知版本。
- 原 Swin 冻结题及证据文件哈希不变；本节点不调用付费模型，也不使用其结果改动 P6 冻结测试。
