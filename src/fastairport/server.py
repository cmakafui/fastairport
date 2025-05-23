"""
FastAirport server implementation.
"""

import inspect
import json
import logging
import signal
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional, Union, Set
from collections.abc import Iterable

import pyarrow as pa
import pyarrow.flight as flight
import polars as pl
from pydantic import BaseModel

from .context import Context
from .errors import FastAirportError
from .utils import (
    parse_flight_descriptor as util_parse_flight_descriptor,
    create_flight_info as util_create_flight_info,
)
from ._pydantic_utils import parse_and_validate_params

logger = logging.getLogger(__name__)


class FastAirport(flight.FlightServerBase):
    """FastAirport server implementation."""

    def __init__(
        self,
        name: str,
        location: Optional[Union[str, flight.Location]] = None,
        auth_handler: Optional[flight.ServerAuthHandler] = None,
        tls_certificates: Optional[List[flight.CertKeyPair]] = None,
        verify_client: bool = False,
        root_certificates: Optional[bytes] = None,
        middleware: Optional[Dict[str, flight.ServerMiddlewareFactory]] = None,
    ):
        super().__init__(
            location,
            auth_handler=auth_handler,
            tls_certificates=tls_certificates,
            verify_client=verify_client,
            root_certificates=root_certificates,
            middleware=middleware,
        )
        self.name = name
        self.location = location
        self._endpoints: Dict[str, Callable[..., Any]] = {}
        self._actions: Dict[str, Callable[..., Any]] = {}
        self._endpoint_schemas: Dict[str, pa.Schema] = {}  # Explicit + cached schemas
        self._streaming_endpoints: Set[str] = set()
        self._server_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._schema_lock = threading.RLock()
        logger.info(f"FastAirport server '{name}' initialized")

    def endpoint(
        self,
        name: str,
        *,
        streaming: bool = False,
        auth_required: bool = False,
        schema: Optional[pa.Schema] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an endpoint."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._endpoints[name] = func
            if streaming:
                self._streaming_endpoints.add(name)
            if schema is not None:
                self._endpoint_schemas[name] = schema
            func._fastairport_metadata = {
                "type": "endpoint",
                "name": name,
                "streaming": streaming,
                "auth_required": auth_required,
            }
            logger.info(f"Registered endpoint: '{name}' (streaming: {streaming})")
            return func

        return decorator

    def action(
        self, name: str, *, auth_required: bool = False
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an action."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._actions[name] = func
            func._fastairport_metadata = {
                "type": "action",
                "name": name,
                "auth_required": auth_required,
            }
            logger.info(f"Registered action: '{name}'")
            return func

        return decorator

    def streaming(
        self,
        name: str,
        *,
        auth_required: bool = False,
        schema: Optional[pa.Schema] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a streaming endpoint."""
        return self.endpoint(
            name, streaming=True, auth_required=auth_required, schema=schema
        )

    def list_flights(
        self, context: flight.ServerCallContext, criteria: bytes
    ) -> Iterator[flight.FlightInfo]:
        """List available flights (endpoints)."""
        for name, func in self._endpoints.items():
            try:
                # Get schema from explicit schemas or infer it
                schema = self._get_endpoint_schema(name, func, {})
                if schema is None:
                    logger.warning(
                        f"No schema available for endpoint '{name}', skipping"
                    )
                    continue

                # Create flight descriptor and info
                descriptor = flight.FlightDescriptor.for_path(name.encode())
                flight_info = util_create_flight_info(descriptor, schema)

                # FlightInfo doesn't have a metadata attribute - skip metadata for now

                yield flight_info
            except Exception as e:
                logger.warning(
                    f"Could not create FlightInfo for endpoint '{name}': {e}",
                    exc_info=True,
                )

    def get_flight_info(
        self, context: flight.ServerCallContext, descriptor: flight.FlightDescriptor
    ) -> flight.FlightInfo:
        """Get flight info for an endpoint."""
        try:
            endpoint_name, params = util_parse_flight_descriptor(descriptor)
            if endpoint_name not in self._endpoints:
                raise flight.FlightNotFoundError(
                    f"Endpoint '{endpoint_name}' not found."
                )

            func = self._endpoints[endpoint_name]
            schema = self._get_endpoint_schema(endpoint_name, func, params)
            if not schema:
                raise flight.FlightInternalError(
                    f"Could not determine schema for endpoint '{endpoint_name}'."
                )
            return util_create_flight_info(descriptor, schema)
        except flight.FlightError:
            raise
        except FastAirportError as e:
            raise e.to_flight_error()
        except Exception as e:
            logger.error(
                f"Error in get_flight_info for '{descriptor.path}': {e}", exc_info=True
            )
            raise flight.FlightInternalError(
                f"Unexpected error processing get_flight_info: {e}"
            )

    def do_get(
        self, context: flight.ServerCallContext, ticket_bytes: flight.Ticket
    ) -> flight.FlightDataStream:
        """Handle a GET request."""
        endpoint_name = "unknown"
        try:
            # Debug what's in the ticket
            ticket_str = ticket_bytes.ticket.decode()
            logger.debug(f"Received ticket: {ticket_str}")
            ticket_data = json.loads(ticket_str)
            endpoint_name = ticket_data.get("endpoint")
            raw_params = ticket_data.get("params", {})

            if not endpoint_name:
                raise flight.FlightInternalError("No endpoint specified in ticket")

            if endpoint_name not in self._endpoints:
                raise flight.FlightNotFoundError(
                    f"Endpoint '{endpoint_name}' not found."
                )

            func = self._endpoints[endpoint_name]
            result_data = self._call_handler(func, raw_params, context)

            if result_data is None:
                raise flight.FlightInternalError(
                    f"Endpoint '{endpoint_name}' returned None"
                )

            if endpoint_name in self._streaming_endpoints:
                if not isinstance(result_data, Iterable):
                    raise flight.FlightInternalError(
                        f"Streaming endpoint '{endpoint_name}' did not return an iterable."
                    )
                if not isinstance(result_data, Iterator):
                    result_data = iter(result_data)
                return self._create_streaming_response(
                    result_data, endpoint_name, func, raw_params
                )
            else:
                arrow_table = self._convert_to_arrow_table(result_data, endpoint_name)
                if arrow_table.num_rows == 0:
                    # Return empty table with correct schema
                    schema = self._get_endpoint_schema(endpoint_name, func, raw_params)
                    if schema:
                        arrow_table = pa.Table.from_pylist([], schema=schema)
                return flight.GeneratorStream(
                    arrow_table.schema, arrow_table.to_batches()
                )

        except flight.FlightError:
            raise
        except FastAirportError as e:
            raise e.to_flight_error()
        except Exception as e:
            logger.error(
                f"Error in do_get for endpoint '{endpoint_name}': {e}", exc_info=True
            )
            raise flight.FlightInternalError(f"Error processing do_get: {e}")

    def do_action(
        self, context: flight.ServerCallContext, action_desc: flight.Action
    ) -> Iterator[flight.Result]:
        """Handle an action request."""
        action_name = action_desc.type
        try:
            if action_name not in self._actions:
                raise flight.FlightNotFoundError(f"Action '{action_name}' not found.")

            func = self._actions[action_name]
            raw_params: Dict[str, Any] = {}
            if action_desc.body and len(action_desc.body.to_pybytes()) > 0:
                try:
                    raw_params = json.loads(action_desc.body.to_pybytes().decode())
                except json.JSONDecodeError:
                    raw_params = {"body": action_desc.body.to_pybytes().decode()}

            result = self._call_handler(func, raw_params, context)
            result_payload = self._serialize_action_result(result)
            yield flight.Result(pa.py_buffer(result_payload))

        except flight.FlightError:
            raise
        except FastAirportError as e:
            raise e.to_flight_error()
        except Exception as e:
            logger.error(f"Error in do_action for '{action_name}': {e}", exc_info=True)
            raise flight.FlightInternalError(
                f"Error executing action '{action_name}': {e}"
            )

    def list_actions(
        self, context: flight.ServerCallContext
    ) -> Iterator[flight.ActionType]:
        """List available actions."""
        for name, func in self._actions.items():
            doc = inspect.getdoc(func) or f"Action: {name}"
            # Create ActionType with positional parameters
            action_type = flight.ActionType(name, doc)
            yield action_type

    def _call_handler(
        self,
        func: Callable[..., Any],
        raw_params: Dict[str, Any],
        call_ctx: Optional[flight.ServerCallContext],
    ) -> Any:
        """Call a handler function with validated parameters."""
        sig = inspect.signature(func)
        try:
            parsed_args = parse_and_validate_params(raw_params, sig)
        except FastAirportError as e:
            logger.error(f"Parameter validation failed: {e}")
            raise e

        if "ctx" in sig.parameters:
            parsed_args["ctx"] = Context(call_ctx, self)

        return func(**parsed_args)

    def _convert_to_arrow_table(self, result_data: Any, endpoint_name: str) -> pa.Table:
        """Convert result data to Arrow table."""
        if isinstance(result_data, pl.DataFrame):
            return result_data.to_arrow()
        elif isinstance(result_data, pa.Table):
            return result_data
        elif isinstance(result_data, BaseModel):
            return pa.Table.from_pylist([result_data.model_dump()])
        elif isinstance(result_data, dict):
            return pa.Table.from_pylist([result_data])
        # Handle lists
        elif isinstance(result_data, list):
            if not result_data:  # Empty list
                return pa.Table.from_pylist([])
            elif all(isinstance(item, BaseModel) for item in result_data):
                return pa.Table.from_pylist([item.model_dump() for item in result_data])
            elif all(isinstance(item, dict) for item in result_data):
                return pa.Table.from_pylist(result_data)
            else:
                raise flight.FlightInternalError(
                    f"Endpoint '{endpoint_name}' returned unsupported list type"
                )
        else:
            raise flight.FlightInternalError(
                f"Endpoint '{endpoint_name}' returned unsupported type: {type(result_data)}"
            )

    def _serialize_action_result(self, result: Any) -> bytes:
        """Serialize action result to bytes."""
        if isinstance(result, BaseModel):
            return result.model_dump_json().encode("utf-8")
        elif isinstance(result, (dict, list)):
            return json.dumps(result).encode("utf-8")
        elif isinstance(result, str):
            return result.encode("utf-8")
        elif result is None:
            return b""
        else:
            return str(result).encode("utf-8")

    def _get_endpoint_schema(
        self, name: str, func: Callable[..., Any], params: Dict[str, Any]
    ) -> Optional[pa.Schema]:
        """Get the schema for an endpoint."""
        # Use explicit schema if provided
        if name in self._endpoint_schemas:
            return self._endpoint_schemas[name]

        # Try schema inference (no caching)
        try:
            schema = self._infer_schema_from_handler(name, func, params)
            if schema is not None:
                return schema
        except Exception as e:
            logger.warning(f"Schema inference failed for endpoint '{name}': {e}")

        # Fallback placeholder when inference fails or returns None
        logger.info(
            f"Using fallback schema for endpoint '{name}' (inference failed or requires parameters)"
        )
        return pa.schema(
            [
                pa.field(
                    "data",
                    pa.binary(),
                    metadata={
                        "fastairport_comment": "Schema inference failed - using fallback"
                    },
                )
            ]
        )

    def _infer_schema_from_handler(
        self, name: str, func: Callable[..., Any], params: Dict[str, Any]
    ) -> Optional[pa.Schema]:
        """Infer schema by calling the handler with a mock context."""
        is_streaming = name in self._streaming_endpoints

        # Create a mock context for schema inference
        mock_context = Context(None, self)

        try:
            # Check if handler requires parameters that aren't provided
            sig = inspect.signature(func)
            required_params = [
                p.name
                for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty and p.name != "ctx"
            ]

            # If required params are missing, skip schema inference
            if required_params and not params:
                logger.debug(
                    f"Skipping schema inference for '{name}': requires parameters {required_params}"
                )
                return None

            result_for_schema = self._call_handler(func, params, mock_context)
        except Exception as e:
            logger.warning(f"Schema inference failed for '{name}': {e}")
            return None

        if is_streaming:
            if not isinstance(result_for_schema, Iterable):
                return None

            # Use tee to avoid consuming the iterator
            import itertools

            iter1, _ = itertools.tee(result_for_schema)

            try:
                first_item = next(iter1, None)
                if first_item is None:
                    return None
                return self._extract_schema_from_item(first_item)
            except Exception:
                return None
        else:
            return self._extract_schema_from_item(result_for_schema)

    def _extract_schema_from_item(self, item: Any) -> Optional[pa.Schema]:
        """Extract Arrow schema from a data item."""
        if isinstance(item, pl.DataFrame):
            return item.to_arrow().schema
        elif isinstance(item, pa.Table):
            return item.schema
        elif isinstance(item, BaseModel):
            return pa.Table.from_pylist([item.model_dump()]).schema
        elif isinstance(item, dict):
            return pa.Table.from_pylist([item]).schema
        return None

    def _create_streaming_response(
        self,
        data_iterator: Iterator[Any],
        name: str,
        func: Callable[..., Any],
        params: Dict[str, Any],
    ) -> flight.FlightDataStream:
        """Create a streaming response from an iterator."""
        schema = self._get_endpoint_schema(name, func, params)

        def generator_wrapper():
            for item in data_iterator:
                arrow_table = self._convert_to_arrow_table(item, name)
                yield from arrow_table.to_batches()

        return flight.GeneratorStream(schema, generator_wrapper())

    def start(
        self, host: str = "0.0.0.0", port: int = 8815, blocking: bool = True
    ) -> None:
        """Start the server."""
        if not self.location:
            self.location = f"grpc://{host}:{port}"

        logger.info(f"Starting FastAirport server '{self.name}' on {self.location}")
        logger.info(f"Registered endpoints: {list(self._endpoints.keys())}")
        logger.info(f"Registered actions: {list(self._actions.keys())}")

        if blocking:
            # Set up signal handler for graceful shutdown
            def signal_handler(signum, frame):
                logger.info("Received interrupt signal, shutting down gracefully...")
                self.shutdown()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            try:
                super().serve()
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt caught, shutting down gracefully...")
                self.shutdown()
        else:
            # Cleanup existing thread if any
            if self._server_thread and self._server_thread.is_alive():
                logger.warning("Existing server thread found, shutting down first")
                self.shutdown()

            self._server_thread = threading.Thread(target=super().serve, daemon=True)
            self._server_thread.start()
            logger.info(f"Server '{self.name}' running in background thread.")

    def serve(self) -> None:
        """Serve the server - simplified to avoid recursion."""
        super().serve()

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Shutdown the server."""
        logger.info(f"Shutting down FastAirport server '{self.name}'...")
        self._shutdown_event.set()
        super().shutdown()
        if self._server_thread and self._server_thread.is_alive():
            logger.info("Waiting for server thread to join...")
            self._server_thread.join(timeout=timeout or 5.0)
            if self._server_thread.is_alive():
                logger.warning("Server thread did not shut down cleanly.")
        logger.info(f"Server '{self.name}' shut down.")

    def _create_action_type(
        self, name: str, func: Callable[..., Any]
    ) -> flight.ActionType:
        """Helper method to create an ActionType object."""
        doc = inspect.getdoc(func) or f"Action: {name}"
        return flight.ActionType(name=name, description=doc)
