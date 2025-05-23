"""
FastAirport CLI - Command line interface for FastAirport servers.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="fastairport",
    help="FastAirport CLI - The fast, Pythonic way to build Arrow Flight servers",
    add_completion=False,
)

console = Console()


def print_banner():
    """Print the FastAirport banner."""
    banner = Text()
    banner.append("FastAirport", style="bold blue")
    banner.append(
        " - The fast, Pythonic way to build Arrow Flight servers\n", style="italic"
    )
    banner.append("Version: ", style="bold")
    banner.append("0.3.0", style="green")

    panel = Panel(banner, border_style="blue")
    console.print(panel)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """FastAirport CLI - The fast, Pythonic way to build Arrow Flight servers."""
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print(
            "\nUse [bold blue]fastairport --help[/] to see available commands."
        )
