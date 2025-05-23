"""
CLI utility functions for FastAirport.
"""

from rich.console import Console
from rich.table import Table
from typing import Optional, List, Dict
import pyarrow as pa
import polars as pl
import json


def print_success(message: str, console: Console):
    console.print(f"[green]✔ {message}[/green]")


def print_error(message: str, console: Console):
    console.print(f"[red]✖ {message}[/red]")


def print_warning(message: str, console: Console):
    console.print(f"[yellow]! {message}[/yellow]")


def display_list_of_dicts_as_table(
    data: List[Dict],
    console: Console,
    title: Optional[str] = None,
    max_rows: int = 10,
):
    """
    Display a list of dictionaries as a rich table.

    Args:
        data: List of dictionaries to display
        console: Rich console instance
        title: Optional title for the table
        max_rows: Maximum number of rows to display
    """
    if not data:
        console.print("[yellow]No data to display.[/yellow]")
        return

    table = Table(
        title=title if title else "Data",
        show_lines=True,
        highlight=True,
    )

    # Get all unique keys from all dictionaries
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())

    # Add columns for each key
    for key in sorted(all_keys):
        table.add_column(str(key), style="cyan")

    # Add rows
    for item in data[:max_rows]:
        row_values = [str(item.get(key, "N/A")) for key in sorted(all_keys)]
        table.add_row(*row_values)

    # Add caption if we're not showing all rows
    if len(data) > max_rows:
        table.caption = f"Showing {max_rows} of {len(data)} rows."

    console.print(table)


def display_arrow_table_rich(
    table_data: pa.Table,
    console: Console,
    title: Optional[str] = None,
    max_rows: int = 10,
):
    if table_data.num_rows == 0:
        console.print(
            f"[yellow]Empty table returned for '{title if title else 'data'}'.[/yellow]"
        )
        console.print(f"Schema: {table_data.schema}")
        return
    try:
        polars_df = pl.from_arrow(table_data)
        display_polars_df_rich(
            polars_df, console, title, max_rows, original_schema=table_data.schema
        )
    except Exception as e:
        console.print(
            f"[red]Error converting Arrow Table to Polars for display: {e}[/red]"
        )
        console.print(f"Schema: {table_data.schema}")
        console.print(
            f"First few rows (raw Arrow): {table_data.slice(0, min(max_rows, table_data.num_rows))}"
        )


def display_polars_df_rich(
    df: pl.DataFrame,
    console: Console,
    title: Optional[str] = None,
    max_rows: int = 10,
    original_schema: Optional[pa.Schema] = None,
):
    if df.is_empty():
        console.print(
            f"[yellow]Empty Polars DataFrame returned for '{title if title else 'data'}'.[/yellow]"
        )
        if original_schema:
            console.print(f"Original Arrow Schema: {original_schema}")
        elif df.schema:
            console.print(f"Polars Schema: {df.schema}")
        return
    table = Table(
        title=title if title else "Polars DataFrame Data",
        show_lines=True,
        highlight=True,
    )
    for col_name in df.columns:
        is_numeric = df[col_name].dtype in [
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
            pl.Float32,
            pl.Float64,
        ]
        table.add_column(
            col_name, style="cyan", justify="right" if is_numeric else "left"
        )
    num_to_display = min(df.height, max_rows)
    for i in range(num_to_display):
        row_values = [str(df[col_name][i]) for col_name in df.columns]
        table.add_row(*row_values)
    caption_parts = []
    if df.height > max_rows:
        caption_parts.append(f"Showing {max_rows} of {df.height} rows.")
    if original_schema:
        caption_parts.append(f"Arrow Schema: {original_schema}")
    else:
        caption_parts.append(f"Polars Schema: {df.schema}")
    table.caption = " ".join(caption_parts)
    console.print(table)


def display_json_Syntax(data, console: Console, title: Optional[str] = None):
    """Display JSON data with syntax highlighting."""
    from rich.syntax import Syntax

    json_str = json.dumps(data, indent=2, default=str)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)

    if title:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print(syntax)
