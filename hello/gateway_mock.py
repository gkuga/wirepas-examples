"""A fake Wirepas gateway.

It stands in for the whole hardware side of the stack -- the mesh nodes, the
USB dongle, the sink service and the transport service -- and speaks the same
MQTT Gateway-to-Backend API v2 a real gateway does. That is enough to develop
and test a backend application without any hardware.

    uv run gateway_mock.py
"""

import itertools
import threading
import time

import paho.mqtt.client as mqtt
import wirepas_mesh_messaging as wmm

from common import (
    DESTINATION_ENDPOINT,
    GW_ID,
    MQTT_HOST,
    MQTT_PORT,
    NETWORK_ADDRESS,
    NODE_ADDRESS,
    SINK_ID,
    SOURCE_ENDPOINT,
    received_data_topic,
    send_data_request_topic,
    send_data_response_topic,
    status_topic,
)

PUBLISH_INTERVAL_S = 5


def publish_status(client: mqtt.Client, state: wmm.GatewayState) -> None:
    """Announce the gateway state.

    Status is published retained so a backend that connects later immediately
    learns which gateways exist.
    """
    event = wmm.StatusEvent(GW_ID, state)
    client.publish(status_topic(GW_ID), event.payload, qos=1, retain=True)
    print(f"[gateway] status -> {state.name}")


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        print(f"[gateway] connection failed: {reason_code}")
        return

    print(f"[gateway] connected to {MQTT_HOST}:{MQTT_PORT} as {GW_ID}")
    publish_status(client, wmm.GatewayState.ONLINE)
    client.subscribe(send_data_request_topic(GW_ID, SINK_ID), qos=1)
    userdata["connected"].set()


def on_message(client, userdata, msg):
    """Handle a downlink request from the backend.

    A real gateway would forward the payload to the sink over the serial link
    and let the mesh route it to the destination node. Here we only decode it
    and answer with a success response.
    """
    try:
        request = wmm.SendDataRequest.from_payload(msg.payload)
    except wmm.GatewayAPIParsingException as err:
        print(f"[gateway] cannot parse request on {msg.topic}: {err}")
        return

    print(
        f"[gateway] downlink to node {request.destination_address} "
        f"ep {request.source_endpoint}/{request.destination_endpoint}: "
        f"{request.data_payload!r}"
    )

    response = wmm.SendDataResponse(
        request.req_id, GW_ID, wmm.GatewayResultCode.GW_RES_OK, SINK_ID
    )
    client.publish(send_data_response_topic(GW_ID, SINK_ID), response.payload, qos=1)


def publish_received_data(client: mqtt.Client, counter: int) -> None:
    """Pretend a node sent an uplink packet through the mesh."""
    payload = f"hello #{counter}".encode()
    event = wmm.ReceivedDataEvent(
        gw_id=GW_ID,
        sink_id=SINK_ID,
        rx_time_ms_epoch=int(time.time() * 1000),
        src=NODE_ADDRESS,
        dst=0,  # 0 is the sink, i.e. the packet travelled uplink
        src_ep=SOURCE_ENDPOINT,
        dst_ep=DESTINATION_ENDPOINT,
        travel_time_ms=120,
        qos=0,
        data=payload,
        hop_count=2,
        network_address=NETWORK_ADDRESS,
    )
    client.publish(
        received_data_topic(
            GW_ID, SINK_ID, NETWORK_ADDRESS, SOURCE_ENDPOINT, DESTINATION_ENDPOINT
        ),
        event.payload,
        qos=1,
    )
    print(f"[gateway] uplink from node {NODE_ADDRESS}: {payload!r}")


def main() -> None:
    connected = threading.Event()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=GW_ID,
        userdata={"connected": connected},
    )
    client.on_connect = on_connect
    client.on_message = on_message

    # If the gateway dies, the broker publishes the offline status on its
    # behalf. A real transport service does exactly the same.
    offline = wmm.StatusEvent(GW_ID, wmm.GatewayState.OFFLINE)
    client.will_set(status_topic(GW_ID), offline.payload, qos=1, retain=True)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    connected.wait()

    try:
        for counter in itertools.count(1):
            publish_received_data(client, counter)
            time.sleep(PUBLISH_INTERVAL_S)
    except KeyboardInterrupt:
        print("\n[gateway] stopping")
    finally:
        publish_status(client, wmm.GatewayState.OFFLINE)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
