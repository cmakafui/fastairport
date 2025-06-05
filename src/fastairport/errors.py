class FastAirportError(Exception):
    """Base exception for FastAirport."""


class EndpointNotFound(FastAirportError):
    pass
