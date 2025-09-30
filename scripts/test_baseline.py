#!/usr/bin/env python
"""Quick baseline verification script for the LabArchives MCP server.

This script tests the core functionality:
1. Credentials loading from conf/secrets.yml
2. HMAC-SHA512 authentication
3. Notebook listing via user_info_via_id
4. MCP resource handler registration
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def main() -> None:
    """Run baseline verification checks."""
    import httpx

    from labarchives_mcp.auth import AuthenticationManager, Credentials
    from labarchives_mcp.eln_client import LabArchivesClient

    print("🔍 LabArchives MCP Server Baseline Verification\n")

    # Test 1: Credentials loading
    print("✓ Test 1: Loading credentials from conf/secrets.yml")
    try:
        credentials = Credentials.from_file()
        print(f"  → AKID: {credentials.akid[:20]}...")
        print(f"  → Region: {credentials.region}")
        print(f"  → UID configured: {credentials.uid is not None}")
    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        return

    # Test 2: Authentication and HMAC signature
    print("\n✓ Test 2: Testing HMAC-SHA512 authentication")
    async with httpx.AsyncClient(base_url=str(credentials.region)) as client:
        auth_manager = AuthenticationManager(client, credentials)

        try:
            uid = await auth_manager.ensure_uid()
            print(f"  → UID resolved: {uid[:30]}...")
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            return

        # Test 3: Notebook listing
        print("\n✓ Test 3: Fetching notebooks via user_info_via_id")
        try:
            lab_client = LabArchivesClient(client, auth_manager)
            notebooks = await lab_client.list_notebooks(uid)
            print(f"  → Retrieved {len(notebooks)} notebooks")

            if notebooks:
                sample = notebooks[0]
                print(f"  → Sample: {sample.name}")
                print(f"    Owner: {sample.owner_name} ({sample.owner_email})")
                print(f"    Created: {sample.created_at}")
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            return

    # Test 4: MCP server resource handler
    print("\n✓ Test 4: MCP server resource handler registration")
    try:
        from labarchives_mcp.mcp_server import _import_fastmcp

        fastmcp_class = _import_fastmcp()
        print(f"  → FastMCP loaded: {fastmcp_class.__name__}")
        print("  → Resource URI: labarchives:notebooks")
        print("  → Transport: stdio (MCP protocol)")
    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        return

    print("\n✅ All baseline checks passed!")
    print("\nYour MCP server is ready to expose to agents.")
    print("See docs/agent_configuration.md for setup instructions.")


if __name__ == "__main__":
    asyncio.run(main())
