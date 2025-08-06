"""
LabArchives MCP Server CLI package.
Avoid heavy imports during package initialization to prevent circular dependencies.
"""

__version__ = "0.1.0"
__author__ = "LabArchives MCP Team"
__email__ = "team@labarchives.com"

import importlib
import types
from typing import TYPE_CHECKING

# --------------------------------------------------------------------------- #
# Ensure fully-qualified import path `src.cli.*` works regardless of whether  #
# project root is on PYTHONPATH.  When tests are executed from inside         #
# `src/cli` the parent `src` package may not yet exist in sys.modules, which  #
# breaks statements like `from src.cli import cli_parser`.  We create a       #
# lightweight stub module named `src` and register the current package under #
# `src.cli` so that both `import cli_parser` *and* `import src.cli.cli_parser`#
# resolve to the same objects.                                               #
# --------------------------------------------------------------------------- #
import sys as _sys, types as _types

if "src" not in _sys.modules:
    _src_pkg = _types.ModuleType("src")
    _sys.modules["src"] = _src_pkg

# Map the current package to the qualified name `src.cli`
_sys.modules.setdefault("src.cli", _sys.modules[__name__])

__all__ = ["main", "__version__"]

_deferrals = {
    "main": "src.cli.main",
}

if TYPE_CHECKING:
    # During static type checking import directly
    from src.cli.main import main  # noqa: F401


# --------------------------------------------------------------------------- #
# Backwards-compatibility import aliases                                       #
#                                                                             #
# Historically, many modules inside the CLI package were imported using their #
# bare names (e.g. ``import config``).  When executing the package directly   #
# these names resolve because ``src/cli`` is first on ``sys.path``; however   #
# unit-tests and external tooling often import via the fully-qualified        #
# ``src.cli.*`` path which means those bare names are missing from            #
# ``sys.modules``.  To keep the public import surface stable while we migrate #
# code to explicit qualified imports, we inject compatibility aliases that    #
# map the bare name to the correct fully-qualified module object.             #
# --------------------------------------------------------------------------- #

import sys

_COMPAT_MODULES = [
    "config",
    "constants",
    "exceptions",
    "validators",
    "auth_manager",
    "cli_parser",
    "logging_setup",
    "mcp_server",
    "resource_manager",
    "utils",
]

for _name in _COMPAT_MODULES:
    # Only alias if the short name hasn't already been imported elsewhere.
    if _name not in sys.modules:
        try:
            _mod = importlib.import_module(f"src.cli.{_name}")
            sys.modules[_name] = _mod
        except ModuleNotFoundError:
            # Silently ignore missing optional modules to avoid import-time failures.
            pass


def __getattr__(name: str) -> types.ModuleType:
    if name in _deferrals:
        module = importlib.import_module(_deferrals[name])
        globals()[name] = module
        return module
    raise AttributeError(name)
