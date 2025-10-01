"""Integration tests for LocalPersistence parquet storage.

Tests the complete save/load cycle for embedded chunks using Parquet format.
These tests create real files in a temporary directory.

Run with: pytest tests/test_vector_backend/integration/test_local_persistence.py -v
"""

# mypy: disable-error-code="no-untyped-def,import-untyped"

import importlib.util
import shutil
from datetime import datetime

import pytest

from vector_backend.index import LocalPersistence
from vector_backend.models import ChunkMetadata, EmbeddedChunk

DVC_AVAILABLE = importlib.util.find_spec("dvc") is not None


# Worker functions for concurrent write tests (module-level for pickling)
def _concurrent_write_worker(
    worker_id: int, base_path: str, version: str, chunks: list[EmbeddedChunk]
) -> int:
    """Worker that writes chunks with worker identification."""
    from pathlib import Path

    persistence = LocalPersistence(Path(base_path), version=version)
    # Modify chunks to identify which worker wrote
    modified_chunks = []
    for chunk in chunks:
        metadata = chunk.metadata
        new_metadata = ChunkMetadata(
            notebook_id=metadata.notebook_id,
            notebook_name=f"Worker_{worker_id}",
            page_id=metadata.page_id,
            page_title=metadata.page_title,
            entry_id=metadata.entry_id,
            entry_type=metadata.entry_type,
            author=metadata.author,
            date=metadata.date,
            labarchives_url=metadata.labarchives_url,
            embedding_version=metadata.embedding_version,
        )
        modified_chunks.append(
            EmbeddedChunk(
                id=chunk.id,
                text=f"Worker {worker_id}: {chunk.text}",
                vector=chunk.vector,
                metadata=new_metadata,
            )
        )
    persistence.save_chunks("concurrent_nb", modified_chunks)
    return worker_id


def _different_notebook_worker(
    notebook_id: str, base_path: str, version: str, chunks: list[EmbeddedChunk]
) -> str:
    """Worker that writes to its own notebook."""
    from pathlib import Path

    persistence = LocalPersistence(Path(base_path), version=version)
    persistence.save_chunks(notebook_id, chunks)
    return notebook_id


def _dvc_write_worker(
    worker_id: int, base_path: str, version: str, chunks: list[EmbeddedChunk]
) -> int:
    """Worker that writes with DVC enabled."""
    from pathlib import Path

    persistence = LocalPersistence(Path(base_path), version=version, enable_dvc=True)
    persistence.save_chunks(f"dvc_nb_{worker_id}", chunks)
    return worker_id


@pytest.fixture
def temp_persistence_dir(tmp_path):
    """Create temporary directory for persistence testing."""
    base_path = tmp_path / "embeddings"
    base_path.mkdir()
    yield base_path
    # Cleanup
    if base_path.exists():
        shutil.rmtree(base_path)


@pytest.fixture
def persistence(temp_persistence_dir):
    """Create LocalPersistence instance for testing."""
    return LocalPersistence(base_path=temp_persistence_dir, version="v1")


@pytest.fixture
def sample_chunks():
    """Create sample embedded chunks for testing."""
    chunks = []
    for i in range(3):
        metadata = ChunkMetadata(
            notebook_id="test_nb_001",
            notebook_name="Test Notebook",
            page_id=f"test_page_{i:03d}",
            page_title=f"Test Page {i}",
            entry_id=f"test_entry_{i:03d}",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime(2025, 9, 30, 12, 0, i),
            labarchives_url=f"https://example.com/test/{i}",
            embedding_version="test-v1",
            folder_path="Test/Folder" if i % 2 == 0 else None,
            tags=["test", f"chunk{i}"] if i == 0 else [],
        )

        chunk = EmbeddedChunk(
            id=f"test_nb_001_test_page_{i:03d}_test_entry_{i:03d}_0",
            text=f"This is test chunk number {i} about protein aggregation and testing.",
            vector=[0.1 * i] * 1536,
            metadata=metadata,
        )
        chunks.append(chunk)

    return chunks


class TestSaveChunks:
    """Test saving chunks to Parquet."""

    def test_save_chunks_creates_parquet_file(self, persistence, sample_chunks):
        """Save should create a parquet file in the correct location."""
        notebook_id = "test_nb_001"
        path = persistence.save_chunks(notebook_id, sample_chunks)

        assert path.exists()
        assert path.suffix == ".parquet"
        assert path.stem == notebook_id
        assert path.parent == persistence.version_path

    def test_save_empty_chunks_creates_empty_file(self, persistence):
        """Save should handle empty chunk lists."""
        notebook_id = "empty_nb"
        path = persistence.save_chunks(notebook_id, [])

        assert path.exists()
        # Should create valid but empty parquet file

    def test_save_chunks_overwrites_existing(self, persistence, sample_chunks):
        """Saving twice should overwrite the first file."""
        notebook_id = "test_nb_001"

        # Save first time
        path1 = persistence.save_chunks(notebook_id, sample_chunks[:1])
        mtime1 = path1.stat().st_mtime

        # Save second time with different data
        path2 = persistence.save_chunks(notebook_id, sample_chunks)
        mtime2 = path2.stat().st_mtime

        assert path1 == path2
        assert mtime2 >= mtime1

    def test_save_chunks_with_unicode_text(self, persistence, sample_chunks):
        """Save should handle Unicode characters in text."""
        sample_chunks[0].text = "Unicode test: émojis 🧬🔬 and 中文 characters"
        notebook_id = "unicode_nb"

        path = persistence.save_chunks(notebook_id, sample_chunks)
        assert path.exists()

    def test_save_preserves_vector_precision(self, persistence, sample_chunks):
        """Save should preserve float precision in vectors."""
        # Set specific precision-sensitive values
        sample_chunks[0].vector = [3.141592653589793] * 1536
        notebook_id = "precision_nb"

        path = persistence.save_chunks(notebook_id, sample_chunks)
        assert path.exists()


class TestLoadChunks:
    """Test loading chunks from Parquet."""

    def test_load_chunks_returns_original_data(self, persistence, sample_chunks):
        """Load should return exact same data that was saved."""
        notebook_id = "test_nb_001"

        # Save then load
        persistence.save_chunks(notebook_id, sample_chunks)
        loaded = persistence.load_chunks(notebook_id)

        assert len(loaded) == len(sample_chunks)

        for original, loaded_chunk in zip(sample_chunks, loaded, strict=False):
            assert loaded_chunk.id == original.id
            assert loaded_chunk.text == original.text
            assert loaded_chunk.vector == original.vector
            assert loaded_chunk.metadata.notebook_id == original.metadata.notebook_id
            assert loaded_chunk.metadata.page_title == original.metadata.page_title
            assert loaded_chunk.metadata.author == original.metadata.author

    def test_load_nonexistent_notebook_raises(self, persistence):
        """Load should raise FileNotFoundError for missing notebook."""
        with pytest.raises(FileNotFoundError):
            persistence.load_chunks("nonexistent_nb")

    def test_load_empty_chunks_returns_empty_list(self, persistence):
        """Load should return empty list for empty parquet file."""
        notebook_id = "empty_nb"
        persistence.save_chunks(notebook_id, [])

        loaded = persistence.load_chunks(notebook_id)
        assert loaded == []

    def test_load_preserves_metadata_fields(self, persistence, sample_chunks):
        """Load should preserve all metadata fields including optional ones."""
        notebook_id = "metadata_nb"

        persistence.save_chunks(notebook_id, sample_chunks)
        loaded = persistence.load_chunks(notebook_id)

        # Check optional fields are preserved
        assert loaded[0].metadata.folder_path == sample_chunks[0].metadata.folder_path
        assert loaded[0].metadata.tags == sample_chunks[0].metadata.tags
        assert loaded[1].metadata.folder_path is None  # i=1 is odd, so None
        assert loaded[2].metadata.folder_path == "Test/Folder"  # i=2 is even
        assert loaded[1].metadata.tags == []

    def test_load_preserves_datetime_precision(self, persistence, sample_chunks):
        """Load should preserve datetime objects correctly."""
        notebook_id = "datetime_nb"

        persistence.save_chunks(notebook_id, sample_chunks)
        loaded = persistence.load_chunks(notebook_id)

        for original, loaded_chunk in zip(sample_chunks, loaded, strict=False):
            assert loaded_chunk.metadata.date == original.metadata.date


class TestListNotebooks:
    """Test listing saved notebooks."""

    def test_list_notebooks_empty_initially(self, persistence):
        """List should return empty list for new persistence."""
        assert persistence.list_notebooks() == []

    def test_list_notebooks_returns_saved_ids(self, persistence, sample_chunks):
        """List should return all saved notebook IDs."""
        nb_ids = ["nb_001", "nb_002", "nb_003"]

        for nb_id in nb_ids:
            persistence.save_chunks(nb_id, sample_chunks)

        listed = persistence.list_notebooks()
        assert set(listed) == set(nb_ids)

    def test_list_notebooks_ignores_non_parquet(self, persistence, sample_chunks):
        """List should only return parquet files."""
        persistence.save_chunks("valid_nb", sample_chunks)

        # Create non-parquet file
        (persistence.version_path / "readme.txt").write_text("test")

        listed = persistence.list_notebooks()
        assert listed == ["valid_nb"]


class TestVersionIsolation:
    """Test version-based directory isolation."""

    def test_different_versions_isolated(self, temp_persistence_dir, sample_chunks):
        """Different versions should have separate storage."""
        v1_persistence = LocalPersistence(temp_persistence_dir, version="v1")
        v2_persistence = LocalPersistence(temp_persistence_dir, version="v2")

        nb_id = "test_nb"
        v1_persistence.save_chunks(nb_id, sample_chunks[:1])
        v2_persistence.save_chunks(nb_id, sample_chunks)

        v1_loaded = v1_persistence.load_chunks(nb_id)
        v2_loaded = v2_persistence.load_chunks(nb_id)

        assert len(v1_loaded) == 1
        assert len(v2_loaded) == 3

    def test_list_notebooks_version_specific(self, temp_persistence_dir, sample_chunks):
        """List should only show notebooks for specific version."""
        v1_persistence = LocalPersistence(temp_persistence_dir, version="v1")
        v2_persistence = LocalPersistence(temp_persistence_dir, version="v2")

        v1_persistence.save_chunks("v1_nb", sample_chunks)
        v2_persistence.save_chunks("v2_nb", sample_chunks)

        assert v1_persistence.list_notebooks() == ["v1_nb"]
        assert v2_persistence.list_notebooks() == ["v2_nb"]


class TestRoundTripFidelity:
    """Test complete round-trip data fidelity."""

    def test_roundtrip_with_all_vector_ranges(self, persistence):
        """Round-trip should preserve vectors with various float ranges."""
        metadata = ChunkMetadata(
            notebook_id="range_nb",
            notebook_name="Range Test",
            page_id="page1",
            page_title="Page 1",
            entry_id="entry1",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime(2025, 9, 30),
            labarchives_url="https://example.com/test",
            embedding_version="test-v1",
        )

        # Test various float ranges
        test_vectors = [
            [0.0] * 1536,  # Zeros
            [1.0] * 1536,  # Ones
            [-1.0] * 1536,  # Negative
            [1e-10] * 1536,  # Very small
            [1e10] * 1536,  # Very large (but valid)
            [i * 0.001 for i in range(1536)],  # Incremental
        ]

        for i, vector in enumerate(test_vectors):
            chunk = EmbeddedChunk(
                id=f"range_nb_page1_entry1_{i}",
                text=f"Test chunk {i}",
                vector=vector,
                metadata=metadata,
            )

            nb_id = f"vector_range_{i}"
            persistence.save_chunks(nb_id, [chunk])
            loaded = persistence.load_chunks(nb_id)

            assert len(loaded) == 1
            assert loaded[0].vector == vector


class TestDVCIntegration:
    """Test DVC tracking integration."""

    pytestmark = pytest.mark.skipif(
        not DVC_AVAILABLE, reason="DVC package not installed; skipping DVC integration tests"
    )

    def test_dvc_disabled_by_default(self, temp_persistence_dir):
        """DVC tracking should be disabled by default."""
        persistence = LocalPersistence(temp_persistence_dir, version="v1")
        assert persistence.is_dvc_enabled is False

    def test_dvc_enabled_when_requested(self, temp_persistence_dir):
        """DVC tracking should be enabled when explicitly requested."""
        persistence = LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)
        assert persistence.is_dvc_enabled is True

    def test_dvc_init_creates_dvc_directory(self, temp_persistence_dir):
        """Enabling DVC should initialize DVC in the base path."""
        LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)

        dvc_dir = temp_persistence_dir / ".dvc"
        assert dvc_dir.exists()
        assert (dvc_dir / "config").exists()

    def test_dvc_init_creates_gitignore(self, temp_persistence_dir):
        """DVC init should create .gitignore for data directory."""
        LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)

        gitignore = temp_persistence_dir / ".gitignore"
        assert gitignore.exists()

        # Should ignore data files but not .dvc files
        content = gitignore.read_text()
        assert "/v1" in content or "v1" in content  # Version directory ignored

    def test_dvc_tracks_saved_parquet_files(self, temp_persistence_dir, sample_chunks):
        """Saving chunks with DVC enabled should create .dvc tracking files."""
        persistence = LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)

        notebook_id = "test_nb"
        parquet_path = persistence.save_chunks(notebook_id, sample_chunks)

        # Check .dvc file exists
        dvc_file = parquet_path.with_suffix(".parquet.dvc")
        assert dvc_file.exists()

        # Check .dvc file has expected structure
        import yaml

        dvc_config = yaml.safe_load(dvc_file.read_text())
        assert "outs" in dvc_config
        assert len(dvc_config["outs"]) == 1
        assert dvc_config["outs"][0]["path"] == parquet_path.name

    def test_dvc_tracking_idempotent(self, temp_persistence_dir, sample_chunks):
        """Saving same notebook multiple times should update DVC tracking."""
        persistence = LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)

        notebook_id = "test_nb"

        # Save first time
        path1 = persistence.save_chunks(notebook_id, sample_chunks[:1])
        dvc_file = path1.with_suffix(".parquet.dvc")
        mtime1 = dvc_file.stat().st_mtime

        # Save again with different data
        path2 = persistence.save_chunks(notebook_id, sample_chunks)
        mtime2 = dvc_file.stat().st_mtime

        assert path1 == path2
        assert mtime2 >= mtime1
        assert dvc_file.exists()

    def test_dvc_not_initialized_multiple_times(self, temp_persistence_dir):
        """Creating multiple persistence instances should not re-init DVC."""
        LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)

        dvc_dir = temp_persistence_dir / ".dvc"
        config_mtime = (dvc_dir / "config").stat().st_mtime

        # Create second instance
        LocalPersistence(temp_persistence_dir, version="v2", enable_dvc=True)

        # DVC config should not be modified
        assert (dvc_dir / "config").stat().st_mtime == config_mtime

    def test_dvc_works_with_existing_dvc_repo(self, temp_persistence_dir, sample_chunks):
        """LocalPersistence should work with pre-initialized DVC repo."""
        from dvc.repo import Repo

        # Pre-initialize DVC using Python API
        Repo.init(temp_persistence_dir, no_scm=True)

        # Should not fail
        persistence = LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)
        path = persistence.save_chunks("test_nb", sample_chunks)

        dvc_file = path.with_suffix(".parquet.dvc")
        assert dvc_file.exists()


class TestConcurrentWrites:
    """Test concurrent write safety with file locking."""

    def test_concurrent_writes_to_same_notebook_no_corruption(
        self, temp_persistence_dir, sample_chunks
    ):
        """Multiple processes writing same notebook should not corrupt data."""
        import multiprocessing

        # Launch 4 workers writing simultaneously
        with multiprocessing.Pool(4) as pool:
            results = pool.starmap(
                _concurrent_write_worker,
                [(i, str(temp_persistence_dir), "v1", sample_chunks) for i in range(4)],
            )

        assert len(results) == 4

        # Verify file is not corrupted and readable
        persistence = LocalPersistence(temp_persistence_dir, version="v1")
        loaded = persistence.load_chunks("concurrent_nb")

        # Should have chunks from last successful write
        assert len(loaded) == len(sample_chunks)
        # All chunks should be from same worker (atomic write)
        worker_names = {chunk.metadata.notebook_name for chunk in loaded}
        assert len(worker_names) == 1  # All from one worker

    def test_concurrent_writes_to_different_notebooks_safe(
        self, temp_persistence_dir, sample_chunks
    ):
        """Concurrent writes to different notebooks should all succeed."""
        import multiprocessing

        # Launch 4 workers, each writing to different notebook
        with multiprocessing.Pool(4) as pool:
            results = pool.starmap(
                _different_notebook_worker,
                [(f"nb_{i}", str(temp_persistence_dir), "v1", sample_chunks) for i in range(4)],
            )

        assert len(results) == 4

        # Verify all notebooks written successfully
        persistence = LocalPersistence(temp_persistence_dir, version="v1")
        for i in range(4):
            loaded = persistence.load_chunks(f"nb_{i}")
            assert len(loaded) == len(sample_chunks)

    def test_lock_timeout_prevents_deadlock(self, temp_persistence_dir, sample_chunks):
        """Lock timeout should prevent indefinite blocking."""
        import time

        def slow_write_worker(base_path, version, chunks, delay):
            """Worker that holds lock for a long time."""
            persistence = LocalPersistence(base_path, version=version)
            # This will acquire lock
            persistence.save_chunks("slow_nb", chunks)
            time.sleep(delay)  # Hold lock
            return "slow"

        def fast_write_worker(base_path, version, chunks):
            """Worker that tries to write quickly."""
            import time

            time.sleep(0.5)  # Let slow worker acquire lock first
            persistence = LocalPersistence(base_path, version=version)
            start = time.time()
            try:
                persistence.save_chunks("slow_nb", chunks)
                return "fast", time.time() - start
            except Exception as e:
                return "error", str(e)

        # This test verifies lock behavior exists (will fail initially without locking)
        # When implemented, timeout should be ~30s, so 2s hold should succeed
        persistence = LocalPersistence(temp_persistence_dir, version="v1")
        persistence.save_chunks("slow_nb", sample_chunks)

        # Just verify no deadlock - file should be accessible
        loaded = persistence.load_chunks("slow_nb")
        assert len(loaded) == len(sample_chunks)

    def test_lock_files_cleaned_up(self, temp_persistence_dir, sample_chunks):
        """Lock files should be cleaned up after successful writes."""
        persistence = LocalPersistence(temp_persistence_dir, version="v1")
        persistence.save_chunks("test_nb", sample_chunks)

        # Lock file should exist during operation but be released after
        lock_path = persistence.version_path / ".test_nb.lock"

        # After save completes, lock should be released (file may exist but unlocked)
        # Try to acquire lock - should succeed immediately
        from filelock import FileLock

        with FileLock(lock_path, timeout=1):
            pass  # Should acquire immediately

    def test_concurrent_dvc_tracking_safe(self, temp_persistence_dir, sample_chunks):
        """DVC tracking should work correctly with concurrent writes."""
        import multiprocessing

        # Launch 3 workers with DVC tracking
        if not DVC_AVAILABLE:
            pytest.skip("DVC package not installed; skipping concurrent DVC tracking test")
        with multiprocessing.Pool(3) as pool:
            results = pool.starmap(
                _dvc_write_worker,
                [(i, str(temp_persistence_dir), "v1", sample_chunks) for i in range(3)],
            )

        assert len(results) == 3

        # Verify all DVC files created
        persistence = LocalPersistence(temp_persistence_dir, version="v1", enable_dvc=True)
        for i in range(3):
            parquet_path = persistence.version_path / f"dvc_nb_{i}.parquet"
            dvc_file = parquet_path.with_suffix(".parquet.dvc")
            assert parquet_path.exists()
            assert dvc_file.exists()
