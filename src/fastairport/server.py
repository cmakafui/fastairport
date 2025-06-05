import logging
from typing import Callable, Dict

import pyarrow as pa
import pyarrow.flight as flight

from .context import Context

logger = logging.getLogger(__name__)


class _Server(flight.FlightServerBase):
    def __init__(self, app: "FastAirport", host: str, port: int):
        self._app = app
        super().__init__((host, port))

    def do_exchange(self, context, descriptor, reader, writer):
        name = descriptor.command.decode()
        handler = self._app._endpoints.get(name)
        if handler is None:
            raise flight.FlightUnavailableError(f"Unknown endpoint: {name}")
        table = reader.read_all()
        ctx = Context(name)
        result = handler(table, ctx)
        writer.begin(result.schema)
        for batch in result.to_batches():
            writer.write_batch(batch)


class FastAirport:
    """Minimal wrapper around an Arrow Flight server."""

    def __init__(self, name: str):
        self.name = name
        self._endpoints: Dict[str, Callable[[pa.Table, Context], pa.Table]] = {}
        self._server: _Server | None = None

    def endpoint(self, name: str) -> Callable[[Callable[[pa.Table, Context], pa.Table]], Callable[[pa.Table, Context], pa.Table]]:
        def decorator(func: Callable[[pa.Table, Context], pa.Table]):
            self._endpoints[name] = func
            return func
        return decorator

    def start(self, host: str = "0.0.0.0", port: int = 8815) -> None:
        self._server = _Server(self, host, port)
        logger.info(f"{self.name} running on {host}:{port}")
        self._server.serve()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
