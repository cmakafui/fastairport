"""
Serve command for running FastAirport servers.
"""

import typer
import sys
from pathlib import Path
from rich.console import Console

from ...server import FastAirport
from ...cli._utils import print_error, print_success


def _load_server_from_file(file_path_str: str, console: Console) -> FastAirport:
    """Loads a FastAirport instance from a Python file."""
    file_path = Path(file_path_str).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Server file not found or is not a file: {file_path}")

    # Temporarily add the file's directory to sys.path to handle relative imports
    original_sys_path = list(sys.path)
    module_dir = str(file_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    import importlib.util

    module_name = file_path.stem

    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not create module spec from file: {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        print_error(f"Error importing server file '{file_path}': {e}", console)
        raise
    finally:
        sys.path = original_sys_path

    # Search for a FastAirport instance in the loaded module
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(module, attr_name)
        if isinstance(attr, FastAirport):
            return attr

    raise AttributeError(
        f"No FastAirport server instance found in {file_path}. "
        "Ensure you have a line like `airport = FastAirport(...)` at the global scope."
    )


def serve_cmd(
    ctx: typer.Context,
    file: Path = typer.Argument(
        ...,
        help="Python file containing the FastAirport server instance (e.g., `my_server.py`).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    host: str = typer.Option(
        "0.0.0.0", "--host", "-h", help="Host to bind the server to."
    ),
    port: int = typer.Option(
        8815, "--port", "-p", help="Port to bind the server to.", min=1, max=65535
    ),
):
    """
    🚀 Runs a FastAirport server from the specified Python file.

    Example:
    `fastairport serve examples/my_server.py --port 8000`
    """
    console: Console = ctx.meta["fastairport_console"]
    airport_instance: FastAirport = None

    try:
        console.print(f"Attempting to load server from: [cyan]{file}[/cyan]")
        airport_instance = _load_server_from_file(str(file), console)
        console.rule(
            f"[bold magenta]Starting Server: '{airport_instance.name}'[/bold magenta]"
        )
        console.print(f"  [dim]Host:[/dim] [bold yellow]{host}[/bold yellow]")
        console.print(f"  [dim]Port:[/dim] [bold yellow]{port}[/bold yellow]")

        if airport_instance._endpoints:
            console.print("\n  [bold u]Endpoints:[/bold u]")
            for ep_name in airport_instance._endpoints.keys():
                console.print(f"    - [green]{ep_name}[/green]")
        else:
            console.print("\n  [yellow]No endpoints registered.[/yellow]")

        if airport_instance._actions:
            console.print("\n  [bold u]Actions:[/bold u]")
            for ac_name in airport_instance._actions.keys():
                console.print(f"    - [blue]{ac_name}[/blue]")
        else:
            console.print("\n  [yellow]No actions registered.[/yellow]")

        console.line()
        console.print("[italic dim]Press Ctrl+C to shut down the server.[/italic dim]")

        airport_instance.start(host=host, port=port, blocking=True)

    except FileNotFoundError:
        print_error(f"Server file not found: {file}", console)
        raise typer.Exit(code=1)
    except (ImportError, AttributeError, Exception) as e:
        if not isinstance(e, (ImportError, AttributeError)):
            print_error(f"Failed to load or start server from '{file}': {e}", console)
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print(
            "\n[bold yellow]Server shutdown initiated by user (Ctrl+C).[/bold yellow]"
        )
    finally:
        if (
            airport_instance
            and hasattr(airport_instance, "shutdown")
            and not airport_instance._shutdown_event.is_set()
        ):
            console.print("[dim]Ensuring server is shut down...[/dim]")
            airport_instance.shutdown(timeout=2.0)
            print_success("Server shut down.", console)
        elif airport_instance and airport_instance._shutdown_event.is_set():
            print_success("Server already shut down.", console)
