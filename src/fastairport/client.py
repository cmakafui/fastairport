"""
Client for interacting with FastAirport servers.
"""

import json
import logging
from typing import Any, Dict, Iterator, List, Optional, Union

import pyarrow as pa
import pyarrow.flight as flight
import polars as pl

from .utils import (
    create_flight_descriptor,
    parse_flight_descriptor as util_parse_flight_descriptor,
)
from .errors import InternalError

logger = logging.getLogger(__name__)


class FlightClient:
    """Client for interacting with FastAirport servers."""

    def __init__(
        self,
        location: Union[str, flight.Location],
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        tls_root_certs: Optional[bytes] = None,
    ):
        if isinstance(location, str):
            if not location.startswith(("grpc://", "grpc+tls://")):
                location = f"grpc://{location}"
            self._location_str = location
            self._client = flight.connect(location, tls_root_certs=tls_root_certs)
        else:
            self._location_str = location.uri.decode()
            self._client = flight.connect(location, tls_root_certs=tls_root_certs)

        self._call_options: Optional[flight.FlightCallOptions] = None
        if auth_token:
            self._call_options = flight.FlightCallOptions(
                headers=[(b"authorization", f"Bearer {auth_token}".encode())]
            )
        elif username and password:
            result = self._client.authenticate_basic_token(
                username.encode(), password.encode()
            )
            self._call_options = flight.FlightCallOptions(headers=list(result))
        logger.info(f"FlightClient connected to {self._location_str}")

    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List available endpoints on the server."""
        endpoints = []
        for flight_info in self._client.list_flights(options=self._call_options):
            name, _ = util_parse_flight_descriptor(flight_info.descriptor)
            endpoints.append(
                {
                    "name": name,
                    "schema": flight_info.schema,
                    "total_records": flight_info.total_records,
                    "total_bytes": flight_info.total_bytes,
                    "ordered": flight_info.ordered,
                }
            )
        return endpoints

    def get_data(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        as_polars: bool = False,
    ) -> Union[pa.Table, pl.DataFrame]:
        """
        Get data from an endpoint.

        Args:
            name: The endpoint name
            params: Optional parameters for the endpoint
            as_polars: If True, return as Polars DataFrame

        Returns:
            The data as an Arrow Table or Polars DataFrame
        """
        descriptor = create_flight_descriptor(name, params)
        flight_info = self._client.get_flight_info(
            descriptor, options=self._call_options
        )
        if not flight_info.endpoints:
            raise InternalError(f"No endpoints available for '{name}'")

        reader = self._client.do_get(
            flight_info.endpoints[0].ticket, options=self._call_options
        )
        arrow_table = reader.read_all()

        if as_polars:
            return pl.from_arrow(arrow_table)
        return arrow_table

    def stream_data(
        self, name: str, params: Optional[Dict[str, Any]] = None
    ) -> Iterator[pa.RecordBatch]:
        """
        Stream data from an endpoint.

        Args:
            name: The endpoint name
            params: Optional parameters for the endpoint

        Yields:
            Arrow RecordBatches
        """
        descriptor = create_flight_descriptor(name, params)
        flight_info = self._client.get_flight_info(
            descriptor, options=self._call_options
        )
        if not flight_info.endpoints:
            raise InternalError(f"No endpoints available for '{name}'")

        reader = self._client.do_get(
            flight_info.endpoints[0].ticket, options=self._call_options
        )
        for record_batch_reader_chunk in reader:
            yield record_batch_reader_chunk

    def call_action(self, name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call an action on the server.

        Args:
            name: The action name
            params: Optional parameters for the action

        Returns:
            The action result
        """
        body = json.dumps(params).encode() if params else b""
        action = flight.Action(name, body)
        results = list(self._client.do_action(action, options=self._call_options))
        if not results:
            return None
        res_bytes = results[0].body.to_pybytes()
        try:
            return json.loads(res_bytes.decode())
        except json.JSONDecodeError:
            return res_bytes.decode()

    def list_actions(self) -> List[Dict[str, str]]:
        """List available actions on the server."""
        actions_list = []
        for action_type in self._client.list_actions(options=self._call_options):
            actions_list.append(
                {"name": action_type.type, "description": action_type.description}
            )
        return actions_list

    def ping(self) -> bool:
        """Check if the server is reachable."""
        try:
            self.list_actions()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the client connection."""
        self._client.close()
        logger.info(f"FlightClient disconnected from {self._location_str}")

    def __enter__(self) -> "FlightClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"FlightClient(location='{self._location_str}')"
