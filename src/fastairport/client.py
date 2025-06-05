import pyarrow as pa
import pyarrow.flight as flight


class Client:
    def __init__(self, location: str):
        if not location.startswith("grpc://"):
            location = f"grpc://{location}"
        self._client = flight.FlightClient(location)

    def call(self, endpoint: str, data: pa.Table) -> pa.Table:
        descriptor = flight.FlightDescriptor.for_command(endpoint.encode())
        writer, reader = self._client.do_exchange(descriptor)
        writer.begin(data.schema)
        for batch in data.to_batches():
            writer.write_batch(batch)
        writer.done_writing()
        return reader.read_all()

    def close(self) -> None:
        self._client.close()
