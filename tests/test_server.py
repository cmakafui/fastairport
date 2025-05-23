"""
Tests for FastAirport server functionality.
"""

import pytest
import pyarrow as pa
import polars as pl
from pydantic import BaseModel, Field
from typing import Iterator

from fastairport import FastAirport, Context, DataFrame, NotFound


# --- Test Pydantic Models ---
class UserQuery(BaseModel):
    user_id: int = Field(..., gt=0)
    include_details: bool = Field(default=False)


# --- Test Server Fixture ---
@pytest.fixture
def test_airport() -> FastAirport:
    airport = FastAirport(name="TestServer")

    # Sample data
    USERS = pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "email": ["alice@example.com", "bob@example.com", "charlie@example.com"],
            "department": ["Engineering", "Sales", "Engineering"],
        }
    )

    @airport.endpoint("get_user")
    def get_user(params: UserQuery, ctx: Context) -> DataFrame:
        """Get user with request tracking."""
        ctx.info(f"Fetching user {params.user_id}")
        ctx.set_request_data("user_id", params.user_id)

        user_data = USERS.filter(pl.col("user_id") == params.user_id)
        if user_data.is_empty():
            raise NotFound(f"User {params.user_id} not found")

        return (
            user_data.select(["user_id", "name"])
            if not params.include_details
            else user_data
        )

    @airport.endpoint(
        "cached_users",
        schema=pa.schema(
            [
                pa.field("user_id", pa.int64()),
                pa.field("name", pa.string()),
                pa.field("department", pa.string()),
            ]
        ),
    )
    def get_cached_users(ctx: Context) -> DataFrame:
        """Endpoint with explicit schema."""
        ctx.info("Returning cached user data")
        return USERS.select(["user_id", "name", "department"])

    @airport.streaming("user_stream")
    def stream_users(ctx: Context, chunk_size: int = 2) -> Iterator[DataFrame]:
        """Stream users with progress tracking."""
        ctx.info(f"Streaming {USERS.height} users in chunks of {chunk_size}")

        for i in range(0, USERS.height, chunk_size):
            ctx.check_cancelled()
            chunk = USERS.slice(i, chunk_size)
            ctx.report_progress(
                f"Streamed {min(i + chunk_size, USERS.height)}/{USERS.height} users"
            )
            yield chunk

    @airport.action("health")
    def health_check(ctx: Context) -> dict:
        """Health check with request correlation."""
        last_user_id = ctx.get_request_data("user_id", "none")
        return {
            "status": "healthy",
            "server": "TestServer",
            "last_user_request": last_user_id,
        }

    return airport


# --- Tests ---
def test_get_user_endpoint_success(test_airport: FastAirport):
    """Test successful user retrieval."""
    handler_func = test_airport._endpoints["get_user"]
    raw_params = {"user_id": 1}
    result_df = test_airport._call_handler(handler_func, raw_params, None)

    assert isinstance(result_df, pl.DataFrame)
    assert result_df.height == 1
    assert result_df["user_id"][0] == 1
    assert result_df["name"][0] == "Alice"


def test_get_user_endpoint_not_found(test_airport: FastAirport):
    """Test user not found error."""
    handler_func = test_airport._endpoints["get_user"]
    raw_params = {"user_id": 999}
    with pytest.raises(NotFound):
        test_airport._call_handler(handler_func, raw_params, None)


def test_cached_users_endpoint(test_airport: FastAirport):
    """Test endpoint with explicit schema."""
    handler_func = test_airport._endpoints["cached_users"]
    result_df = test_airport._call_handler(handler_func, {}, None)

    assert isinstance(result_df, pl.DataFrame)
    assert result_df.height == 3
    assert "user_id" in result_df.columns
    assert "name" in result_df.columns
    assert "department" in result_df.columns


def test_stream_users_endpoint(test_airport: FastAirport):
    """Test streaming endpoint with progress tracking."""
    handler_func = test_airport._endpoints["user_stream"]
    iterator = test_airport._call_handler(handler_func, {"chunk_size": 2}, None)

    results = list(iterator)
    assert len(results) == 2  # 3 users in chunks of 2
    assert isinstance(results[0], pl.DataFrame)
    assert results[0].height == 2
    assert results[1].height == 1


def test_health_action(test_airport: FastAirport):
    """Test health check action with request correlation."""
    # Create a shared context that persists across calls
    shared_context = Context(None, test_airport)

    # Manually call the functions with shared context
    get_user_func = test_airport._endpoints["get_user"]
    user_query = UserQuery(user_id=1)
    get_user_func(params=user_query, ctx=shared_context)

    # Then check health with the same context
    health_func = test_airport._actions["health"]
    result = health_func(ctx=shared_context)

    assert isinstance(result, dict)
    assert result["status"] == "healthy"
    assert result["last_user_request"] == 1
