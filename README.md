# FastAirport

A tiny wrapper around Apache Arrow Flight for building analytical services.

```python
from fastairport import FastAirport, Context
import pyarrow as pa

airport = FastAirport("Demo")

@airport.endpoint("echo")
def echo(data: pa.Table, ctx: Context) -> pa.Table:
    ctx.info(f"rows: {data.num_rows}")
    return data

airport.start()
```

Clients send and receive Arrow tables:

```python
from fastairport import Client

client = Client("localhost:8815")
result = client.call("echo", pa.table({"a": [1, 2]}))
client.close()
```
