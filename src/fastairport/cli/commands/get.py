"""
Get command for retrieving data from a FastAirport server endpoint.
"""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing_extensions import Annotated
from typing import List, Optional, Dict, Any
import json
import pyarrow as pa
import polars as pl

from ...client import FlightClient
from ...cli import app
from ...cli._utils import (
    print_error,
    display_arrow_table_rich,
    print_warning,
    print_success,
)


def parse_cli_params(
    params_str: Optional[List[str]], console: Console
) -> Dict[str, Any]:
    """Parses 'key=value' strings into a dictionary, supports JSON for values."""
    if not params_str:
        return {}
    parsed = {}
    for p_str in params_str:
        if "=" not in p_str:
            print_error(
                f"Invalid parameter format: '{p_str}'. Must be 'key=value'.", console
            )
            raise typer.BadParameter(f"Invalid parameter format: '{p_str}'.")
        key, value_str = p_str.split("=", 1)
        try:
            # Try to parse as JSON first
            parsed[key] = json.loads(value_str)
        except json.JSONDecodeError:
            # If not JSON, try to convert to appropriate type
            if value_str.lower() in ("true", "false"):
                parsed[key] = value_str.lower() == "true"
            elif value_str.isdigit():
                parsed[key] = int(value_str)
            elif value_str.replace(".", "", 1).isdigit() and value_str.count(".") == 1:
                parsed[key] = float(value_str)
            else:
                parsed[key] = value_str
    return parsed


@app.command(name="get")
def get_data_cmd(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="Name of the endpoint to query.")],
    params: Annotated[
        List[str],
        typer.Option(
            "--param",
            "-p",
            help="Endpoint parameters in 'key=value' format. Value can be JSON. Repeat for multiple params.",
        ),
    ] = [],
    host: Annotated[str, typer.Option(help="Server host.")] = "localhost",
    port: Annotated[int, typer.Option(help="Server port.")] = 8815,
    stream: Annotated[
        bool, typer.Option(help="Stream data as Arrow RecordBatches.")
    ] = False,
    as_polars: Annotated[
        bool,
        typer.Option(
            help="If not streaming, request data as Polars DataFrame (client-side)."
        ),
    ] = False,
    max_rows: Annotated[
        int,
        typer.Option(help="Maximum rows to display for non-streaming table preview."),
    ] = 10,
):
    """
    📥 Retrieve data from a FastAirport server endpoint.
    Values for --param can be JSON strings, e.g., -p 'ids=[1,2,3]'
    """
    console: Console = ctx.meta["fastairport_console"]
    location = f"{host}:{port}"

    try:
        cli_params = parse_cli_params(params, console)
    except typer.BadParameter as e:
        print_error(str(e), console)
        raise typer.Exit(code=1)

    try:
        with FlightClient(location) as client:
            if stream:
                console.print(
                    f"Streaming data from endpoint [bold cyan]'{endpoint}'[/bold cyan] at [green]{location}[/green] with params: {cli_params}..."
                )
                total_records = 0
                batch_count = 0
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Streaming batch {batch_count + 1}", total=None
                    )
                    for i, batch in enumerate(client.stream_data(endpoint, cli_params)):
                        batch_count = i + 1
                        num_records = len(batch)
                        total_records += num_records
                        progress.update(
                            task,
                            description=f"Received batch {batch_count} ({num_records} records, total {total_records})",
                        )
                        if batch_count == 1:
                            console.print(f"Schema of first batch: {batch.schema}")
                    progress.update(
                        task,
                        completed=True,
                        description=f"Stream finished. Total {batch_count} batches, {total_records} records.",
                    )
            else:
                console.print(
                    f"Fetching data from endpoint [bold cyan]'{endpoint}'[/bold cyan] at [green]{location}[/green] with params: {cli_params}..."
                )
                data = client.get_data(endpoint, cli_params, as_polars=as_polars)
                if isinstance(data, pl.DataFrame):
                    from ...cli._utils import display_polars_df_rich

                    display_polars_df_rich(
                        data,
                        console,
                        title=f"Endpoint: {endpoint} (Polars)",
                        max_rows=max_rows,
                    )
                elif isinstance(data, pa.Table):
                    display_arrow_table_rich(
                        data,
                        console,
                        title=f"Endpoint: {endpoint} (Arrow)",
                        max_rows=max_rows,
                    )
                else:
                    print_warning(
                        f"Received unexpected data type: {type(data)}. Cannot display.",
                        console,
                    )
                print_success(f"Data received from '{endpoint}'.", console)
    except Exception as e:
        print_error(
            f"Could not get data from '{endpoint}' at '{location}': {e}", console
        )
        raise typer.Exit(code=1)
