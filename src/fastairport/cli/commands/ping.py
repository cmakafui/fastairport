"""
Ping command for checking FastAirport server reachability.
"""

import typer
from rich.console import Console
from typing_extensions import Annotated

from ...client import FlightClient
from ...cli import app
from ...cli._utils import print_error, print_success, print_warning


@app.command(name="server")
def ping_server_cmd(
    ctx: typer.Context,
    host: Annotated[
        str, typer.Option("--host", "-H", help="Server host.")
    ] = "localhost",
    port: Annotated[int, typer.Option("--port", "-P", help="Server port.")] = 8815,
    timeout: Annotated[
        float, typer.Option(help="Connection timeout in seconds.")
    ] = 5.0,
):
    """
    Pings a FastAirport server to check if it's reachable and responding.
    """
    console: Console = ctx.meta["fastairport_console"]
    location = f"{host}:{port}"

    console.print(f"Pinging server at [cyan]{location}[/cyan] (timeout: {timeout}s)...")
    try:
        with FlightClient(location) as client:
            if client.ping():
                print_success(
                    f"Server at '{location}' is reachable and responding.", console
                )
            else:
                print_warning(
                    f"Server at '{location}' connected, but ping (list_actions) failed. "
                    "Server might be unhealthy or not a FastAirport server.",
                    console,
                )
                raise typer.Exit(code=1)
    except Exception as e:
        print_error(
            f"Could not connect to or ping server at '{location}': {e}", console
        )
        raise typer.Exit(code=1)
