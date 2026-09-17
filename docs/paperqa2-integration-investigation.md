# P2.5：PaperQA2接入前置核验

核验日期：2026-09-17。官方源码与依赖核验后已安装固定版本、实现公开接口adapter并运行真实生成；未修改上游。实施与验收记录见 [问答说明](p2-qa-guide.md)。以下保留接入前的接口分析，安装结果另述。

## 固定上游身份

- 包：`paper-qa==2026.8.12`，Python >=3.11，与ican的3.11一致。
- Git tag：`v2026.08.12`；commit：`57e89f7223b0960d5ee5ea048c69e3c47e088572`。
- 来源：[PyPI元数据](https://pypi.org/project/paper-qa/2026.8.12/)、[固定源码](https://github.com/Future-House/paper-qa/tree/57e89f7223b0960d5ee5ea048c69e3c47e088572)。上游代码Apache-2.0。
- 本地只读参考：`data/raw/reference-projects/paper-qa/`，由Git忽略；未把该目录列入证据allowlist。

## 实际公开接入能力

| 接口 | 固定源码中的行为 | 本项目用途 |
|---|---|---|
| `Docs.aadd_texts(texts, doc, settings, embedding_model)` | 接收已分块的Text；可通过defer_embedding推迟编码；按dockey去重 | 验证既有chunk可导入，不重复PDF解析／分块 |
| `PQASession.contexts`、`Context`、`Text`、`Doc` | 公开数据对象，可显式提供Context；Text允许extra metadata | 为外部检索结果创建上下文，另存完整来源注册表 |
| `Docs.aquery(session, ...)` | 已有contexts时可跳过get_evidence；组织prompt并调用LLM；记录tokens／cost；格式化答案和引用 | 复用真实回答／引用流程，固定单轮流程 |
| `Settings.custom_context_serializer` | 提供异步serializer替换默认按score／name排序的行为 | 保留检索顺序及实际输入证据范围 |
| `QdrantVectorStore` | 已存在；使用AsyncQdrantClient，payload为序列化Text，point ID来自embedding | 与现有`{id,collection,chunk,...}`契约不同，不能直接加载既有集合 |

源码位置：[docs.py](https://github.com/Future-House/paper-qa/blob/57e89f7223b0960d5ee5ea048c69e3c47e088572/src/paperqa/docs.py)、[types.py](https://github.com/Future-House/paper-qa/blob/57e89f7223b0960d5ee5ea048c69e3c47e088572/src/paperqa/types.py)、[settings.py](https://github.com/Future-House/paper-qa/blob/57e89f7223b0960d5ee5ea048c69e3c47e088572/src/paperqa/settings.py)、[llms.py](https://github.com/Future-House/paper-qa/blob/57e89f7223b0960d5ee5ea048c69e3c47e088572/src/paperqa/llms.py)。

## 必须处理的接口细节

1. README示例出现`add_texts`，本固定版本实际公开方法是异步`aadd_texts`；实现以源码为准。
2. `aquery`会创建LLM／summary／embedding对象，即使已有contexts。adapter必须显式传入受控对象，禁止隐式调用默认OpenAI embedding或再次编码文档。
3. 默认context serializer按score和name排序，并限制answer_max_sources。外部dense分数不能伪装成LLM的0–10相关性分数；保留原始retrieval_score，显式定义admitted context score及排序。
4. Context ID自动生成只基于问题与正文前缀；本项目应显式绑定chunk ID并检测碰撞，以避免相同正文不同版本或路径的证据混淆。
5. `PQASession.populate_formatted_answers_and_bib_from_raw_answer`会删除未知引用ID。必须在raw_answer上检测未知ID，然后才返回结构化引用状态，不能把被删除的伪引用当成引用通过。
6. Text的extra值若包含dict/list，其hash可能失败；完整嵌套location保留在本项目引用注册表，Text只传递必要、可哈希的标识字段。

## 依赖dry-run

`pip install --dry-run paper-qa==2026.8.12`成功解析出21个新增／变更包，包括fhaviary0.37.0、fhlmi1.0.7、LiteLLM1.84.1、tantivy0.26.2。packaging26.3降为25.0；安装前快照见requirements/ican-before-p25-lock.txt，新增锁见requirements/paperqa2-lock.txt，实际完整环境已更新ican-lock.txt。安装后pip check通过，六个索引identity库版本保持不变，真实BGE检索和离线问答通过。

实现前应保存既有lock，固定新增包版本并安装后检查依赖、完整测试、真实BGE检索；不要为新增库破坏P2.3索引身份。索引identity所包含的torch／transformers／sentence-transformers／qdrant-client／tokenizers／numpy应保持原版本。

## 推荐结论

优先使用“现有Qdrant检索→领域Context adapter→PaperQA2 Docs.aquery”的公开接口方案。P2.5先完成固定单轮带引用问答，P4再引入Agent补查和核查工具。完整迁移上游存储需要转换payload与重新验证；小范围fork目前没有已证实的必要性。

开发助手切换最高阶模型不等于作品拥有API配置。实施阶段使用用户明确提供的DeepSeek服务，密钥仅存忽略的.env，未读取或使用其他工具凭据。fake LLM只能证明接口行为。

## 实施中新增发现

上游在设置session.raw_answer之前还会移除默认示例引用pqac-0f650d59，单独校验session.raw_answer不足以发现它。现以CapturedAnswerModel捕获原始LLMResult.text，实际执行上游aquery后验证未经清理的文本；回归覆盖合法引用混合该未知示例ID。独立只读审查确认修复。

运行时采用OpenAI SDK单调用桥接fhlmi公开LLMResult契约，没有使用LiteLLM路由或默认重试。保留上游回答组织、对象适配、格式化和token统计；API最终编号由本项目注册表映射，以保证未知引用不会被隐藏。
