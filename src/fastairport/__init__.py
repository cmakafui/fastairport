"""
FastAirport: The fast, Pythonic way to build Arrow Flight servers
with Polars and Pydantic.
"""

__version__ = "0.1.0"

from .server import FastAirport
from .client import FlightClient
from .context import Context
from .errors import (
    FastAirportError,
    InvalidArgument,
    NotFound,
    Unauthorized,
    Forbidden,
    InternalError,
    Unavailable,
    TimedOut,
    Cancelled,
    require_param,
    require_positive,
    require_non_empty,
    require_one_of,
)
from .types import BaseModel, Field, DataFrame, Series

__all__ = [
    "FastAirport",
    "FlightClient",
    "Context",
    "BaseModel",  # Pydantic BaseModel
    "Field",  # Pydantic Field
    "DataFrame",  # Polars DataFrame
    "Series",  # Polars Series
    # Errors
    "FastAirportError",
    "InvalidArgument",
    "NotFound",
    "Unauthorized",
    "Forbidden",
    "InternalError",
    "Unavailable",
    "TimedOut",
    "Cancelled",
    # Validation helpers
    "require_param",
    "require_positive",
    "require_non_empty",
    "require_one_of",
]


def hello() -> str:
    return "Hello from fastairport!"
