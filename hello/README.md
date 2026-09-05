# hello

A Wirepas "Hello World" that runs **without any hardware**.

The Wirepas gateway stack ends at an MQTT broker, and everything above that
line speaks the [Gateway-to-Backend API v2](https://github.com/wirepas/backend-apis/tree/master/gateway_to_backend)
(Protocol Buffers over MQTT). So a backend application can be written and
tested against a fake gateway that publishes the very same messages a real one
would.

```
┌─────────────────────────────────────────────────────────────┐
│ Real deployment                     │ This example          │
│                                     │                       │
│  [ backend application ]            │  app.py               │
│           ▲                         │      ▲                │
│           │ MQTT (protobuf)         │      │ MQTT (protobuf)│
│           ▼                         │      ▼                │
│  [ MQTT broker ]                    │  Mosquitto (Docker)   │
│           ▲                         │      ▲                │
│           │                         │      │                │
│  [ Transport Service ] (Python)     │      │                │
│           ▲                         │      │                │
│           │ D-Bus                   │      │  gateway_mock.py
│  [ Sink Service ] (C)               │      │  fakes all of  │
│           ▲                         │      │  this          │
│           │ serial (/dev/ttyACM0)   │      │                │
│  [ USB dongle / Sink FW ]           │      │                │
│           ▲                         │      │                │
│           │ 2.4GHz radio            │      │                │
│  [ mesh nodes ]                     │      ▼                │
└─────────────────────────────────────────────────────────────┘
```

`app.py` is the part you keep when real hardware arrives: it only talks MQTT
and never touches D-Bus, the serial link or the dongle.

## Run it

Three terminals, in this order.

```bash
# 1. MQTT broker
docker compose up -d

# 2. the backend application (start it first so it sees every uplink)
uv sync
uv run app.py

# 3. the fake gateway
uv run gateway_mock.py
```

`app.py` prints something like:

```
[app] connected to localhost:1883
[app] gateway gw-hello is ONLINE
[app] downlink sent to node 1001 via gw-hello/sink0
[app] downlink accepted by gw-hello: GW_RES_OK
[app] uplink from node 1001 via gw-hello/sink0 (2 hops, 120 ms): b'hello #1'
[app] uplink from node 1001 via gw-hello/sink0 (2 hops, 120 ms): b'hello #2'
```

Stop the broker with `docker compose down`.

## What happens

| Direction | Topic | Message |
|---|---|---|
| gateway → backend | `gw-event/status/<gw_id>` | `StatusEvent` — published **retained**, so a backend that connects later immediately learns the gateway exists. The MQTT last will publishes `OFFLINE` if the gateway dies. |
| gateway → backend | `gw-event/received_data/<gw_id>/<sink_id>/<network_address>/<src_ep>/<dst_ep>` | `ReceivedDataEvent` — an uplink packet from a mesh node, every 5 s here. |
| backend → gateway | `gw-request/send_data/<gw_id>/<sink_id>` | `SendDataRequest` — a downlink packet for a node. `app.py` sends one as soon as it sees a gateway go online. |
| gateway → backend | `gw-response/send_data/<gw_id>/<sink_id>/<req_id>` | `SendDataResponse` — the gateway accepted the request (it says nothing about the packet reaching the node). |

Details worth noticing:

- **Endpoints** (`src_ep` / `dst_ep`) are the Wirepas equivalent of port
  numbers. An application picks a pair and both ends agree on what the payload
  bytes mean; the payload itself is opaque to the stack.
- **Addresses**: `0` is the sink, so `dst=0` on an uplink means "to the sink".
- **Topic wildcards** are how a backend discovers things: `app.py` subscribes
  with `+` in every position, so it works with any number of gateways and
  sinks without configuration.
- The retained status message survives a broker restart of the subscriber, so
  on the second run you may see a stale `OFFLINE` before the fresh `ONLINE`.

## Files

| File | Role |
|---|---|
| [app.py](app.py) | The backend application — hardware-independent. |
| [gateway_mock.py](gateway_mock.py) | Fake gateway: fakes the mesh, dongle, sink service and transport service. |
| [common.py](common.py) | Broker settings, identifiers and topic helpers shared by both. |
| [compose.yaml](compose.yaml) | Mosquitto broker on `localhost:1883`, anonymous access. |

`MQTT_HOST` and `MQTT_PORT` override the broker location, e.g. to point
`app.py` at a real gateway:

```bash
MQTT_HOST=192.168.1.10 uv run app.py
```

## Dependencies

- [`wirepas-mesh-messaging`](https://pypi.org/project/wirepas-mesh-messaging/) —
  the official protobuf message classes (`ReceivedDataEvent`, `SendDataRequest`, …).
- [`paho-mqtt`](https://pypi.org/project/paho-mqtt/) — the MQTT client.

Wirepas also publishes
[`wirepas-mqtt-library`](https://pypi.org/project/wirepas-mqtt-library/), which
wraps both of these in a higher-level client. This example deliberately uses
the raw messages so the topics and the encoding stay visible.
