"""
Command Line Interface for Cognitive Runtime.

This module provides the primary entrypoint for managing and running
the cognitive architecture.
"""

from typing import Annotated

import typer

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.logging.logger import get_logger

app = typer.Typer(
    name="cognitive-runtime",
    help="Cognitive Runtime Management CLI",
    add_completion=False,
)

logger = get_logger(__name__)


@app.command()
def run(
    env_file: Annotated[
        str | None,
        typer.Option("--env-file", "-e", help="Path to .env configuration file"),
    ] = None,
) -> None:
    """
    Start the cognitive runtime.

    Initializes logging, configuration, storage, and keeps the
    runtime alive until manually stopped.
    """
    typer.echo("Initializing Cognitive Runtime...")

    brain = None
    try:
        # Initialize runtime
        brain = startup(env_file=env_file)

        # (Future) Here would be the main event loop
        typer.echo("Cognitive Runtime is running. Press Ctrl+C to stop.")

        # Simulate keeping the process alive (for the skeleton, we just block)
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
        # Graceful shutdown
        if brain:
            shutdown(brain)


if __name__ == "__main__":
    app()
