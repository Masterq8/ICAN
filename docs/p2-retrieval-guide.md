# P2.4：只返回证据的检索接口

## 目的与边界

本节点将P2.3的固定BGE-M3／Qdrant索引提供为只读HTTP接口。它只返回已入库的chunk、来源版本、页码或行号、核验标记和Cosine分数；不会生成回答、摘要、报告，亦不会规划或执行Agent动作。

服务默认读取不可变索引版本`3fcc38131d303a03b83cbe0dea77dc74b83398f597aee10e6a4fb1fbae9eaa87`。首次实际查询会核验模型账本和阶段输入，再加载固定本地模型；`GET /health`不加载模型或打开Qdrant。

## 启动与调用

```powershell
conda activate ican
python scripts/serve_api.py
```

Qdrant local会锁定数据库目录，因此脚本固定单worker。不要用多worker启动；需要并发服务时改为Qdrant server，并保持相同payload契约。

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/evidence/search `
  -ContentType application/json `
  -Body '{"query":"Swin-T 的窗口大小配置是多少？","collection":"swin_v1","limit":5,"filters":{"source_types":["config"],"path_prefixes":["data/raw/repositories/Swin-Transformer/configs/swin/"]}}'
```

请求字段：

| 字段 | 规则 |
|---|---|
| `query` | 去除首尾空白后为1–4096字符；直接以固定BGE-M3编码 |
| `collection` | `swin_v1`、`qasper_train_v1`或`qasper_validation_v1` |
| `limit` | 1–20，默认5 |
| `filters.source_types` | 可选：`paper`、`code`、`config`、`documentation` |
| `filters.path_prefixes` | 可选的相对POSIX前缀，拒绝绝对路径、反斜杠和`..` |

返回每条证据的`rank`、`score`、`chunk_id`、原始`text`、`review_required`和`source`。`source`包含`source_id`、`source_type`、`source_path`、固定`source_version`与`location`。没有匹配时返回200和空`results`；非法请求或collection返回422；索引、账本或本地数据库不能可靠使用时返回503，不泄露本机绝对路径。

请求日志只记录请求ID、索引指纹、collection、过滤条件、结果数和耗时；不写查询原文、证据正文、向量、模型提示或密钥。

## 真实验证

```powershell
python scripts/verify_retrieval_api.py
```

该命令通过实际FastAPI路由发起两次中文功能查询。仅按`config`过滤时，前列包含SwinV2和SwinMoE；再限定`data/raw/repositories/Swin-Transformer/configs/swin/`后，5条结果全部位于标准Swin配置目录。结果写入该不可变索引目录下的`retrieval_smoke.json`，只保存路径、位置、排名和分数。

这证明路径约束和证据定位可用，不证明窗口大小问题已经答对，也不使用冻结答案。P3仍需评估BM25、混合检索和更精确的配置实体约束。

## 后续边界

P2.5将验证PaperQA2对本接口／证据DTO的适配，并开始带引用问答。届时首次进入Agent规划或回答生成前，应先切换到最高阶模型。
