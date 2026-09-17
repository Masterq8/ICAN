# P2.5：PaperQA2证据适配与带引用问答设计

## 目标与方案

消费P2.4已验证的证据检索服务，实际复用固定`paper-qa==2026.8.12`的上下文、回答生成、引用格式化与用量统计。交付领域adapter、只读问答API、模型配置契约、接入试验记录及样例结果。

推荐公开数据对象适配：Qdrant检索→`Doc/Text/Context/PQASession`→`Docs.aquery`。另外两种方案是迁移到上游QdrantVectorStore（需要转换payload与重验索引），或fork上游（需要额外维护）。当前已核验公开接口足够，采用第一种，保持P2.3索引不变。

## 固定流程

1. 校验用户问题、collection和来源过滤，复用P2.4查询契约。
2. 从现有服务检索最多8块，保持检索顺序。通过明确的字符总预算剔除末尾块，记录实际送入模型的chunk ID；不静默截断原文。
3. 无证据时直接返回`insufficient_evidence`，不调用生成模型。
4. 将每个块映射为上游公开对象，建立`Context.id→chunk/source/location/version/review_required`注册表。正文仍为原始证据；路径、版本及人工核验状态在序列化prompt中可见。
5. 将构建的PQASession传给`Docs.aquery`。显式关闭自动补取证据、pre/post prompt，传入受控LLM／embedding对象，禁止默认远程embedding和重复入库。
6. 从raw_answer提取引用，检查引用ID属于实际送入模型的集合，再转换为可点击的编号和结构化来源。
7. 返回答案及引用状态、token用量、模型标识、prompt版本、索引指纹和实际输入证据ID。

这是一轮固定问答流程；P4再加入自主工具选择、多步补查与Agent停止条件。

## 引用与可靠性

- Context ID显式基于完整chunk ID计算，并在单请求注册表检测碰撞。
- 同一来源不同chunk分别保持页／物理行／QASPER段落位置；QASPER不生成虚构PDF页码。
- 识别raw_answer中的未知引用ID，返回`citation_invalid`；不得依赖上游删去伪引用后将答案标为通过。
- 没有任何合法引用的确定性回答同样标为`citation_invalid`。
- 引用格式有效只证明ID及定位可解析，不证明证据语义支持声明。必要证据覆盖与答案／引用支持评测留P2.6。
- 候选表格的review_required传递到引用；含该证据的结论状态为`review_required`。
- 模型表明无法由证据回答时使用`insufficient_evidence`；不得根据未查到的参数补写数值。
- API与日志不返回模型私有reasoning_content。

## API与配置

`POST /v1/qa/answer`输入沿用query、collection、filters，最多检索8块；返回`status`（answered／insufficient_evidence／citation_invalid／review_required）、`answer`、`citations`、`usage`与版本字段。

新增`configs/qa/v1.json`固定PaperQA2版本、prompt版本、最大证据数8、正文总预算18000字符、最大输出1536 tokens和90秒超时。生成模型名称、provider、API地址和key环境变量名称来自明确的运行配置；没有已配置服务时返回503，不默认使用开发工具的凭据。

首版每请求最多一次生成调用，关闭重试、自动fallback与summary调用。模型支持要求为文本生成及足够上下文；P2.5不要求其支持工具调用。密钥只能从指定环境变量／忽略的本机.env读取，不进入仓库或日志。

## 模块职责

- `ican/qa/schema.py`：问答请求、状态、引用和用量契约。
- `ican/qa/paperqa_adapter.py`：外部证据到上游对象及稳定引用注册表。
- `ican/qa/runtime.py`：运行配置、单次受控模型调用、timeout与凭据读取。
- `ican/qa/service.py`：固定流程、raw引用校验与响应映射。
- `ican/api/app.py`：新增问答路由，保留现有health与检索接口。
- `scripts/verify_paperqa2.py`：公开接口导入、无隐式embedding／检索、来源保真、固定样例的真实生成验收。

## 验收

1. 固定包及依赖安装后pip check通过，旧解析／分块／索引／检索测试不回归；P2.3索引身份和模型版本不变。
2. 使用真实PaperQA2包与fake LLM验证公开aquery流程被调用，证明并非只复制prompt或假装接入。
3. 覆盖原文保真、页／行／段落与版本、重复正文不同来源、ID碰撞、伪引用、无证据、候选表格标记、预算与超时。
4. 用实际检索与用户配置的真实生成服务运行至少论文和配置两类功能样例，保存模型／prompt／索引版本及调用用量。样例不读取冻结gold，不报告正式准确率。
5. 保存上游默认问答设置作为参考，与领域adapter配置对照；本节点只报告接口／功能差异，公平效果比较在P2.6固定语料与模型后进行。

## 当前前置条件

官方源码和依赖dry-run已核验，详见`docs/paperqa2-integration-investigation.md`。作品的生成服务及测试预算需要用户给定；本设计通过显式配置支持该选择，不替用户静默启用已有开发工具密钥。
