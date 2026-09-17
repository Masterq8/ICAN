# P2.5：PaperQA2领域证据问答

## 实际复用与职责

固定 `paper-qa==2026.8.12`，上游 commit `57e89f7223b0960d5ee5ea048c69e3c47e088572`、Apache-2.0。实现实际调用 `Docs.aadd_texts`、`Docs.aquery`，复用 `Doc/Text/Context/PQASession/Settings`、prompt组织、上游引用格式化及token统计；没有fork上游。

现有BGE-M3／Qdrant负责检索。本项目adapter保留检索顺序、原文、版本、物理页／行／QASPER段落和表格核验状态，并将引用映射成编号及结构化证据。完整嵌套位置放在外部注册表，避免上游Text的hash限制。Context score=1仅表示证据已准入，dense分数单独保留。

生成服务通过公开 `call_single` 接口桥接OpenAI SDK，返回fhlmi的 `LLMResult`。没有启用LiteLLM路由；这样可显式设置SDK `max_retries=0`、每请求一次调用，避免未知模型费用估计。调用前显式传入禁用summary／embedding的对象，关闭上游补查、pre/post和回答迭代。

PaperQA2既会在格式化时清理未知ID，也会在保存raw_answer前删除示例ID。因此捕获**未经上游修改的LLMResult.text**进行校验，不以清理后的答案判断引用有效性。上游格式化照常执行，API使用受校验原文映射编号；私有reasoning不返回或记录。

## 配置与运行

`configs/qa/v1.json`固定最多8块、正文总预算18000字符、输出1536tokens、生成超时90秒和prompt版本。预算保留完整chunk，从超预算处剔除剩余块，并记录实际包含／剔除的ID；元数据和问题额外计入模型输入token。

复制 `.env.example` 为 `.env`，填写以下变量。已存在的环境变量优先于本机文件；生成配置不从开发工具读取。

| 变量 | 意义 |
|---|---|
| ICAN_LLM_PROVIDER | 首版为 `openai`，表示OpenAI兼容协议 |
| ICAN_LLM_MODEL | 用户选定 `deepseek-flash` |
| ICAN_LLM_BASE_URL | `https://api.deepseek.com` |
| ICAN_LLM_API_KEY | 用户服务密钥，仅本机保存 |

`.env`、原始材料、处理产物和索引被Git忽略。网络请求只使用配置的HTTPS地址；API请求不能覆盖服务地址或凭据。[DeepSeek官方接口](https://api-docs.deepseek.com/)说明OpenAI兼容协议；本实现依据[思考模式说明](https://api-docs.deepseek.com/guides/thinking_mode/)设置 `thinking.type=disabled`，用固定预算生成最终答案。

```powershell
conda activate ican
python -m pip install -r requirements/ican-lock.txt
python scripts/serve_api.py
```

Qdrant local仍使用单worker。`GET /health`不加载Embedding或生成模型。`POST /v1/evidence/search`保持原有行为。

## 问答接口与操作流程

`POST /v1/qa/answer`示例请求：

```json
{
  "query": "官方Swin-T配置中的WINDOW_SIZE是多少？",
  "collection": "swin_v1",
  "limit": 8,
  "filters": {
    "source_types": ["config"],
    "path_prefixes": ["data/raw/repositories/Swin-Transformer/configs/swin/swin_tiny_patch4_window7_224.yaml"]
  }
}
```

1. 选择collection，输入问题；需要确定模型变体时约束真实快照路径。
2. 接口检索原始证据并调用一次PaperQA2回答流程；无证据直接返回，不构造生成模型。
3. 阅读answer，按 `citations[].number` 查看对应完整 `evidence.text`、source位置及版本。编号已为未来网页证据面板提供映射；本节点尚无网页或PDF高亮。
4. 依据status决定接受、补充材料或人工核验。

| status | 意义／处理 |
|---|---|
| answered | 存在可解析的合法引用；仍需语义支持评测 |
| insufficient_evidence | 无输入证据，或模型明确无法回答核心问题 |
| citation_invalid | 引用未知／格式错误的ID，或确定性答案未带合法引用；不能当可信答案 |
| review_required | 实际引用包含待核验解析候选，应对照原PDF检查 |

`review_required=false`仅表示没有已标记的解析风险。引用存在和定位有效不等于结论已获验证。输出还包括实际证据ID、索引指纹、模型标识、PaperQA2／prompt版本和usage。费用未知时为null，不宣称为零。

无效参数／collection为422；索引或模型不可用为503；生成超时为504。错误不返回provider内部信息。首版不重试或自动fallback。

## 验证与记录

```powershell
python -m pytest tests -q
python scripts/verify_paperqa2.py
# 真实生成：每个选中样例一次调用，会产生用户API费用。
python scripts/verify_paperqa2.py --live --case paper
python scripts/verify_paperqa2.py --live --case config
```

默认脚本使用真实检索及真实PaperQA2包、fake LLM，记录为offline，不能算回答效果验收。`--live`使用用户明确配置的服务。运行结果位于被忽略的 `data/processed/qa/`；新运行用时间戳命名，保留失败记录、用量、索引／prompt版本及参考的上游默认Settings。脚本不读取冻结gold。

首轮真实验收：论文题2224输入／709输出tokens，配置题1614／172。配置题回答四项参数，引用官方YAML第6–9行。论文题有合法的PDF引用并回答机制，但主动扩展未问到的偏移量，附加证据不足标记，导致功能验收未通过。保留 `live-smoke.json`，将prompt从v1改为v2：限定所问范围、约300中文字，明确人工核验标记的含义；仅追加一次论文调用验证。

追加论文验收v2通过：2301输入／263输出tokens、answered，引用PDF第2、4页；记录 `live-paper-20260917T055824425535Z.json`，完整HTTP请求耗时20.514秒（检索及生成，可能包含首次索引核验／模型加载）。配置通过记录属于v1，不宣称已在v2重跑。共3次真实生成，6139输入／1144输出tokens，没有自动重试；provider费用未提供，记录为null。

最终123项pytest通过，1项Windows真实符号链接权限跳过；22项QA测试使用实际PaperQA2和受控fake／SDK MockTransport。pip check及改动范围Ruff通过，独立审查确认原始引用校验修复。六个索引identity库版本和61个受保护文件哈希未变。

当前功能样例不是开发集／冻结集得分。公平比较PaperQA2默认方案与领域adapter、检索覆盖和引用语义支持进入P2.6；自主补查和Agent工具规划进入P4。
