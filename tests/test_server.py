import threading
import time

import pyarrow as pa
from fastairport import FastAirport, Client


def test_echo_roundtrip():
    tbl = pa.table({"a": [1, 2]})

    airport = FastAirport("Test")

    @airport.endpoint("echo")
    def echo(data: pa.Table, ctx):
        return data

    thread = threading.Thread(target=airport.start, kwargs={"host": "127.0.0.1", "port": 8815}, daemon=True)
    thread.start()
    time.sleep(0.5)

    client = Client("127.0.0.1:8815")
    result = client.call("echo", tbl)
    client.close()

    airport.stop()
    thread.join(timeout=1)

    assert result.equals(tbl)

