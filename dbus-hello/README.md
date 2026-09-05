# dbus-hello

One layer below [hello](../hello/): a fake **sink service** on D-Bus, with the
**real, unmodified Wirepas transport service** running on top of it.

In [hello](../hello/) everything below MQTT was faked. Here only the bottom
piece is — the USB dongle and the C sink service that drives it. Everything
above is the genuine article, pulled from the official Docker image.

```
┌──────────────────────────────┬──────────────────────────────┐
│ Real deployment              │ This example                 │
│                              │                              │
│  [ backend application ]     │  ../hello/app.py             │
│           ▲ MQTT             │           ▲ MQTT             │
│  [ MQTT broker ]             │  Mosquitto (Docker)          │
│           ▲                  │           ▲                  │
│  [ Transport Service ]       │  the real transport service, │
│    (Python)                  │  official image, unmodified  │
│           ▲ D-Bus            │           ▲ D-Bus            │
│  [ Sink Service ] (C)        │  sink_mock.py  ← the only    │
│           ▲ serial           │                  fake left    │
│  [ USB dongle / Sink FW ]    │                              │
│           ▲ 2.4GHz radio     │                              │
│  [ mesh nodes ]              │                              │
└──────────────────────────────┴──────────────────────────────┘
```

Because the transport service is real, this example proves something
[hello](../hello/) cannot: that the D-Bus contract is right. If `sink_mock.py`
gets a signature wrong, the transport service fails exactly as it would against
a broken sink.

## Run it

```bash
docker compose up -d
docker compose logs -f
```

Then watch the MQTT side with the backend app from the other example:

```bash
cd ../hello
uv run app.py
```

```
[app] connected to localhost:1883
[app] gateway gw-hello is ONLINE
[app] downlink sent to node 1001 via gw-hello/sink0
[app] downlink accepted by gw-hello: GW_RES_OK
[app] uplink from node 1001 via gw-hello/sink0 (2 hops, 120 ms): b'hello #62'
```

That uplink started as a D-Bus signal from `sink_mock.py`, was turned into a
protobuf `ReceivedDataEvent` by the real transport service, and arrived over
MQTT. The downlink went the other way and shows up in the sink mock's log:

```bash
docker compose logs sink-mock | grep downlink
# [sink] downlink to node 1001 ep 1/1: b'hello from the backend'
```

Stop everything with `docker compose down`.

> **Do not run this and [hello](../hello/) at the same time.** Both bind port
> 1883 and both use the gateway id `gw-hello`. Two gateways sharing an id on one
> broker knock each other off the broker in a loop, each firing the other's last
> will — the status flaps between `ONLINE` and `OFFLINE` forever. Gateway ids
> must be unique per broker in real deployments too.

## Services

| Service | What it stands for |
|---|---|
| `dbus` | The D-Bus system bus. On a real gateway this is just the host's bus. |
| `sink-mock` | **Our code.** Replaces the C sink service and the dongle behind it. |
| `transport` | The real transport service, `wirepas/gateway_transport_service:v1.6.2`, unmodified. |
| `mosquitto` | The MQTT broker. |

The three D-Bus containers share the bus socket through a named volume mounted
at `/var/run/dbus`, which is how the [official
compose file](https://github.com/wirepas/gateway/blob/master/docker/docker-compose/single_transport/docker-compose.yml)
wires a real gateway too. The only change is that `sink-mock` takes the place of
their `sink-service`.

## The D-Bus contract

`sink_mock.py` is a transcription of the sd-bus vtables in the real sink
service. Each sink owns a bus name `com.wirepas.sink.sinkN` and exports one
object, `/com/wirepas/sink`, carrying three interfaces:

| Interface | Source | Contents |
|---|---|---|
| `com.wirepas.sink.data1` | [data.c](https://github.com/wirepas/gateway/blob/master/sink_service/source/data.c) | `SendMessage` method (downlink), `MessageReceived` signal (uplink) |
| `com.wirepas.sink.config1` | [config.c](https://github.com/wirepas/gateway/blob/master/sink_service/source/config.c) | Node/network configuration as properties, `StackStarted` / `StackStopped` signals |
| `com.wirepas.sink.otap1` | [otap.c](https://github.com/wirepas/gateway/blob/master/sink_service/source/otap.c) | Scratchpad (over-the-air firmware update) status |

The two that carry mesh traffic:

```
SendMessage(u dst, y src_ep, y dst_ep, u delay, y qos, b unack_csma_ca, y hop_limit, ay data) -> u
MessageReceived(t timestamp, u src, u dst, y src_ep, y dst_ep, u travel_time, y qos, y hop_count, ay data)
```

These are the same two operations that appear one layer up as
`SendDataRequest` and `ReceivedDataEvent`.

Details worth knowing:

- **Signatures must match exactly.** The transport service builds pydbus
  proxies from introspection; a wrong type is a runtime failure, not a warning.
- **`StackStatus` is a bit field where bit 0 means *stopped*,** so `0` means the
  stack is running. The transport service reads it as `(StackStatus & 0x01) == 0`.
- **Discovery is by bus name.** The transport service calls `ListNames()`,
  picks up anything starting with `com.wirepas.sink.`, and then watches
  `NameOwnerChanged` — so starting a second mock with `SINK_ID=sink1` makes a
  second sink appear with no configuration anywhere.
- **`StackStarted` triggers a config read.** The mock emits it once at startup;
  the transport service responds by reading every property and publishing a
  status message.

### The uid gotcha

D-Bus policy matches clients by **user name**, and `dbus-daemon` resolves each
client's UID through its own `/etc/passwd`. A client whose UID does not exist
in the bus container is refused with a bare `The connection is closed` — no
hint about why.

That is why [dbus/Dockerfile](dbus/Dockerfile) creates a `wirepas` user it
never runs anything as, and why every container here uses uid 1000. Upstream's
[dbus service image](https://github.com/wirepas/gateway/blob/master/docker/dbus_service/Dockerfile)
does the same thing for the same reason.

## Files

| File | Role |
|---|---|
| [sink_mock.py](sink_mock.py) | The fake sink service. |
| [compose.yaml](compose.yaml) | The four services above. |
| [dbus/Dockerfile](dbus/Dockerfile) | The system bus. |
| [dbus/com.wirepas.sink.conf](dbus/com.wirepas.sink.conf) | Bus policy, same as upstream: only `wirepas` may own a sink name. |
| [Dockerfile](Dockerfile) | The sink mock, uv-managed. |

## Dependencies

[`dbus-fast`](https://pypi.org/project/dbus-fast/) — a pure-Python D-Bus
library, so this project installs with `uv` anywhere. The real transport
service uses `pydbus`, which needs PyGObject and GLib; that is fine inside its
own image but painful to install by hand.

Note that **D-Bus means Linux**: unlike [hello](../hello/), `sink_mock.py`
cannot run directly on macOS. Everything here goes through Docker.
