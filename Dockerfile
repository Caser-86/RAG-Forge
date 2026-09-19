FROM python:3.11-slim

WORKDIR /app

# 依赖按 Python 3.11 的锁文件安装；项目本身随后以 wheel 方式安装，避免
# editable 安装把源码目录和构建工具带入运行层。
COPY pyproject.toml README.md ./
COPY requirements/docker-py311-piptools.txt /tmp/requirements.txt

# 锁文件不含 index-url；两个源分别承载常规包和 CPU torch wheel。
RUN pip install --no-cache-dir --retries 5 \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cpu/ \
    -r /tmp/requirements.txt

COPY src ./src
COPY scripts ./scripts
RUN python -m pip wheel --no-deps --no-cache-dir --wheel-dir /tmp/wheels . \
    && python -m pip install --no-cache-dir --no-deps /tmp/wheels/rag_forge-*.whl \
    && rm -rf /tmp/wheels /tmp/requirements.txt

# 运行时不使用 root；/app/data 是唯一需要写入的持久化目录。
RUN groupadd --system ragforge \
    && useradd --system --gid ragforge --home-dir /app --shell /usr/sbin/nologin ragforge \
    && mkdir -p /app/data \
    && chown -R ragforge:ragforge /app
USER ragforge

# 模型由 docker-compose 挂载宿主机缓存（见 RAG_EMBEDDER_MODEL / RAG_RERANK_MODEL），
# 避免在镜像内重复下载 bge-m3 / bge-reranker（约 3.4GB）。
EXPOSE 8000
CMD ["uvicorn", "ragforge.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
