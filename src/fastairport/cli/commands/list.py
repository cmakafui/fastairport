"""
List command for retrieving information about FastAirport server endpoints and actions.
"""

import typer
from rich.console import Console
from typing_extensions import Annotated

from ...client import FlightClient
from ...cli import app
from ...cli._utils import (
    print_error,
    print_warning,
    display_list_of_dicts_as_table,
    print_success,
)


@app.command(name="endpoints")
def list_endpoints_cmd(
    ctx: typer.Context,
    host: Annotated[
        str, typer.Option("--host", "-H", help="Server host address.")
    ] = "localhost",
    port: Annotated[
        int, typer.Option("--port", "-P", help="Server port number.", min=1, max=65535)
    ] = 8815,
):
    """
    Lists all available data endpoints on the server.
    """
    console: Console = ctx.meta["fastairport_console"]
    location = f"{host}:{port}"
    try:
        with FlightClient(location) as client:
            console.print(f"Fetching endpoints from [cyan]{location}[/cyan]...")
            endpoints_data = client.list_endpoints()
            if not endpoints_data:
                print_warning("No endpoints found on the server.", console)
                return

            # Prepare data for Rich table, be robust to missing keys
            table_rows = []
            for ep in endpoints_data:
                schema_info = "N/A"
                if ep.get("schema"):
                    try:
                        schema_info = f"{len(ep['schema'].names)} fields"
                    except Exception:
                        schema_info = str(ep["schema"])
                table_rows.append(
                    {
                        "Name": ep.get("name", "Unknown"),
                        "Records": ep.get("total_records", "N/A"),
                        "Bytes": ep.get("total_bytes", "N/A"),
                        "Schema": schema_info,
                        "Ordered": str(ep.get("ordered", "N/A")),
                    }
                )
            display_list_of_dicts_as_table(
                table_rows, console, title="Available Endpoints"
            )
            print_success(f"Found {len(endpoints_data)} endpoint(s).", console)

    except Exception as e:
        print_error(
            f"Could not connect or list endpoints from '{location}': {e}", console
        )
        raise typer.Exit(code=1)


@app.command(name="actions")
def list_actions_cmd(
    ctx: typer.Context,
    host: Annotated[
        str, typer.Option("--host", "-H", help="Server host address.")
    ] = "localhost",
    port: Annotated[
        int, typer.Option("--port", "-P", help="Server port number.", min=1, max=65535)
    ] = 8815,
):
    """
    Lists all available actions (RPC calls) on the server.
    """
    console: Console = ctx.meta["fastairport_console"]
    location = f"{host}:{port}"
    try:
        with FlightClient(location) as client:
            console.print(f"Fetching actions from [cyan]{location}[/cyan]...")
            actions_data = client.list_actions()
            if not actions_data:
                print_warning("No actions found on the server.", console)
                return

            table_rows = [
                {
                    "Name": ac.get("name", "Unknown"),
                    "Description": ac.get("description", "N/A"),
                }
                for ac in actions_data
            ]
            display_list_of_dicts_as_table(
                table_rows, console, title="Available Actions"
            )
            print_success(f"Found {len(actions_data)} action(s).", console)

    except Exception as e:
        print_error(
            f"Could not connect or list actions from '{location}': {e}", console
        )
        raise typer.Exit(code=1)
