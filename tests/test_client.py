"""
Tests for FastAirport client functionality.
"""

import pytest
import pyarrow as pa
import polars as pl
from unittest.mock import patch, MagicMock
import json

from fastairport.client import FlightClient


@pytest.fixture
def mock_pyarrow_flight_client_instance():
    """Mocks the pyarrow.flight.Client instance returned by flight.connect()."""
    mock = MagicMock(spec=pa.flight.FlightClient)

    # Default return values for common methods
    mock.list_flights.return_value = []
    mock.list_actions.return_value = []
    mock.get_flight_info.return_value = MagicMock(
        spec=pa.flight.FlightInfo, endpoints=[]
    )

    return mock


@pytest.fixture
def mock_flight_connect(mock_pyarrow_flight_client_instance: MagicMock):
    """Patches pyarrow.flight.connect to return our mocked client instance."""
    with patch(
        "pyarrow.flight.connect", return_value=mock_pyarrow_flight_client_instance
    ) as mock_connect:
        yield mock_connect, mock_pyarrow_flight_client_instance


class TestFlightClient:
    def test_client_initialization(self, mock_flight_connect):
        mock_connect_func, _ = mock_flight_connect
        client = FlightClient("localhost:8815")
        mock_connect_func.assert_called_once_with(
            "grpc://localhost:8815", tls_root_certs=None
        )
        assert client._location_str == "grpc://localhost:8815"

        client_tls = FlightClient("grpc+tls://securehost:9000", tls_root_certs=b"certs")
        mock_connect_func.assert_called_with(
            "grpc+tls://securehost:9000", tls_root_certs=b"certs"
        )
        assert client_tls._location_str == "grpc+tls://securehost:9000"

    def test_list_endpoints(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect

        # Setup mock response from pyarrow client
        mock_flight_info1 = MagicMock(spec=pa.flight.FlightInfo)
        mock_flight_info1.descriptor = pa.flight.FlightDescriptor.for_path("ep1")
        mock_flight_info1.schema = pa.schema([("a", pa.int32())])
        mock_flight_info1.total_records = 100
        mock_flight_info1.total_bytes = 1024
        mock_flight_info1.ordered = False

        mock_pa_client.list_flights.return_value = [mock_flight_info1]

        client = FlightClient("dummy:123")
        endpoints = client.list_endpoints()

        mock_pa_client.list_flights.assert_called_once_with(options=None)
        assert len(endpoints) == 1
        assert endpoints[0]["name"] == "ep1"
        assert endpoints[0]["schema"] == mock_flight_info1.schema

    def test_get_data_arrow(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect

        sample_arrow_table = pa.Table.from_pydict({"colA": [1, 2]})
        mock_flight_endpoint = MagicMock(
            spec=pa.flight.FlightEndpoint, ticket=pa.flight.Ticket(b"testticket")
        )
        mock_flight_info = MagicMock(
            spec=pa.flight.FlightInfo, endpoints=[mock_flight_endpoint]
        )
        mock_reader = MagicMock(spec=pa.flight.FlightStreamReader)
        mock_reader.read_all.return_value = sample_arrow_table

        mock_pa_client.get_flight_info.return_value = mock_flight_info
        mock_pa_client.do_get.return_value = mock_reader

        client = FlightClient("dummy:123")
        table = client.get_data("my_data_ep", params={"id": 1})

        mock_pa_client.get_flight_info.assert_called_once()
        mock_pa_client.do_get.assert_called_once_with(
            mock_flight_endpoint.ticket, options=None
        )
        assert isinstance(table, pa.Table)
        assert table == sample_arrow_table

    def test_get_data_polars(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect

        sample_arrow_table = pa.Table.from_pydict({"colA": [1, 2]})
        expected_polars_df = pl.from_arrow(sample_arrow_table)

        mock_flight_endpoint = MagicMock(
            spec=pa.flight.FlightEndpoint, ticket=pa.flight.Ticket(b"testticket")
        )
        mock_flight_info = MagicMock(
            spec=pa.flight.FlightInfo, endpoints=[mock_flight_endpoint]
        )
        mock_reader = MagicMock(spec=pa.flight.FlightStreamReader)
        mock_reader.read_all.return_value = sample_arrow_table

        mock_pa_client.get_flight_info.return_value = mock_flight_info
        mock_pa_client.do_get.return_value = mock_reader

        client = FlightClient("dummy:123")
        polars_df = client.get_data("my_data_ep", as_polars=True)

        assert isinstance(polars_df, pl.DataFrame)
        assert polars_df.equals(expected_polars_df)

    def test_stream_data(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect

        mock_batch1_data = pa.record_batch([[1, 2]], names=["x"])
        mock_batch2_data = pa.record_batch([[3, 4]], names=["x"])

        mock_flight_endpoint = MagicMock(
            spec=pa.flight.FlightEndpoint, ticket=pa.flight.Ticket(b"testticket")
        )
        mock_flight_info = MagicMock(
            spec=pa.flight.FlightInfo, endpoints=[mock_flight_endpoint]
        )

        mock_stream_reader = MagicMock(spec=pa.flight.FlightStreamReader)
        mock_stream_reader.__iter__.return_value = iter(
            [mock_batch1_data, mock_batch2_data]
        )

        mock_pa_client.get_flight_info.return_value = mock_flight_info
        mock_pa_client.do_get.return_value = mock_stream_reader

        client = FlightClient("dummy:123")
        batches = list(client.stream_data("my_stream_ep"))
        assert len(batches) == 2
        assert batches[0] == mock_batch1_data
        assert batches[1] == mock_batch2_data

    def test_call_action_json_response(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect

        action_response_data = {"status": "ok", "value": 123}
        mock_result = MagicMock(spec=pa.flight.Result)
        mock_result.body.to_pybytes.return_value = json.dumps(
            action_response_data
        ).encode()

        mock_pa_client.do_action.return_value = iter([mock_result])

        client = FlightClient("dummy:123")
        response = client.call_action("my_action", params={"id": 1})

        mock_pa_client.do_action.assert_called_once()
        assert response == action_response_data

    def test_ping_success(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect
        mock_pa_client.list_actions.return_value = iter([])

        client = FlightClient("dummy:123")
        assert client.ping() is True
        mock_pa_client.list_actions.assert_called_once_with(options=None)

    def test_ping_failure(self, mock_flight_connect):
        _, mock_pa_client = mock_flight_connect
        mock_pa_client.list_actions.side_effect = Exception("Connection error")

        client = FlightClient("dummy:123")
        assert client.ping() is False
