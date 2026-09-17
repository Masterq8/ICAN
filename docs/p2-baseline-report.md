# P2.6 基线报告：检索已完成，生成与语义评测待执行

日期：2026-09-17。状态：**in_progress**。本轮已完成评测管线、47题真实dense检索、官方QASPER评分接入和独立代码审查；**本轮生成调用为0**，等待用户选择批量调用预算。不能据以下结果宣称回答正确率、引用支持率或领域版优于默认版。

## 1. 固定材料与协议

- Swin dev12题，开发题及标注保持原字节；冻结8题只核对SHA，未解析问题或标准答案。
- QASPER train按question_id排序取前3题检查格式；validation10篇论文32题、57份答案标注，独立报告。训练小样本不代表训练集总体表现。
- 既有BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`，1024维归一化Cosine；索引 `3fcc38131d303a03b83cbe0dea77dc74b83398f597aee10e6a4fb1fbae9eaa87`。
- 单次检索Top8；Swin只限定collection，未按gold选择类型／路径。QASPER根据题目原paper_id限制到给定论文，符合其问答任务定义。
- 首次preflight完成全部检索；经相同问题、输入SHA、chunk正文／来源核验复用到最终 `data/processed/evaluation/p26-v2/`，原始检索协议保留在provenance。两版生成将消费同一快照，不再次检索。
- 快照SHA `14aa782abf9a15bfc43fc820ac22122c129388a47bc26304e47df6cef1558d7f`；已封存快照不能重新赋hash覆盖，生成／报告发现变更即拒绝。

## 2. 检索结果

所有数值为逐题macro平均。不同任务的指标定义和来源约束分别写明。

| Top-K | Swin必要定位召回，n=12 | Swin必要仓库证据完整行范围覆盖，n=12 | QASPER validation完整段落召回，n=31 |
|---|---:|---:|---:|
| 1 | 8.33% | 0.00% | 25.27% |
| 3 | 27.08% | 0.00% | 62.37% |
| 5 | 27.08% | 8.33% | 73.66% |
| 8 | 32.64% | 8.33% | 78.49% |

**Swin口径：** 论文以固定页码命中为代理，仓库证据以目标代码行相交为定位命中。完整行范围覆盖需要多个chunk联合覆盖标注中的全部区间，包含additional_path；这是严格的来源范围指标。页码／行号命中不证明语义必要证据已完整出现，粗粒度代码范围也可能包含回答不需要的行。因此不将上述定位指标命名为语义Required Evidence Recall。Top8仅2/12题找齐全部必要定位入口。

**QASPER口径：** 根据原段落unit ID和chunk字符范围，联合覆盖段落所有非空白字符才算完整召回；对多份可回答且带证据的标注取最佳比例。32题中31题适用该指标；有1份可回答标注未提供证据，4份标注为unanswerable，均保留明细和每份参考证据分母。一个题目可能同时包含不同类型标注。此样本的段落命中召回与完整召回相同；不能推广为所有长段落均不会拆分。Top8有24/32题完整覆盖至少一份非空证据标注，其余无参考证据题不算覆盖成功。

**Train格式样本：** 3题中2题带可回答证据标注，K1/3/5/8完整段落召回均为0。仅用作格式／错误检查，不与validation合并。

## 3. 失败样例与下一步

检索记录可直接定位以下开发题失败：

- swin_dev_01：前三项来自swin_mlp.py、swin_transformer_v2.py、swin_transformer_moe.py；Top8只命中P01，缺标准Swin-T配置和PatchEmbed代码证据。
- swin_dev_04：前三项为SwinV2分辨率微调YAML，未命中题目所需PatchEmbed／PatchMerging／stage构造入口。
- swin_dev_06：学习率问题召回MoE训练配置，缺config.py默认值与main.py运行时缩放。
- swin_dev_07：加载分支问题召回SimMIM／MoE工具文件，缺标准main.py分支。
- swin_dev_08：梯度累积问题召回SwinV2 YAML，缺标准训练循环及启动缩放代码。

这些是原始dense基线的实际失败，不在本节点用gold路径修正后覆盖基线。P3优先加入可从问题／仓库元数据识别的模型家族约束、精确符号／配置检索、BM25融合及重排序。参数用Swin dev／QASPER train决定，validation保留为本轮独立结果。

## 4. 待运行的问答对照

模型使用用户已配置的 `deepseek-flash`；每题每版最多1次、1536输出tokens、90秒，无summary／embedding／补查／重试／fallback。预计47题×2版=94次（其中6次train格式检查）。用户也可选47次领域版或暂只保留本地检索。

| 配置 | prompt／serializer | 实际证据范围 |
|---|---|---|
| adapter | 基于生产swin-evidence-v2，仅将中文要求改为问题语言；独立版本eval-adapter-v2-question-language-v1 | 检索顺序，最多8块／18000原文字符；详细位置和review标记 |
| paperqa-default | 固定PaperQA2 2026.8.12默认问答prompt及serializer；关闭自动补查以固定单轮预算 | 默认按score／name排序，最多5sources；记录实际送入的ID |

这是**同检索快照的默认问答配置对照**，未运行完整PaperQA2自主Agent／默认embedding及检索链。源码及prompt hash在manifest保存。生产API提示仍为中文v2，不因评测语言协议改变。

QASPER指标调用[作者官方evaluator](https://github.com/allenai/qasper-led-baseline/blob/afd0fb96bf78ce8cd8157639c6f6a6995e4f9089/scripts/evaluator.py)，按其规则分别对多份答案／证据标注取最佳F1。原始答句保留，评分前移除引用标记；证据从被引用chunk回溯原段落，段落命中Evidence F1与完整段落Evidence F1分别统计。词面F1受答案长度、语言和改写影响，不等于语义正确率。

生成后逐题审核Swin grading_points与QASPER参考答案，检查相邻引用是否支持结论，记录理由和实际审核者类型（助手／人类）；助手审核不标成人类复核。API answered等可靠性状态与gold supported／conditional等语义状态不直接比较字符串。当前答案指标、引用语义支持、语义状态准确率、耗时／tokens／费用均待生成；未生成的官方指标为null。

## 5. 耗时、可靠性与恢复

检索请求耗时中位数0.984秒，首题75.141秒，含首次索引核验和BGE-M3加载；没有剔除首题后宣称冷启动性能。费用目前没有生成支出，未来provider费用未提供时记null。

调用前started记录flush＋fsync，已开始键永久跳过；中断／失败不自动重试。未完成started计入失败及引用率分母，未知tokens单独计数。CLI单写者文件锁避免两个进程同时消耗同一运行预算。resume核对模型服务、输入／代码／prompt hash和密封快照；改变配置需新run，不将旧结果混入。

本轮完整测试136通过／1项Windows符号链接权限跳过，13项评测测试通过；pip check及改动范围Ruff／format通过。独立审查发现并修正快照可变、重新封存绕过、中断统计遗漏和无证据分母缺失，最终无剩余重要发现。61个受保护文件及索引identity未变。

## 6. 运行说明

```powershell
conda activate ican
# 新环境恢复材料和索引后，从头获取新快照。
python scripts/evaluate_baseline.py retrieval --run-dir data/processed/evaluation/new-run
python scripts/evaluate_baseline.py report --run-dir data/processed/evaluation/new-run
# 以下会调用用户API；max-calls为同一run累计上限，须符合已给定预算。
python scripts/evaluate_baseline.py generate --run-dir data/processed/evaluation/p26-v2 --max-calls 94
python scripts/evaluate_baseline.py report --run-dir data/processed/evaluation/p26-v2
```

当前最终产物：manifest.json、retrieval.jsonl、summary.json；生成将追加generation-identity.json、journal.jsonl，语义审核单独保存semantic-audit.jsonl。数据产物被Git忽略，协议、代码、报告和官方脚本／Apache-2.0许可入库。

P2.6完成条件还包括预算内真实生成、两版配置的答案／引用结果及语义审核。当前仍为in_progress，不提前进入P3或宣称生成基线完成。
