"""Pytest configuration for test discovery and fixtures."""

import sys
from pathlib import Path

# Ensure src directory is in path for imports
repo_root = Path(__file__).parent.parent
src_path = repo_root / "src"

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
