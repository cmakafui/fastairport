"""
FastAirport server example.
"""

import polars as pl
import pyarrow as pa
from typing import Iterator
from fastairport import FastAirport, Context, BaseModel, Field, DataFrame

# Initialize FastAirport server
airport = FastAirport(name="Demo Server", location="grpc://0.0.0.0:8815")


# --- Pydantic models ---
class UserQuery(BaseModel):
    user_id: int = Field(..., gt=0)
    include_details: bool = Field(default=False)


# Sample data
USERS = pl.DataFrame(
    {
        "user_id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "email": [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "diana@example.com",
            "eve@example.com",
        ],
        "department": [
            "Engineering",
            "Sales",
            "Engineering",
            "Marketing",
            "Engineering",
        ],
    }
)


@airport.endpoint(
    "users",
    schema=pa.schema(
        [
            pa.field("user_id", pa.int64()),
            pa.field("name", pa.string()),
            pa.field("email", pa.string()),
            pa.field("department", pa.string()),
        ]
    ),
)
def get_users(ctx: Context) -> DataFrame:
    """Get users with request correlation."""
    ctx.set_request_data("user_id", 1)
    return USERS.head(3)


@airport.endpoint(
    "get_user",
    schema=pa.schema(
        [
            pa.field("user_id", pa.int64()),
            pa.field("name", pa.string()),
            pa.field("email", pa.string()),
            pa.field("department", pa.string()),
        ]
    ),
)
def get_user(params: UserQuery, ctx: Context) -> DataFrame:
    """Get user with request tracking."""
    ctx.info(f"Fetching user {params.user_id}")

    # Store request data for correlation
    ctx.set_request_data("user_id", params.user_id)

    user_data = USERS.filter(pl.col("user_id") == params.user_id)
    if user_data.is_empty():
        from fastairport.errors import NotFound

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
    """Endpoint with explicit schema (no inference overhead)."""
    ctx.info("Returning cached user data")
    return USERS.select(["user_id", "name", "department"])


@airport.streaming(
    "user_stream",
    schema=pa.schema(
        [
            pa.field("user_id", pa.int64()),
            pa.field("name", pa.string()),
            pa.field("email", pa.string()),
            pa.field("department", pa.string()),
        ]
    ),
)
def stream_users(ctx: Context, chunk_size: int = 2) -> Iterator[DataFrame]:
    """Stream users with progress tracking and cancellation."""
    ctx.info(f"Streaming {USERS.height} users in chunks of {chunk_size}")

    for i in range(0, USERS.height, chunk_size):
        # Check if client cancelled
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
        "server": "Demo Server",
        "last_user_request": last_user_id,
    }


if __name__ == "__main__":
    airport.start(host="0.0.0.0", port=8815)
