"""Minimal CLI exposing only the `serve` command."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import typer

from .. import __version__, FastAirport

app = typer.Typer(help="FastAirport command line interface")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"FastAirport {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(None, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"),
):
    """FastAirport command line interface."""
    pass


def _load_airport_from_file(path: Path) -> FastAirport:
    """Load a `FastAirport` instance from a Python file."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    for value in vars(module).values():
        if isinstance(value, FastAirport):
            return value
    raise AttributeError("No FastAirport instance found in file")


@app.command()
def serve(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8815, "--port", "-p"),
):
    """Run a FastAirport server from the given Python file."""
    try:
        airport = _load_airport_from_file(file)
    except Exception as exc:
        typer.echo(f"Error loading '{file}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Starting {airport.name} on {host}:{port}")
    try:
        airport.start(host=host, port=port)
    except KeyboardInterrupt:
        typer.echo("Server stopped by user.")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
