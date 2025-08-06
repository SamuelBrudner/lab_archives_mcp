# Bug: `labarchives-mcp` Console Script Fails to Import Package

## Summary
Running `labarchives-mcp --version` from a fresh install fails with:

```
ModuleNotFoundError: No module named 'labarchives_mcp'
```

The generated console-script points to a non-existent package path.

## Steps to Reproduce
1. Create and activate the conda env (see `environment.yml`).
2. Install the package:
   ```bash
   pip install --no-cache-dir ./src/cli
   ```
3. Run the CLI:
   ```bash
   labarchives-mcp --version
   ```

## Expected Behaviour
CLI prints version (e.g., `labarchives-mcp 0.1.0`) and exits with code 0.

## Actual Behaviour
Process exits with a traceback ending in `ModuleNotFoundError: No module named 'labarchives_mcp'`.

## Root Cause
`src/cli/pyproject.toml` registers the console script as:

```toml
[project.scripts]
labarchives-mcp = "labarchives_mcp.cli:main"
```

But the codebase does **not** contain a `labarchives_mcp/` package. All modules (`main.py`, `cli_parser.py`, etc.) live at project root.

## Suggested Fix
Update the script entry to point at the real module (e.g., `main:main` or `cli_entry:main`) and adjust the package discovery sections accordingly.

```toml
[project.scripts]
labarchives-mcp = "main:main"

[tool.setuptools.packages.find]
where = ["."]
```

After fixing, reinstall the package and re-run the CLI to verify.

## Severity
🚨 **High** – prevents any invocation of the CLI after installation.
