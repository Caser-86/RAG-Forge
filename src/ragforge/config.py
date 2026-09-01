"""配置管理：所有配置集中于此，支持 .env / 环境变量覆盖。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 向量库: in_memory | qdrant | pgvector
    vector_store: str = "in_memory"
    qdrant_url: str = "http://localhost:6333"
    pg_dsn: str = "postgresql://user:pass@localhost:5432/rag"

    # 嵌入
    embedder_backend: str = "local"  # local | api
    embedder_model: str = "BAAI/bge-m3"
    embedder_dim: int = 1024
    embedder_api_key: str = ""

    # 生成 LLM（OpenAI 兼容）
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # 检索
    top_k: int = 4
    dense_weight: float = 1.0
    sparse_top_k: int = 15
    rerank_top_k: int = 4
    rerank_model: str = "BAAI/bge-reranker-base"
    use_rerank: bool = True
    min_evidence_score: float = 0.15

    # 分块
    chunk_size: int = 800
    chunk_overlap: int = 100

    # 拒答阈值：证据不足时拒答而非硬编
    refuse_threshold: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()