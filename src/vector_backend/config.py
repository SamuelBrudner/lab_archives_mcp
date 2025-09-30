"""Configuration management for vector backend using Hydra.

All configuration is loaded from YAML files in conf/vector_search/.
This module provides typed config objects and validation.
"""

from pathlib import Path

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig, OmegaConf
from pydantic import BaseModel, Field

from vector_backend.chunking import ChunkingConfig
from vector_backend.embedding import EmbeddingConfig


class VectorSearchConfig(BaseModel):
    """Top-level configuration for vector search system.

    Attributes:
        chunking: Text chunking configuration
        embedding: Embedding model configuration
        index: Vector index configuration
        incremental_updates: Incremental update configuration
    """

    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    index: "IndexConfig"
    incremental_updates: "IncrementalUpdateConfig"


class IndexConfig(BaseModel):
    """Vector index configuration.

    Attributes:
        backend: Index backend ("pinecone" or "qdrant")
        index_name: Name of the index/collection
        namespace: Optional namespace for multi-tenancy
        api_key: API key for hosted service
        environment: Environment name (for Pinecone)
        url: URL for self-hosted Qdrant
    """

    backend: str = Field(pattern="^(pinecone|qdrant)$")
    index_name: str
    namespace: str | None = None
    api_key: str | None = None
    environment: str | None = None  # Pinecone
    url: str | None = None  # Qdrant


class IncrementalUpdateConfig(BaseModel):
    """Configuration for incremental index updates.

    Attributes:
        enabled: Whether incremental updates are enabled
        schedule: Cron schedule string (e.g., "0 2 * * *")
        batch_size: Number of chunks to process per batch
        last_indexed_file: Path to file storing last indexed timestamp
    """

    enabled: bool = True
    schedule: str = "0 2 * * *"
    batch_size: int = Field(default=200, ge=1, le=1000)
    last_indexed_file: str = "data/.last_indexed"


def load_config(
    config_name: str = "default",
    config_path: str | Path | None = None,
    overrides: list[str] | None = None,
) -> VectorSearchConfig:
    """Load vector search configuration from Hydra YAML files.

    Args:
        config_name: Name of config file (without .yaml extension)
        config_path: Path to config directory (defaults to conf/vector_search/)
        overrides: List of config overrides (e.g., ["embedding.version=v2"])

    Returns:
        Validated configuration object

    Example:
        >>> config = load_config("default")
        >>> config.embedding.model
        'openai/text-embedding-3-small'

        >>> config = load_config("default", overrides=["embedding.version=v2"])
        >>> config.embedding.version
        'v2'
    """
    if config_path is None:
        # Default to conf/vector_search/ relative to repo root
        repo_root = Path(__file__).parent.parent.parent
        config_path = repo_root / "conf" / "vector_search"

    config_path = Path(config_path).resolve()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config directory not found: {config_path}\n" f"Create it with: mkdir -p {config_path}"
        )

    # Initialize Hydra with config directory
    with initialize_config_dir(
        config_dir=str(config_path), version_base=None, job_name="vector_search"
    ):
        cfg: DictConfig = compose(config_name=config_name, overrides=overrides or [])

    # Convert OmegaConf to dict and validate with Pydantic
    config_dict = OmegaConf.to_container(cfg, resolve=True)
    return VectorSearchConfig(**config_dict)  # type: ignore


def create_default_config() -> dict[str, dict[str, object]]:
    """Create a default configuration dictionary for bootstrapping.

    Returns:
        Dictionary suitable for writing to YAML

    Example:
        >>> import yaml
        >>> config = create_default_config()
        >>> with open("conf/vector_search/default.yaml", "w") as f:
        ...     yaml.dump(config, f)
    """
    return {
        "chunking": {
            "chunk_size": 400,
            "overlap": 50,
            "tokenizer": "cl100k_base",
            "preserve_boundaries": True,
        },
        "embedding": {
            "model": "openai/text-embedding-3-small",
            "version": "v1",
            "dimensions": 1536,
            "batch_size": 100,
            "max_retries": 3,
            "timeout_seconds": 30.0,
            "api_key": "${oc.env:OPENAI_API_KEY}",
        },
        "index": {
            "backend": "pinecone",
            "index_name": "labarchives-semantic-search",
            "namespace": None,
            "api_key": "${oc.env:PINECONE_API_KEY}",
            "environment": "${oc.env:PINECONE_ENVIRONMENT,us-east-1}",
            "url": None,
        },
        "incremental_updates": {
            "enabled": True,
            "schedule": "0 2 * * *",
            "batch_size": 200,
            "last_indexed_file": "data/.last_indexed",
        },
    }
