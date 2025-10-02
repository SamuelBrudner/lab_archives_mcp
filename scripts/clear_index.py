#!/usr/bin/env python
"""Clear all vectors from the Pinecone index."""

import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml  # type: ignore[import-untyped]
from pinecone import Pinecone


def main() -> None:
    """Clear the index."""
    # Load secrets
    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with open(secrets_path) as f:
        loaded = yaml.safe_load(f)
    secrets: dict[str, Any] = cast(dict[str, Any], loaded or {})

    # Connect to Pinecone
    pc = Pinecone(api_key=secrets["PINECONE_API_KEY"])
    index = pc.Index("labarchives-test")

    # Get stats before
    stats = index.describe_index_stats()
    print(f"Current chunks: {stats.total_vector_count}")

    # Delete all vectors in the default namespace
    index.delete(delete_all=True, namespace="")
    print("✓ Index cleared")

    # Verify
    stats = index.describe_index_stats()
    print(f"After clearing: {stats.total_vector_count}")


if __name__ == "__main__":
    main()
