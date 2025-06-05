import threading
import time

import pyarrow as pa
from fastairport import FastAirport, Client


def start_server():
    airport = FastAirport("Srv")

    @airport.endpoint("add")
    def add(data: pa.Table, ctx):
        arr = data.column(0)
        total = sum(arr.to_pylist())
        return pa.table({"sum": [total]})

    thread = threading.Thread(target=airport.start, kwargs={"host": "127.0.0.1", "port": 8816}, daemon=True)
    thread.start()
    time.sleep(0.5)
    return airport, thread


def test_client_call():
    airport, thread = start_server()
    client = Client("127.0.0.1:8816")
    tbl = pa.table({"x": [1, 2, 3]})
    out = client.call("add", tbl)
    client.close()
    airport.stop()
    thread.join(timeout=1)
    assert out.to_pydict() == {"sum": [6]}

