"""Set up Pinecone index for vector backend testing.

This script creates the test index with correct configuration.

Usage:
    python scripts/setup_pinecone.py

Populate `conf/secrets.yml` with your Pinecone credentials. The script falls back to
environment variables only if the secrets file is missing or does not contain a key.
"""

import os
import sys
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


def main() -> None:
    """Create Pinecone test index."""
    api_key = os.environ.get("PINECONE_API_KEY")

    if not api_key:
        secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
        try:
            with secrets_path.open() as fh:
                loaded = yaml.safe_load(fh)
            secrets: dict[str, Any] = cast(dict[str, Any], loaded or {})
        except FileNotFoundError:
            secrets = {}

        api_key = secrets.get("PINECONE_API_KEY", "")
        if secrets.get("PINECONE_ENVIRONMENT"):
            os.environ.setdefault("PINECONE_ENVIRONMENT", secrets["PINECONE_ENVIRONMENT"])

    if not api_key:
        print(
            "❌ Error: Pinecone credentials not found. Populate conf/secrets.yml "
            "or export PINECONE_API_KEY."
        )
        sys.exit(1)

    try:
        from pinecone import Pinecone, ServerlessSpec

        print("🔧 Setting up Pinecone...\n")

        # Initialize Pinecone
        pc = Pinecone(api_key=api_key)

        # Configuration
        index_name = "labarchives-test"
        dimension = 1536  # text-embedding-3-small dimension
        metric = "cosine"

        # Check if index already exists
        existing_indexes = pc.list_indexes()
        index_names = [idx["name"] for idx in existing_indexes]

        if index_name in index_names:
            print(f"✅ Index '{index_name}' already exists!")

            # Get index info
            index = pc.Index(index_name)
            stats = index.describe_index_stats()

            print("\nIndex Statistics:")
            print(f"  • Total vectors: {stats.total_vector_count}")
            print(f"  • Dimension: {stats.dimension if hasattr(stats, 'dimension') else 'N/A'}")

        else:
            print(f"📝 Creating index '{index_name}'...")
            print(f"  • Dimension: {dimension}")
            print(f"  • Metric: {metric}")
            print("  • Spec: Serverless (us-east-1)")

            # Create index
            pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

            print(f"✅ Index '{index_name}' created successfully!")

        print("\n🎉 Pinecone setup complete!")
        print("\nYou can now run:")
        print("  pytest tests/test_vector_backend/integration/ -v -m integration")
        print("  python scripts/test_e2e_workflow.py")

    except ImportError:
        print("❌ Error: pinecone package not installed")
        print("\nInstall it with:")
        print("  pip install 'pinecone>=4.1'")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  • Check your API key is correct")
        print("  • Ensure you have a free index slot available")
        print("  • Visit https://app.pinecone.io/ to check your account")
        sys.exit(1)


if __name__ == "__main__":
    main()
