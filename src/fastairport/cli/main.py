"""
FastAirport CLI main module.
"""

import typer
from rich.console import Console
from .. import __version__
from .commands import list, action, ping
from .commands.serve import serve_cmd
from .commands.get import get_data_cmd

app = typer.Typer(
    name="fastairport",
    help="FastAirport CLI - The fast, Pythonic way to build Arrow Flight servers",
)


def version_callback(value: bool):
    if value:
        typer.echo(f"FastAirport CLI Version {__version__}")
        raise typer.Exit()


# Add context with console for rich output
@app.callback()
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    ctx.meta["fastairport_console"] = Console()


# Register serve command directly to root
app.command("serve")(serve_cmd)

# Register get commands directly to root
app.command("get")(get_data_cmd)

# Register other commands with proper descriptions
app.add_typer(
    list.app, name="list", help="List available endpoints and actions on the server"
)
app.add_typer(
    action.app, name="action", help="Call server actions and manage server operations"
)
app.add_typer(ping.app, name="ping", help="Check server health and connectivity")


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
