"""Minimal Arrow Flight framework."""

__version__ = "0.2.0"

from .server import FastAirport
from .client import Client
from .context import Context
from .errors import FastAirportError, EndpointNotFound

__all__ = [
    "FastAirport",
    "Client",
    "Context",
    "FastAirportError",
    "EndpointNotFound",
]
