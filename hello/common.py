"""Shared settings and topic helpers for the Wirepas hello example.

Topic names follow the Wirepas Gateway-to-Backend API v2, which is what a real
transport service publishes to MQTT:

    gw-event/status/<gw_id>
    gw-event/received_data/<gw_id>/<sink_id>/<network_address>/<src_ep>/<dst_ep>
    gw-request/send_data/<gw_id>/<sink_id>
    gw-response/send_data/<gw_id>/<sink_id>
"""

import os

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Identifiers the fake gateway pretends to have. A real deployment gets the
# gateway id from the transport service configuration and the sink id from the
# sink service instance (usually "sink0" for the first dongle).
GW_ID = "gw-hello"
SINK_ID = "sink0"
NETWORK_ADDRESS = 0x123456

# Endpoints are the Wirepas equivalent of port numbers: an application picks a
# pair and both ends agree on how to interpret the payload.
SOURCE_ENDPOINT = 1
DESTINATION_ENDPOINT = 1

# Address of the node the fake gateway pretends to hear from.
NODE_ADDRESS = 1001


def status_topic(gw_id: str = "+") -> str:
    return f"gw-event/status/{gw_id}"


def received_data_topic(
    gw_id: str = "+",
    sink_id: str = "+",
    network_address: int | str = "+",
    src_ep: int | str = "+",
    dst_ep: int | str = "+",
) -> str:
    return f"gw-event/received_data/{gw_id}/{sink_id}/{network_address}/{src_ep}/{dst_ep}"


def send_data_request_topic(gw_id: str = "+", sink_id: str = "+") -> str:
    return f"gw-request/send_data/{gw_id}/{sink_id}"


def send_data_response_topic(gw_id: str = "+", sink_id: str = "+") -> str:
    # No req_id in the topic: a response is matched to its request by the
    # req_id carried inside the protobuf payload.
    return f"gw-response/send_data/{gw_id}/{sink_id}"
