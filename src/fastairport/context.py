import logging
import time


class Context:
    """Simple request context."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._start = time.time()
        self._logger = logging.getLogger(f"fastairport.{endpoint}")

    def info(self, msg: str) -> None:
        self._log(self._logger.info, msg)

    def warning(self, msg: str) -> None:
        self._log(self._logger.warning, msg)

    def error(self, msg: str) -> None:
        self._log(self._logger.error, msg)

    def _log(self, func, msg: str) -> None:
        elapsed = time.time() - self._start
        func(f"[{elapsed:.3f}s] {msg}")
