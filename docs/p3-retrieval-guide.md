# P3 混合检索与重排序使用说明

## 组成与复用

沿用 P2 的已核验分块、BGE-M3 向量和 Qdrant collection，不重建索引。新增本地 BM25、RRF 融合、模型家族过滤、重排序及结构证据补充。PaperQA2 的公开接口 adapter 继续负责回答和引用。

Kotaemon 仅作为“范围过滤→向量／文本候选→重排→TopK”的流程参考，已阅读固定 commit `9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9` 的 [VectorRetrieval](https://github.com/Cinnamon/kotaemon/blob/9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9/libs/kotaemon/kotaemon/indices/vectorindex.py)。本项目未安装其运行时，也未复制该模块；RRF、结构补充和统一证据契约由本项目实现。

重排序实际使用 [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)，Apache-2.0，固定 revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`。模型配置和逐文件身份见 `configs/reranking/v1.json`、`data/catalog/reranker-bge-v2-m3.json`。本地 FP16 CUDA、batch2、查询与片段合计最多1536 tokens；超长对数在 trace 中报告，返回证据原文不截断。

## 启动

```powershell
conda activate ican
python -X utf8 scripts/prepare_reranker.py
# 普通下载停滞时，可续传固定版本的公开权重：
python -X utf8 scripts/prepare_reranker.py --http-ranges
python scripts/serve_api.py
```

依赖和 BGE-M3／持久化索引的准备沿用 [P2索引说明](p2-indexing-guide.md)。模型缓存约2.29GB，不提交到Git。健康检查不加载向量或重排序模型；实际首次检索会核验本地文件并加载模型。

## 请求

`POST /v1/evidence/search`：

```json
{
  "query": "Swin-T的命令行参数如何覆盖YAML配置？",
  "collection": "swin_v1",
  "strategy": "hybrid_rerank",
  "family": "auto",
  "limit": 8,
  "filters": {"source_types": ["code", "config"]}
}
```

同样的 `strategy`、`family` 可传入 `POST /v1/qa/answer`，由现有 PaperQA2 adapter 消费证据。检索本身不调用生成模型；回答需要已配置的 `ICAN_LLM_*`，参见 [P2问答说明](p2-qa-guide.md)。网页交互仍在P5，当前可通过Swagger `/docs`操作。

| strategy | 行为 |
|---|---|
| dense（默认） | 保留P2无自动家族限制的向量基线；显式family约束转为dense_scoped |
| dense_scoped | 先限定家族及用户范围，再向量排序 |
| bm25 | 范围内精确词、符号、文件路径检索 |
| hybrid | 每路最多40候选，RRF常数60，合并去重 |
| hybrid_rerank | 融合后最多48候选重排，再补同一代码结构的既有片段 |

`family`可选 `auto/all/swin_v1/swin_v2/swin_mlp/swin_moe/simmim`。auto在Swin collection缺少明确变体时默认v1；问题同时明确多个家族时用all，保留比较所需候选。显式请求优先。共享训练入口、论文和README保留；过滤基于来源路径，不能保证共享文档中的每段文字都只讨论v1。

问题明确Swin-T/S/B/L时，YAML候选也按尺寸限定；比较多个尺寸则保留各尺寸。显式`.yaml`文件名限定配置候选到该文件及已入库的静态`BASE`引用闭包；未找到该文件时不返回其他YAML替代。共享Python入口仍可检索。结构补充优先问题或固定展开词中的具名类／函数，以及具名YAML的默认值与合并函数；这些是静态证据，未执行配置加载。

类型条件、路径前缀条件与家族条件取交集；多个路径前缀取并集。所有候选通道、重排与结构扩展遵守同一范围。

## 如何检查证据与分数

返回证据保持原 `chunk_id/text/source/version/location/review_required`。代码／配置按原行号引用，论文按原页码引用；15个待核验表格块仍保留标记。

`trace`记录家族及理由、扩展检索词、每路候选、融合／重排候选、补充块、模型身份与截断计数。BM25采用正值IDF `log(1+(N-df+0.5)/(df+0.5))`，并对路径与结构名称增加词项权重。术语和CLI扩展由固定规则生成，不使用评测答案。

`score_meaning`分别说明Cosine、BM25、RRF或未校准的重排序logit；它们不应直接互比，也不是答案正确率。结构补充块如果未参与重排，score用0占位；以trace中的补充ID判断角色。最多补3块，输出仍不超过请求limit；不会拼接新文本或编造跨块行号。

## 可复现评测

```powershell
python -X utf8 scripts/evaluate_retrieval_strategies.py --run-dir data/processed/evaluation/p3-final-v3 --phase all
python -X utf8 scripts/verify_p3_retrieval_api.py
python -X utf8 scripts/verify_p3_snapshot_equivalence.py
python -X utf8 scripts/evaluate_baseline.py report --run-dir data/processed/evaluation/p3-qa-v1
```

先跑12道Swin开发题与3道QASPER train题；参数固定后再跑已观察过的32道validation。六组消融中的 `hybrid_rerank_raw` 从同一重排候选列表派生，不额外加载模型或发起调用。输入、代码、模型、索引指纹和输出SHA均记录，变更后必须新建run。冻结8题只校验SHA；原P2.6快照与94次journal保留。

`p3-final-v3`是当前代码的封存检索；`p3-qa-v1`是此前v4证据生成的47份adapter回答。修复短查询／字段边界后47题实际准备输入完全一致，未追加生成。旧v4源码身份已变化，不能重新导出成当前身份。已有run身份匹配时复读；源码变化时另建run。Qdrant本地索引单进程访问，上述命令顺序运行。

若后续主动安排另一轮真实回答，需要使用全新的目标目录并重新审核，以下是付费执行示例，本轮没有执行：

```powershell
python -X utf8 scripts/prepare_p3_answer_run.py --source data/processed/evaluation/p3-final-v3 --run-dir data/processed/evaluation/p3-qa-next
python -X utf8 scripts/evaluate_baseline.py generate --run-dir data/processed/evaluation/p3-qa-next --max-calls 47
```

本节点只对改进策略生成47份回答，与原47份adapter基线作对照，不对每个消融重复生成。已开始的请求不会自动重试，旧答句审核不能用于新回答。实测结果及限制见 [P3评测报告](p3-retrieval-report.md)。
