"""The backend side of the Wirepas hello example.

This is the code you would keep when you swap the fake gateway for real
hardware: it only talks MQTT to the broker and never touches D-Bus, the serial
link or the dongle.

    uv run app.py
"""

import paho.mqtt.client as mqtt
import wirepas_mesh_messaging as wmm

from common import (
    DESTINATION_ENDPOINT,
    MQTT_HOST,
    MQTT_PORT,
    NODE_ADDRESS,
    SOURCE_ENDPOINT,
    received_data_topic,
    send_data_request_topic,
    send_data_response_topic,
    status_topic,
)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        print(f"[app] connection failed: {reason_code}")
        return

    print(f"[app] connected to {MQTT_HOST}:{MQTT_PORT}")
    # The wildcards come from common.py: subscribe to every gateway and sink.
    client.subscribe(
        [
            (status_topic(), 1),
            (received_data_topic(), 1),
            (send_data_response_topic(), 1),
        ]
    )


def on_status(client, msg) -> None:
    event = wmm.StatusEvent.from_payload(msg.payload)
    print(f"[app] gateway {event.gw_id} is {event.state.name}")

    if event.state is wmm.GatewayState.ONLINE:
        say_hello(client, event.gw_id)


def on_received_data(client, msg) -> None:
    event = wmm.ReceivedDataEvent.from_payload(msg.payload)
    print(
        f"[app] uplink from node {event.source_address} "
        f"via {event.gw_id}/{event.sink_id} "
        f"({event.hop_count} hops, {event.travel_time_ms} ms): "
        f"{event.data_payload!r}"
    )


def on_send_data_response(client, msg) -> None:
    response = wmm.SendDataResponse.from_payload(msg.payload)
    print(f"[app] downlink accepted by {response.gw_id}: {response.res.name}")


def on_message(client, userdata, msg):
    handlers = {
        "gw-event/status": on_status,
        "gw-event/received_data": on_received_data,
        "gw-response/send_data": on_send_data_response,
    }
    for prefix, handler in handlers.items():
        if msg.topic.startswith(prefix):
            try:
                handler(client, msg)
            except wmm.GatewayAPIParsingException as err:
                print(f"[app] cannot parse message on {msg.topic}: {err}")
            return

    print(f"[app] ignoring {msg.topic}")


def say_hello(client: mqtt.Client, gw_id: str, sink_id: str = "sink0") -> None:
    """Send a downlink packet to a node through the given gateway."""
    request = wmm.SendDataRequest(
        dest_add=NODE_ADDRESS,
        src_ep=SOURCE_ENDPOINT,
        dst_ep=DESTINATION_ENDPOINT,
        qos=0,
        payload=b"hello from the backend",
        sink_id=sink_id,
    )
    client.publish(
        send_data_request_topic(gw_id, sink_id), request.payload, qos=1
    )
    print(f"[app] downlink sent to node {NODE_ADDRESS} via {gw_id}/{sink_id}")


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[app] stopping")
        client.disconnect()


if __name__ == "__main__":
    main()
