"""
Command Line Interface for Cognitive Runtime.

This module provides the primary entrypoint for managing and running
the cognitive architecture.
"""

import threading
from typing import Annotated

import typer
import uvicorn

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.logging.logger import get_logger

app = typer.Typer(
    name="cognitive-runtime",
    help="Cognitive Runtime Management CLI",
    add_completion=False,
)

logger = get_logger(__name__)

API_HOST = "127.0.0.1"
API_PORT = 8000


def _start_api_server() -> None:
    """Runs the FastAPI server in a daemon thread."""
    from cognitive_runtime.api.server import app as api_app

    uvicorn.run(
        api_app,
        host=API_HOST,
        port=API_PORT,
        log_level="warning",  # Suppress uvicorn access logs — structlog handles runtime logs
    )


@app.command()
def run(
    env_file: Annotated[
        str | None,
        typer.Option("--env-file", "-e", help="Path to .env configuration file"),
    ] = None,
    api_port: Annotated[
        int,
        typer.Option("--api-port", help="Port for the runtime API server"),
    ] = API_PORT,
) -> None:
    """
    Start the cognitive runtime.

    Initializes logging, configuration, storage, and keeps the
    runtime alive until manually stopped. The runtime API server
    starts on port 8000 (configurable via --api-port).
    """
    typer.echo("Initializing Cognitive Runtime...")

    brain = None
    try:
        # Initialize runtime — this populates the API context
        brain = startup(env_file=env_file)

        # Start the API server in a background daemon thread
        # (daemon=True ensures it exits when the main thread exits)
        api_thread = threading.Thread(
            target=_start_api_server,
            daemon=True,
            name="rage-api-server",
        )
        api_thread.start()
        typer.echo(
            f"Runtime API listening on http://{API_HOST}:{api_port}/api"
        )
        typer.echo("Cognitive Runtime is running. Press Ctrl+C to stop.")

        # Keep alive
        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user. Shutting down...")
    except Exception as e:
        logger.exception("cognitive_runtime.cli.error", error=str(e))
        typer.echo(f"Fatal error: {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        if brain:
            shutdown(brain)


if __name__ == "__main__":
    app()
