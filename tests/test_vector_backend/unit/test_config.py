"""Unit tests for configuration loading.

Tests cover:
- Hydra config loading from YAML
- Environment variable interpolation
- Config validation
- Override mechanism
"""

import os

import pytest

from vector_backend.config import (
    IncrementalUpdateConfig,
    IndexConfig,
    VectorSearchConfig,
    create_default_config,
    load_config,
)


class TestConfigCreation:
    """Tests for default config creation."""

    def test_create_default_config(self) -> None:
        """Default config should have sensible values."""
        config_dict = create_default_config()

        assert config_dict["chunking"]["chunk_size"] == 400
        assert config_dict["chunking"]["overlap"] == 50
        assert config_dict["embedding"]["model"] == "openai/text-embedding-3-small"
        assert config_dict["index"]["backend"] == "pinecone"

    def test_default_config_has_all_sections(self) -> None:
        """Default config should have all required sections."""
        config_dict = create_default_config()

        required_sections = ["chunking", "embedding", "index", "incremental_updates"]
        assert all(section in config_dict for section in required_sections)


class TestConfigModels:
    """Tests for config model validation."""

    def test_index_config_valid_backend(self) -> None:
        """Index config should validate backend."""
        # Valid backends
        IndexConfig(backend="pinecone", index_name="test")
        IndexConfig(backend="qdrant", index_name="test")

        # Invalid backend should raise
        with pytest.raises(ValueError):
            IndexConfig(backend="invalid", index_name="test")

    def test_incremental_update_config_batch_size(self) -> None:
        """Batch size must be within valid range."""
        # Valid batch size
        IncrementalUpdateConfig(batch_size=200)

        # Too small
        with pytest.raises(ValueError):
            IncrementalUpdateConfig(batch_size=0)

        # Too large
        with pytest.raises(ValueError):
            IncrementalUpdateConfig(batch_size=2000)


class TestConfigLoading:
    """Tests for loading config from Hydra YAML."""

    def test_load_default_config(self) -> None:
        """Should load default config from YAML."""
        config = load_config("default")

        assert isinstance(config, VectorSearchConfig)
        assert config.chunking.chunk_size == 400
        assert config.embedding.model == "openai/text-embedding-3-small"

    def test_load_config_with_overrides(self) -> None:
        """Should apply overrides to config."""
        config = load_config(
            "default",
            overrides=[
                "chunking.chunk_size=500",
                "embedding.version=v2",
            ],
        )

        assert config.chunking.chunk_size == 500
        assert config.embedding.version == "v2"

    def test_load_config_env_var_interpolation(self) -> None:
        """Should interpolate environment variables."""
        # Set test env vars
        os.environ["TEST_OPENAI_KEY"] = "test-key-123"

        try:
            config = load_config(
                "default",
                overrides=["embedding.api_key=${oc.env:TEST_OPENAI_KEY}"],
            )

            assert config.embedding.api_key == "test-key-123"
        finally:
            del os.environ["TEST_OPENAI_KEY"]

    def test_load_config_missing_file_raises(self) -> None:
        """Should raise if config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent", config_path="/nonexistent/path")

    def test_load_config_validates_structure(self) -> None:
        """Config should be validated by Pydantic."""
        # This should work - valid config
        config = load_config("default")

        # Verify Pydantic validation kicked in
        assert isinstance(config.chunking.chunk_size, int)
        assert isinstance(config.embedding.dimensions, int)
        assert config.embedding.dimensions >= 128  # Pydantic validator
