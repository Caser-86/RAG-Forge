FROM python:3.11-slim

WORKDIR /app

# 先拷贝依赖清单与源码，利用构建缓存（改代码不触发重装依赖）
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts

# CPU 版 torch 单独一层：走上海交大 pytorch-wheels 国内镜像（官方 R2 CDN 国内不稳定）
RUN pip install --no-cache-dir --retries 5 torch --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cpu/

# 项目依赖走国内 PyPI 镜像，加速且稳定（sentence-transformers / qdrant-client 等）
RUN pip install --no-cache-dir --retries 5 -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[local,vector]"

# 模型由 docker-compose 挂载宿主机缓存（见 RAG_EMBEDDER_MODEL / RAG_RERANK_MODEL），
# 避免在镜像内重复下载 bge-m3 / bge-reranker（约 3.4GB）。
EXPOSE 8000
CMD ["uvicorn", "ragforge.api.main:app", "--host", "0.0.0.0", "--port", "8000"]