# wirepas-examples

Small, self-contained experiments for getting familiar with
[Wirepas Mesh](https://wirepas.com/) and its gateway stack.
Each directory is a uv project.

Wirepas splits a gateway into layers, and each example fakes everything below
one of them — so you can work at that layer without hardware.

```
  [ backend application ]
           ▲ MQTT (protobuf)          ← hello: fakes everything below this
  [ Transport Service ] (Python)
           ▲ D-Bus                    ← dbus-hello: fakes everything below this
  [ Sink Service ] (C)
           ▲ serial (Dual-MCU API)    ← issue #1: not built yet
  [ USB dongle / Sink FW ]
           ▲ 2.4GHz radio
  [ mesh nodes ]
```

## Examples

| Name | Fakes | Description |
|---|---|---|
| [hello](hello/) | everything below MQTT | A backend app and a fake gateway exchanging Gateway-to-Backend API v2 messages |
| [dbus-hello](dbus-hello/) | everything below D-Bus | A fake sink service, with the **real** transport service running on top of it |

## Next steps

- [ ] [#1](https://github.com/gkuga/wirepas-examples/issues/1) — emulate the
  Dual-MCU API over a virtual serial port, so the real `sink_service` and
  `c-mesh-api` run without a dongle.

## How to run

This repo uses [uv](https://docs.astral.sh/uv/). Enter an example directory and
follow its README.

```bash
cd hello
uv sync
```

Run one example at a time: both bind port 1883 and both use the gateway id
`gw-hello`.

## Notes on Wirepas

- **It is not Bluetooth.** The dongles use BLE-capable chips (nRF52 and
  friends), but the firmware is Wirepas' own 2.4GHz mesh stack.
- The gateway stack is open source and Apache-2.0:
  [wirepas/gateway](https://github.com/wirepas/gateway) (sink service in C,
  transport service in Python) and
  [wirepas/c-mesh-api](https://github.com/wirepas/c-mesh-api) (the UART
  protocol library).
- There is **no official emulator or mock** for any layer; these examples are
  written from scratch against the upstream sources.
