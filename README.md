# FastAirport 🛩️

**The fast, Pythonic way to build Arrow Flight servers**

---

## 🌟 **Transform Your Data Into Distributed Intelligence**

FastAirport brings the **FastAPI decorator pattern** to Apache Arrow Flight, making it trivial to build high-performance data servers.

**Before FastAirport:**

```python
# 100+ lines of Arrow Flight boilerplate
class MLFlightServer(pyarrow.flight.FlightServerBase):
    def __init__(self, host="localhost", location=None, ...):
        super(MLFlightServer, self).__init__(...)
        # 50+ lines of setup

    def get_flight_info(self, context, descriptor):
        # 30+ lines of protocol handling

    def do_get(self, context, ticket):
        # 40+ lines of data handling
```

**With FastAirport:**

```python
from fastairport import FastAirport, Context
import pyarrow as pa
import polars as pl

airport = FastAirport("ML Intelligence Server")

@airport.endpoint("predict_churn")
def predict_churn(ctx: Context) -> pl.DataFrame:
    """Predict customer churn using ML model"""
    ctx.info("Computing predictions...")
    predictions = ml_model.predict(customer_data)
    return pl.DataFrame(predictions)

airport.start(host="0.0.0.0", port=8815)
```

**The transformation:** From 100+ lines of protocol handling to **6 lines of business logic**.

---

## 🚀 **Quick Start**

### Installation

```bash
pip install fastairport
```

### Create Your First Server

```python
# server.py
from fastairport import FastAirport, Context
import pyarrow as pa
import polars as pl

# Create server
airport = FastAirport("Demo Server")

@airport.endpoint("get_user")
def get_user(params: UserQuery, ctx: Context) -> pl.DataFrame:
    """Get user with request tracking."""
    ctx.info(f"Fetching user {params.user_id}")
    ctx.set_request_data("user_id", params.user_id)

    user_data = USERS.filter(pl.col("user_id") == params.user_id)
    if user_data.is_empty():
        raise NotFound(f"User {params.user_id} not found")

    return user_data.select(["user_id", "name"]) if not params.include_details else user_data

@airport.endpoint(
    "cached_users",
    schema=pa.schema([
        pa.field("user_id", pa.int64()),
        pa.field("name", pa.string()),
        pa.field("department", pa.string()),
    ])
)
def get_cached_users(ctx: Context) -> pl.DataFrame:
    """Endpoint with explicit schema."""
    ctx.info("Returning cached user data")
    return USERS.select(["user_id", "name", "department"])

@airport.streaming("user_stream")
def stream_users(ctx: Context, chunk_size: int = 2) -> Iterator[pl.DataFrame]:
    """Stream users with progress tracking."""
    ctx.info(f"Streaming {USERS.height} users in chunks of {chunk_size}")

    for i in range(0, USERS.height, chunk_size):
        ctx.check_cancelled()
        chunk = USERS.slice(i, chunk_size)
        ctx.report_progress(f"Streamed {min(i + chunk_size, USERS.height)}/{USERS.height} users")
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
    airport.start(port=8815)
```

### Run the Server

You can run your FastAirport server in two ways:

1. Using the CLI:

```bash
# Run a server
fastairport serve server.py --host 0.0.0.0 --port 8815

# List available endpoints and actions
fastairport list endpoints
fastairport list actions

# Get data from an endpoint
fastairport get get_user --param user_id=1
fastairport get cached_users

# Stream data
fastairport get user_stream --stream

# Call actions
fastairport action call health

# Health check
fastairport ping server
```

2. Running directly with Python:

```bash
python server.py
```

---

## 🏗️ **Core Features**

### **Decorator-Driven Simplicity**

```python
@airport.endpoint("data")
def get_data(ctx: Context) -> pl.DataFrame:
    return pl.DataFrame(my_data)

@airport.action("process")
def process_data(ctx: Context) -> dict:
    return {"status": "complete"}

@airport.streaming("large_dataset")
def stream_data(ctx: Context) -> Iterator[pl.DataFrame]:
    for chunk in load_large_dataset():
        yield pl.DataFrame(chunk)
```

### **Request Context**

```python
@airport.endpoint("analytics")
def get_analytics(ctx: Context) -> pl.DataFrame:
    # Logging
    ctx.info("Computing analytics...")
    ctx.warning("High load detected")
    ctx.error("Failed to fetch data")

    # Request tracking
    ctx.set_request_data("user_id", 123)
    last_user = ctx.get_request_data("user_id")

    # Progress reporting
    ctx.report_progress("Processing batch 1/10")

    # Cancellation support
    ctx.check_cancelled()

    return pl.DataFrame(results)
```

### **Explicit Schemas**

```python
@airport.endpoint(
    "cached_data",
    schema=pa.schema([
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
        pa.field("value", pa.float64()),
    ])
)
def get_cached_data(ctx: Context) -> pl.DataFrame:
    return pl.DataFrame(data)
```

---

## 🔧 **CLI Usage**

FastAirport comes with a powerful CLI for development and operations:

```bash
# Run a server
fastairport serve my_server.py --host 0.0.0.0 --port 8815

# List available endpoints and actions
fastairport list endpoints
fastairport list actions

# Get data from an endpoint
fastairport get get_user --param user_id=1
fastairport get cached_users

# Stream data
fastairport get user_stream --stream

# Call actions
fastairport action call health

# Health check
fastairport ping server
```

---

## 🌐 **Client Usage**

```python
from fastairport import FlightClient

# Connect to server
client = FlightClient("localhost:8815")

# Get data
users = client.get_data("get_user", {"user_id": 1})
cached = client.get_data("cached_users")

# Stream data
for batch in client.stream_data("user_stream"):
    process_batch(batch)

# Call actions
result = client.call_action("health")

# List available endpoints
endpoints = client.list_endpoints()
actions = client.list_actions()
```

---

## 🏆 **Why FastAirport?**

| Feature                | Raw Arrow Flight            | FastAirport               |
| ---------------------- | --------------------------- | ------------------------- |
| **Server Setup**       | 100+ lines                  | 6 lines                   |
| **Parameter Handling** | Manual parsing              | Automatic from type hints |
| **Schema Generation**  | Manual creation             | Automatic or explicit     |
| **Error Handling**     | Custom Flight errors        | Python exceptions         |
| **Streaming**          | Complex protocol            | Simple Iterator           |
| **Request Context**    | None                        | Rich context object       |
| **Development**        | Protocol expertise required | Pythonic patterns         |

---

## 🛠️ **Development**

### **Setup**

```bash
git clone https://github.com/cmakafui/fastairport.git
cd fastairport
uv pip install -e .
```

### **Testing**

```bash
pytest tests/
pytest tests/ --cov=src/fastairport --cov-report=html
```

### **Code Quality**

```bash
ruff check src/ tests/
```

---

## 📄 **License**

FastAirport is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 **Acknowledgments**

- **Apache Arrow** team for the amazing Arrow Flight protocol
- **FastAPI/FastMCP** for the decorator pattern inspiration
- **Polars** for the fast DataFrame implementation
- **Pydantic** for the data validation

---
