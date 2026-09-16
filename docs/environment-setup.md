# ICAN 开发环境

## 环境信息

- Conda 环境名：`ican`
- 环境路径：`D:\CondaEnv\ican`
- Python：3.11.16
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU（8 GB）
- PyTorch：2.11.0+cu128
- TorchVision：0.26.0+cu128
- Jupyter 内核：`Python (ican)`

## 创建与安装

```powershell
conda create -n ican python=3.11 pip setuptools wheel -y
conda run -n ican python -m pip install -r requirements/torch-cu128.txt
conda run -n ican python -m pip install -r requirements/ican.txt
```

`requirements/ican.txt` 保存直接依赖和必要的兼容性约束；`requirements/ican-lock.txt` 保存 2026-09-15 验证通过的完整版本快照。严格复现时，在安装 CUDA 版 PyTorch 后将第三条命令替换为：

```powershell
conda run -n ican python -m pip install -r requirements/ican-lock.txt
```

## 激活

```powershell
conda activate ican
```

在 VS Code 或 Jupyter 中选择 `Python (ican)` 内核。

若当前 PowerShell 尚未执行过 Conda 初始化，可直接使用：

```powershell
conda run -n ican python <script.py>
```

## 依赖分组

- FastAPI、Pydantic、SQLAlchemy：后端 API、任务和 SQLite。
- LangGraph、LangChain：Agent 状态图与工具编排。
- Qdrant Client、Sentence Transformers、BM25：混合检索和重排序。
- PyMuPDF、pypdf、pdfplumber、tree-sitter：论文和代码解析。
- Transformers、timm、PyTorch：视觉模型与 embedding/reranker。
- Ragas、pytest：RAG 指标和工程测试。

## 已验证功能

```powershell
conda run -n ican python -m pip check
conda run -n ican python scripts/smoke_environment.py
```

2026-09-15 的结果：

- `pip check`：无损坏或冲突依赖。
- PyTorch 可识别 RTX 5060，并完成 CUDA 矩阵运算。
- PyMuPDF 成功读取 Swin Transformer 论文的 14 页内容。
- Qdrant 内存模式完成建库、写入和 Top-1 查询。
- BM25、LangGraph 状态图和 FastAPI TestClient 正常运行。
- 微软官方 Swin-T 实现严格加载官方权重，并在 CUDA 上得到 `(1, 1000)` 输出。

## 兼容性约束

- Ragas 0.4.3 仍导入 `langchain_community.chat_models.vertexai`，该模块已从 `langchain-community` 0.4 移除，因此固定 `langchain-community==0.3.31`。
- Instructor 1.17 与 OpenAI SDK 3.x 对 `jiter` 的版本范围冲突，因此固定 OpenAI SDK 2.x，并使用兼容的 `langchain-openai==1.1.9`。
- 这些约束已经通过导入测试、`pip check` 和完整冒烟测试；升级其中任一包时需重新执行全部检查。

## 范围说明

- Qdrant 首版可以使用 Python Client 的本地持久化模式；需要网页 Dashboard 或服务部署时再启动 Docker 服务。
- `mamba-ssm` 和 SAM 3 的运行/训练依赖暂不放入基础环境。当前 MambaVision 固定 `mamba-ssm==2.2.4` 与 `transformers==4.50.0`，而 SAM 3 声明 `numpy<2`；它们与当前 RAG 基础栈的版本和 Windows CUDA 扩展条件不同，将在对应动态复现实验开始前使用独立环境安装和锁定。
- 评测 JSONL 和带答案的评测文档不得加入 RAG 索引。
