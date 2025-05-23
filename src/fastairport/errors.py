"""
Custom error classes and validation helpers for FastAirport.
"""

import pyarrow.flight as flight
from typing import Any, Union


class FastAirportError(Exception):
    """Base class for all FastAirport errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_flight_error(self) -> flight.FlightError:
        """Convert to appropriate Arrow Flight error."""
        return flight.FlightInternalError(self.message)


class InvalidArgument(FastAirportError):
    """Raised when an invalid argument is provided."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightInternalError(self.message)


class NotFound(FastAirportError):
    """Raised when a requested resource is not found."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightNotFoundError(self.message)


class Unauthorized(FastAirportError):
    """Raised when authentication is required or failed."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightUnauthenticatedError(self.message)


class Forbidden(FastAirportError):
    """Raised when access to a resource is forbidden."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightUnauthorizedError(self.message)


class InternalError(FastAirportError):
    """Raised when an internal error occurs."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightInternalError(self.message)


class Unavailable(FastAirportError):
    """Raised when a service is unavailable."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightUnavailableError(self.message)


class TimedOut(FastAirportError):
    """Raised when an operation times out."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightTimedOutError(self.message)


class Cancelled(FastAirportError):
    """Raised when an operation is cancelled."""

    def to_flight_error(self) -> flight.FlightError:
        return flight.FlightCancelledError(self.message)


# Validation helper functions
def require_param(name: str, value: Any) -> None:
    """Require that a parameter is not None."""
    if value is None:
        raise InvalidArgument(f"Parameter '{name}' is required")


def require_positive(name: str, value: Union[int, float]) -> None:
    """Require that a numeric parameter is positive."""
    if value <= 0:
        raise InvalidArgument(f"Parameter '{name}' must be positive")


def require_non_empty(name: str, value: Any) -> None:
    """Require that a parameter is not empty (for strings, lists, etc)."""
    if not value:
        raise InvalidArgument(f"Parameter '{name}' cannot be empty")


def require_one_of(name: str, value: Any, allowed_values: list) -> None:
    """Require that a parameter is one of the allowed values."""
    if value not in allowed_values:
        raise InvalidArgument(f"Parameter '{name}' must be one of {allowed_values}")
