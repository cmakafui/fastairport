"""
Utility functions for Arrow Flight operations.
"""

import json
from typing import Dict, Any, Tuple
import pyarrow as pa
import pyarrow.flight as flight


def parse_flight_descriptor(
    descriptor: flight.FlightDescriptor,
) -> Tuple[str, Dict[str, Any]]:
    """
    Parse a Flight descriptor into endpoint name and parameters.

    Args:
        descriptor: The Flight descriptor to parse

    Returns:
        Tuple of (endpoint_name, parameters_dict)
    """
    if descriptor.descriptor_type == flight.DescriptorType.PATH:
        path = descriptor.path[0].decode()
        params = {}
        if len(descriptor.path) > 1:
            try:
                params = json.loads(descriptor.path[1].decode())
            except (json.JSONDecodeError, IndexError, UnicodeDecodeError) as e:
                # Log warning for malformed parameters
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to parse descriptor parameters: {e}")
                pass
        return path, params
    elif descriptor.descriptor_type == flight.DescriptorType.CMD:
        try:
            cmd = json.loads(descriptor.command.decode())
            return cmd.get("endpoint", ""), cmd.get("params", {})
        except json.JSONDecodeError:
            return "", {}
    else:
        return "", {}


def create_flight_descriptor(
    endpoint: str, params: Dict[str, Any]
) -> flight.FlightDescriptor:
    """
    Create a Flight descriptor from endpoint name and parameters.

    Args:
        endpoint: The endpoint name
        params: The parameters dictionary

    Returns:
        A Flight descriptor
    """
    if not params:
        return flight.FlightDescriptor.for_path(endpoint.encode())

    cmd = {"endpoint": endpoint, "params": params}
    return flight.FlightDescriptor.for_command(json.dumps(cmd).encode())


def create_flight_info(
    descriptor: flight.FlightDescriptor, schema: pa.Schema
) -> flight.FlightInfo:
    """
    Create a Flight info object from a descriptor and schema.

    Args:
        descriptor: The Flight descriptor
        schema: The Arrow schema

    Returns:
        A Flight info object
    """
    # Create a ticket for this endpoint
    ticket = create_ticket_from_descriptor(descriptor)

    # Create an endpoint with the ticket
    endpoint = flight.FlightEndpoint(ticket, [])

    return flight.FlightInfo(
        schema,
        descriptor,
        [endpoint],  # Include the endpoint
        -1,  # Unknown total records
        -1,  # Unknown total bytes
    )


def create_ticket_from_descriptor(descriptor: flight.FlightDescriptor) -> flight.Ticket:
    """
    Create a Flight ticket from a descriptor.

    Args:
        descriptor: The Flight descriptor

    Returns:
        A Flight ticket
    """
    if descriptor.descriptor_type == flight.DescriptorType.PATH:
        ticket_data = {"endpoint": descriptor.path[0].decode(), "params": {}}
        if len(descriptor.path) > 1:
            try:
                ticket_data["params"] = json.loads(descriptor.path[1].decode())
            except (json.JSONDecodeError, IndexError, UnicodeDecodeError) as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to parse ticket parameters: {e}")
                pass
    else:
        try:
            cmd = json.loads(descriptor.command.decode())
            ticket_data = {
                "endpoint": cmd.get("endpoint", ""),
                "params": cmd.get("params", {}),
            }
        except json.JSONDecodeError:
            ticket_data = {"endpoint": "", "params": {}}

    return flight.Ticket(json.dumps(ticket_data).encode())
