"""
Context class for FastAirport server-side operations.
"""

import logging
import time
from typing import Any, Optional, Dict
import pyarrow.flight as flight

logger = logging.getLogger(__name__)


class Context:
    """Context object passed to endpoint and action handlers."""

    def __init__(self, call_context: Optional[flight.ServerCallContext], server: Any):
        self._call_context = call_context
        self._server = server
        self._request_data: Dict[str, Any] = {}
        self._start_time = time.time()

    @property
    def peer(self) -> Optional[str]:
        """Get the peer address if available."""
        if self._call_context:
            return self._call_context.peer()
        return None

    def set_request_data(self, key: str, value: Any) -> None:
        """Store request-scoped data."""
        self._request_data[key] = value

    def get_request_data(self, key: str, default: Any = None) -> Any:
        """Retrieve request-scoped data."""
        return self._request_data.get(key, default)

    def info(self, message: str) -> None:
        """Log an info message with context."""
        self._log("INFO", message)

    def warning(self, message: str) -> None:
        """Log a warning message with context."""
        self._log("WARNING", message)

    def error(self, message: str) -> None:
        """Log an error message with context."""
        self._log("ERROR", message)

    def debug(self, message: str) -> None:
        """Log a debug message with context."""
        self._log("DEBUG", message)

    def _log(self, level: str, message: str) -> None:
        """Internal logging method with consistent formatting."""
        peer_info = f" from {self.peer}" if self.peer else ""
        elapsed = f"[{time.time() - self._start_time:.3f}s]"
        formatted_msg = f"[{self._server.name}]{peer_info} {elapsed}: {message}"

        getattr(logger, level.lower())(formatted_msg)

    def report_progress(self, message: str) -> None:
        """Report progress."""
        self.info(f"Progress: {message}")

    def is_cancelled(self) -> bool:
        """Check if the current call has been cancelled."""
        if self._call_context:
            return self._call_context.is_cancelled()
        return False

    def check_cancelled(self) -> None:
        """Raise an exception if the call has been cancelled."""
        if self.is_cancelled():
            from .errors import Cancelled

            raise Cancelled("Request was cancelled by client")

    def get_server_name(self) -> str:
        """Get the server name."""
        return self._server.name

    def get_endpoint_names(self) -> list:
        """Get the list of registered endpoint names."""
        return list(self._server._endpoints.keys())
