"""配置管理：所有配置集中于此，支持 .env / 环境变量覆盖。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 向量库: qdrant_local | qdrant_server | in_memory；qdrant 保留为 server 别名
    vector_store: Literal["qdrant_local", "qdrant_server", "in_memory", "qdrant"] = "qdrant_local"
    qdrant_url: str = "http://localhost:6333"
    qdrant_path: Path = Path("data/qdrant")
    qdrant_collection: str = "rag_forge_local_v1"
    index_manifest_path: Path = Path("data/index_manifest.json")

    # 公开知识库采集与增量更新
    knowledge_manifest_path: Path = Path("data/knowledge_manifest.sqlite3")
    collector_config: Path = Path("configs/sources.yaml")
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")

    # 嵌入
    embedder_backend: Literal["ollama", "local", "api", "deterministic"] = "ollama"
    embedder_model: str = "bge-m3"
    embedder_dim: int = Field(default=1024, gt=0)
    embedder_batch_size: int = Field(default=16, gt=0)
    # Optional provider revision/digest. Set this when a provider exposes a
    # mutable tag (for example an Ollama model digest) so same-name changes
    # cannot silently reuse an old index.
    embedder_digest: str = ""
    embedder_api_key: str = ""

    # 生成 LLM（OpenAI 兼容）
    generation_backend: Literal["ollama", "api", "offline"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    default_generation_model: str = "gemma3:4b"
    allowed_generation_models: list[str] = Field(
        default_factory=lambda: ["gemma3:4b", "gemma4:e4b"]
    )
    ollama_connect_timeout: float = Field(default=5.0, gt=0)
    ollama_generate_timeout: float = Field(default=180.0, gt=0)
    # Optional Ollama generation controls. ``None`` preserves Ollama defaults
    # for normal application requests; benchmark profiles set these explicitly.
    generation_temperature: float | None = Field(default=None, ge=0, le=2)
    generation_num_predict: int | None = Field(default=None, gt=0)
    generation_seed: int | None = None
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # Qdrant 远程实例可选认证；本地 Compose 默认留空。
    qdrant_api_key: str = ""

    # 检索
    retrieval_mode: Literal["dense", "hybrid", "hybrid_rerank"] = "hybrid"
    dense_top_k: int = Field(default=20, gt=0)
    top_k: int = Field(default=5, gt=0)
    sparse_top_k: int = Field(default=20, ge=0)
    rerank_candidate_k: int = Field(default=40, gt=0)
    rerank_top_k: int = Field(default=5, gt=0)
    rerank_model: str = "BAAI/bge-reranker-base"
    use_rerank: bool = False

    # 分块
    chunk_strategy: Literal["heading_chars", "char"] = "heading_chars"
    chunk_size: int = Field(default=2200, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)

    # API 摄入允许访问的根目录；请求路径必须位于此目录内。
    ingest_root: Path = Path("data/raw/docs")
    max_ingest_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    ingest_total_bytes: int = Field(default=32 * 1024 * 1024, gt=0)
    max_request_body_bytes: int = Field(default=128 * 1024, gt=0)
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"]
    )
    api_key: str = ""
    rate_limit_per_minute: int = Field(default=60, gt=0)

    # 拒答阈值：证据不足时拒答而非硬编
    refuse_threshold: float = Field(default=0.15, ge=0, le=1)
    context_max_chars: int = Field(default=12000, gt=0)
    trace_max_entries: int = Field(default=100, gt=0)
    trace_ttl_seconds: int = Field(default=3600, gt=0)
    trace_max_item_chars: int = Field(default=4000, gt=0)

    # 可选查询改写：默认关闭，只生成检索查询，不生成答案。
    rewrite_enabled: bool = False
    rewrite_model: str = "qwen3:0.6b"
    rewrite_max_chars: int = Field(default=1000, gt=0)
    rewrite_history_max_messages: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.default_generation_model not in self.allowed_generation_models:
            raise ValueError("default_generation_model must be in allowed_generation_models")
        if (
            self.generation_backend == "api"
            and self.llm_model not in self.allowed_generation_models
        ):
            raise ValueError("llm_model must be in allowed_generation_models for api backend")
        return self

    @field_validator("allowed_generation_models")
    @classmethod
    def validate_generation_models(cls, models: list[str]) -> list[str]:
        if not models or any(not model.strip() for model in models):
            raise ValueError("allowed_generation_models must contain non-empty names")
        if any(model.strip().startswith("bge-m3") for model in models):
            raise ValueError("embedding model bge-m3 cannot be a generation model")
        return models

    @field_validator("allowed_hosts")
    @classmethod
    def validate_allowed_hosts(cls, hosts: list[str]) -> list[str]:
        if not hosts or any(not host.strip() for host in hosts):
            raise ValueError("allowed_hosts must contain non-empty host names")
        return [host.strip().lower() for host in hosts]


@lru_cache
def get_settings() -> Settings:
    return Settings()
