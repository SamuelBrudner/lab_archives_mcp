"""Lazy vector-search runtime dependencies for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vector_backend.config import VectorSearchConfig
    from vector_backend.embedding import EmbeddingClient
    from vector_backend.index import VectorIndex

    from ..settings import Settings


@dataclass(slots=True)
class VectorRuntime:
    """Create and cache vector-search dependencies on first use."""

    settings: Settings
    _config: VectorSearchConfig | None = field(default=None, init=False)
    _embedding_client: EmbeddingClient | None = field(default=None, init=False)
    _index: VectorIndex | None = field(default=None, init=False)
    _health_checked: bool = field(default=False, init=False)

    def get_config(self) -> VectorSearchConfig:
        """Return vector-search config, applying runtime secrets once."""
        if self._config is not None:
            return self._config

        # Keep vector imports lazy so non-search MCP startup has no vector backend side effects.
        from vector_backend.config import load_config

        config = load_config(
            self.settings.vector_config_name,
            config_path=self.settings.vector_config_path,
        )
        secrets = self.settings.secrets

        if not config.embedding.api_key and (openai_key := secrets.get("OPENAI_API_KEY")):
            config.embedding.api_key = str(openai_key)
        if not config.index.api_key and (pinecone_key := secrets.get("PINECONE_API_KEY")):
            config.index.api_key = str(pinecone_key)
        if not config.index.environment and (
            pinecone_environment := secrets.get("PINECONE_ENVIRONMENT")
        ):
            config.index.environment = str(pinecone_environment)

        self._config = config
        return config

    def get_embedding_client(self) -> EmbeddingClient:
        """Return the cached embedding client for the configured model."""
        if self._embedding_client is None:
            # Keep vector imports lazy so tests and non-search installs can monkeypatch cleanly.
            from vector_backend.embedding import create_embedding_client

            self._embedding_client = create_embedding_client(self.get_config().embedding)
        return self._embedding_client

    async def get_index(self) -> VectorIndex:
        """Return the cached vector index and health-check it on first use."""
        if self._index is None:
            self._index = self._create_index()

        if not self._health_checked:
            healthy = await self._index.health_check()
            if not healthy:
                raise RuntimeError(
                    "Vector index is not reachable. Check network, API key, or environment."
                )
            self._health_checked = True

        return self._index

    def _create_index(self) -> VectorIndex:
        config = self.get_config()
        if config.index.backend == "pinecone":
            # Keep vector imports lazy so non-search MCP startup does not initialize Pinecone.
            from vector_backend.index import PineconeIndex

            if not config.index.api_key:
                raise RuntimeError(
                    "PINECONE_API_KEY is required in the configured secrets or vector config."
                )
            return PineconeIndex(
                index_name=config.index.index_name,
                api_key=config.index.api_key,
                environment=config.index.environment or "us-east-1",
                namespace=config.index.namespace,
            )

        if config.index.backend == "qdrant":
            from vector_backend.index import QdrantIndex

            if not config.index.url:
                raise RuntimeError("Qdrant vector config requires index.url.")
            return QdrantIndex(
                collection_name=config.index.index_name,
                url=config.index.url,
                api_key=config.index.api_key,
            )

        raise ValueError(f"Unsupported vector index backend: {config.index.backend}")
