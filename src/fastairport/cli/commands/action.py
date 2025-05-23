"""
Action command for calling FastAirport server actions.
"""

import typer
from rich.console import Console
from typing_extensions import Annotated
from typing import List

from ...client import FlightClient
from ...cli import app
from ...cli._utils import print_error, display_json_Syntax, print_success
from .get import parse_cli_params


@app.command(name="call")
def call_action_cmd(
    ctx: typer.Context,
    action_name: Annotated[str, typer.Argument(help="Name of the action to call.")],
    params: Annotated[
        List[str],
        typer.Option(
            "--param",
            "-p",
            help="Action parameter as 'key=value'. Value can be a JSON string. Repeat for multiple.",
        ),
    ] = [],
    host: Annotated[
        str, typer.Option("--host", "-H", help="Server host.")
    ] = "localhost",
    port: Annotated[int, typer.Option("--port", "-P", help="Server port.")] = 8815,
):
    """
    Calls a specified action on the server with given parameters.

    Parameters are passed as 'key=value'. For complex values, use JSON strings:
    e.g., `fastairport action call my_action -p user_id=10 -p 'details={"name":"Test","active":true}'`
    """
    console: Console = ctx.meta["fastairport_console"]
    location = f"{host}:{port}"

    try:
        cli_params = parse_cli_params(params, console)
    except typer.BadParameter:
        raise typer.Exit(code=1)

    try:
        with FlightClient(location) as client:
            console.print(
                f"Calling action [bold cyan]'{action_name}'[/bold cyan] at [green]{location}[/green] with params: [dim]{cli_params if cli_params else 'None'}[/dim]..."
            )
            result = client.call_action(action_name, cli_params)

            print_success(f"Action '{action_name}' called successfully.", console)
            display_json_Syntax(result, console, title="Action Response")

    except Exception as e:
        print_error(
            f"Could not call action '{action_name}' at '{location}': {e}", console
        )
        raise typer.Exit(code=1)
