"""
Tests for FastAirport CLI functionality.
"""

import pytest
from typer.testing import CliRunner
import polars as pl
from unittest.mock import patch, MagicMock

from fastairport.cli.main import app
from fastairport.client import FlightClient

runner = CliRunner()


@pytest.fixture
def mock_flight_client():
    """Mocks FlightClient for CLI tests."""
    with (
        patch("fastairport.cli.commands.get.FlightClient") as MockGetClient,
        patch("fastairport.cli.commands.list.FlightClient") as MockListClient,
        patch("fastairport.cli.commands.action.FlightClient") as MockActionClient,
        patch("fastairport.cli.commands.ping.FlightClient") as MockPingClient,
    ):
        mock_instance = MagicMock(spec=FlightClient)

        # Default behaviors
        mock_instance.list_endpoints.return_value = [
            {"name": "get_user", "description": "Get user by ID"},
            {"name": "cached_users", "description": "Get cached users"},
        ]
        mock_instance.list_actions.return_value = [
            {"name": "health", "description": "Health check"},
        ]
        mock_instance.get_data.return_value = pl.DataFrame(
            {
                "user_id": [1],
                "name": ["Alice"],
            }
        ).to_arrow()
        mock_instance.stream_data.return_value = iter(
            [
                pl.DataFrame({"user_id": [1, 2], "name": ["Alice", "Bob"]}).to_arrow(),
                pl.DataFrame({"user_id": [3], "name": ["Charlie"]}).to_arrow(),
            ]
        )
        mock_instance.call_action.return_value = {
            "status": "healthy",
            "server": "Demo Server",
            "last_user_request": "none",
        }
        mock_instance.ping.return_value = True

        # Set all mocks to return the same instance
        for MockClient in [
            MockGetClient,
            MockListClient,
            MockActionClient,
            MockPingClient,
        ]:
            MockClient.return_value = mock_instance
        mock_instance.__enter__.return_value = mock_instance
        yield mock_instance


def test_cli_version():
    """Test CLI version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "FastAirport CLI Version" in result.stdout


def test_cli_list_endpoints(mock_flight_client):
    """Test listing endpoints."""
    result = runner.invoke(app, ["list", "endpoints"])
    assert result.exit_code == 0
    assert "get_user" in result.stdout
    assert "cached_users" in result.stdout


def test_cli_list_actions(mock_flight_client):
    """Test listing actions."""
    result = runner.invoke(app, ["list", "actions"])
    assert result.exit_code == 0
    assert "health" in result.stdout


def test_cli_get_data(mock_flight_client):
    """Test getting data from endpoint."""
    result = runner.invoke(app, ["get", "get_user", "--param", "user_id=1"])
    assert result.exit_code == 0
    assert "Alice" in result.stdout


def test_cli_stream_data(mock_flight_client):
    """Test streaming data from endpoint."""
    result = runner.invoke(app, ["get", "user_stream", "--stream"])
    assert result.exit_code == 0
    assert "Streaming data from endpoint" in result.stdout
    assert "Stream finished" in result.stdout
    assert "2 batches" in result.stdout
    assert "3 records" in result.stdout


def test_cli_call_action(mock_flight_client):
    """Test calling an action."""
    result = runner.invoke(app, ["action", "call", "health"])
    assert result.exit_code == 0
    assert "healthy" in result.stdout
    assert "Demo Server" in result.stdout


def test_cli_ping_server(mock_flight_client):
    """Test pinging server."""
    result = runner.invoke(app, ["ping", "server"])
    assert result.exit_code == 0
    assert "reachable" in result.stdout


def test_cli_ping_failure():
    """Test ping failure."""
    with patch(
        "fastairport.cli.commands.ping.FlightClient",
        side_effect=ConnectionRefusedError("Cannot connect"),
    ):
        result = runner.invoke(app, ["ping", "server", "--host", "badhost"])
        assert result.exit_code == 1
        assert "Could not connect" in result.stdout
