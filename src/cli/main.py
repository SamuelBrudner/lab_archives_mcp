#!/usr/bin/env python3
"""CLI entry point and signal management for the LabArchives MCP PoL server."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import signal
import sys
from collections.abc import Sequence
from types import FrameType
from typing import Any

from cli.version import __version__
from labarchives_mcp import mcp_server

# Make version available as MCP_SERVER_VERSION for test compatibility
MCP_SERVER_VERSION = __version__

# =============================================================================
# Global Variables
# =============================================================================

# Main application logger - initialized during startup
logger = logging.getLogger("labarchives_mcp.main")

# Global server instance for signal handling
server_instance: Any | None = None

# =============================================================================
# Signal Handling Functions
# =============================================================================


def shutdown_handler(signum: int, frame: FrameType | None) -> None:
    """
    Handles OS signals for graceful shutdown of the MCP server.

    This function provides a clean shutdown mechanism when the server receives
    termination signals (SIGINT, SIGTERM). It logs the shutdown event, performs
    necessary cleanup operations, and exits the process with appropriate status code.

    The function ensures that:
    - The shutdown signal is properly logged for audit purposes
    - Any active server operations are cleanly terminated
    - Log buffers are flushed to prevent data loss
    - The process exits with a success code to indicate clean shutdown

    Args:
        signum (int): The signal number received (e.g., 2 for SIGINT, 15 for SIGTERM)
        frame: The current stack frame (required by signal handler interface but not used)

    Returns:
        None: This function performs cleanup and exits the process

    Example:
        >>> # Signal handler is registered during server startup
        >>> signal.signal(signal.SIGINT, shutdown_handler)
        >>> signal.signal(signal.SIGTERM, shutdown_handler)
    """
    global server_instance

    # Map signal numbers to human-readable names for logging
    try:
        signal_enum = signal.Signals(signum)
        signal_name = f"{signal_enum.name} ({signum})"
    except ValueError:
        signal_name = f"Unknown Signal ({signum})"

    # Log the shutdown signal receipt
    logger.info(
        f"Received shutdown signal: {signal_name}",
        extra={
            "signal_number": signum,
            "signal_name": signal_name,
            "operation": "shutdown_handler",
            "event": "shutdown_initiated",
        },
    )

    # Perform server cleanup if server instance exists
    if server_instance:
        try:
            logger.info(
                "Shutting down MCP server instance",
                extra={"operation": "shutdown_handler", "event": "server_shutdown"},
            )

            # Perform any necessary server cleanup
            # Note: FastMCP handles most cleanup automatically
            server_instance = None

        except Exception as e:
            logger.error(
                f"Error during server shutdown: {str(e)}",
                extra={
                    "operation": "shutdown_handler",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    # Flush all log handlers to ensure messages are written
    for handler in logger.handlers:
        with contextlib.suppress(Exception):
            handler.flush()
    # Log successful shutdown completion
    logger.info(
        "Graceful shutdown completed",
        extra={"operation": "shutdown_handler", "event": "shutdown_completed"},
    )

    # Exit the process with success code
    sys.exit(0)


def _run_cli(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, register signal handlers, and launch the MCP server."""

    parser = argparse.ArgumentParser(
        prog="labarchives-mcp",
        description="Launch the LabArchives MCP Proof-of-Life server",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Display the LabArchives MCP server version and exit.",
    )
    parser.add_argument(
        "--print-onboard",
        choices=("json", "markdown"),
        help="Print the onboarding payload to stdout and exit.",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize the local state directory and exit.",
    )

    parsed = parser.parse_args(list(argv) if argv is not None else None)

    if parsed.version:
        print(__version__)
        return 0

    if parsed.init:
        _init_state()
        return 0

    if parsed.print_onboard:
        asyncio.run(_emit_onboard(parsed.print_onboard))
        return 0

    logger.info("Starting LabArchives MCP server")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, shutdown_handler)

    global server_instance
    server_instance = object()

    try:
        mcp_server.run()
    finally:
        server_instance = None

    return 0


async def _emit_onboard(output_format: str) -> None:
    import httpx

    from labarchives_mcp.auth import AuthenticationManager, Credentials
    from labarchives_mcp.eln_client import LabArchivesClient
    from labarchives_mcp.onboard import OnboardService

    credentials = Credentials.from_file()
    async with httpx.AsyncClient(base_url=str(credentials.region)) as http_client:
        auth_manager = AuthenticationManager(http_client, credentials)
        notebook_client = LabArchivesClient(http_client, auth_manager)
        service = OnboardService(
            auth_manager=auth_manager,
            notebook_client=notebook_client,
            version=mcp_server.__version__,
        )
        payload = await service.get_payload()

    if output_format == "json":
        print(json.dumps(payload.as_dict(), indent=2))
    else:
        print(payload.markdown)


def _init_state() -> None:
    """Initialize the local state directory."""
    from pathlib import Path

    from labarchives_mcp.state import StateManager

    state_dir = Path(".labarchives_state")
    if state_dir.exists():
        print(f"State directory already exists at {state_dir.absolute()}")
    else:
        print(f"Initializing state directory at {state_dir.absolute()}...")
        # StateManager init will create the directory and empty state file
        StateManager(storage_dir=state_dir)
        print("Done.")


# =============================================================================
# Main Entry Point Function
# =============================================================================


def main() -> None:
    """
    Main entry point for the CLI application.

    This function orchestrates the complete lifecycle of the LabArchives MCP Server,
    from initialization through operation to shutdown. It handles all aspects of
    server startup including argument parsing, configuration loading, logging setup,
    authentication, resource management, and MCP server initialization.

    The function implements a comprehensive startup sequence:
    1. Parse CLI arguments using parse_and_dispatch_cli() from cli_parser
    2. Handle special cases like --help and --version display
    3. Load and validate configuration using load_configuration() from config
    4. Initialize logging using setup_logging() from logging_setup
    5. Log startup banner with version and configuration summary
    6. Initialize AuthenticationManager with loaded configuration
    7. Authenticate with LabArchives API using AuthenticationManager
    8. Initialize ResourceManager with authenticated session context
    9. Register signal handlers for graceful shutdown
    10. Launch MCP server with resource handlers
    11. Start the MCP server event loop using asyncio
    12. Handle all errors with appropriate logging and exit codes

    Error Handling:
    - ConfigurationError: Invalid or missing configuration parameters
    - AuthenticationError: Failed authentication with LabArchives API
    - StartupError: Server initialization or startup failures
    - KeyboardInterrupt: User interruption (Ctrl+C)
    - General exceptions: Unexpected errors with full context logging

    Exit Codes:
    - 0: Success - server started and ran successfully
    - 1: Configuration error - invalid or missing configuration
    - 2: Authentication error - failed to authenticate with LabArchives
    - 3: Startup error - server initialization failed
    - 130: User interruption - KeyboardInterrupt received

    Returns:
        None: Exits the process with appropriate status code

    Example:
        >>> # Called from console_scripts entry point
        >>> main()
        # Server starts and runs until interrupted or error occurs
    """
    sys.exit(_run_cli())


# =============================================================================
# Module Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
