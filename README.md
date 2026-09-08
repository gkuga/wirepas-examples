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
  friends), but the firmware is Wirepas' own 2.4GHz mesh stack. See
  [Wirepas and Bluetooth](#wirepas-and-bluetooth) below.
- The gateway stack is open source and Apache-2.0:
  [wirepas/gateway](https://github.com/wirepas/gateway) (sink service in C,
  transport service in Python) and
  [wirepas/c-mesh-api](https://github.com/wirepas/c-mesh-api) (the serial
  protocol library).
- There is **no official emulator or mock** for any layer; these examples are
  written from scratch against the upstream sources.

## Wirepas and Bluetooth

The dongles are BLE-capable chips, so the two stacks get confused for each
other. They are unrelated, and lining them up explains the shape of everything
in this repo.

### Bluetooth

```
┌─ Profiles ─────────  HID / A2DP / HFP   |   GATT-based profiles
│
├─ Host ─────────────┐
│  Classic: RFCOMM  SDP  AVDTP            │   LE: ATT/GATT  SMP
│                     L2CAP  (multiplexes by CID/PSM)
│                      GAP
├──────────── HCI ────────────────────────  ← the split the spec defines
│
└─ Controller ───────  Link Manager (LMP) / Link Layer
                       Baseband
                       PHY (2.4GHz)
```

The spec draws the chip/host line at HCI, *below* L2CAP. The controller
implements the radio and the link layer; **everything above that is the host's
problem.** Linux then splits the host part again:

```
  application ──── D-Bus (org.bluez) ───┐
                                        ▼
                                bluetoothd  (userspace)
                                  GATT, SDP, pairing policy, profiles
                                        │  AF_BLUETOOTH sockets
  ──────────────────────────────────────┼─────────────── user / kernel
                                        ▼
                          L2CAP / SMP / SCO / BNEP  (kernel)
                                    hci_dev
                              btusb / hci_uart      (kernel)
```

Bluetooth needs kernel code for four reasons, and none of them apply to
Wirepas:

- **Multiplexing.** One controller, several users at once — a BLE mouse, an
  A2DP headset, an app speaking GATT. A bare tty belongs to whoever opened it;
  an `AF_BLUETOOTH` socket hands L2CAP CIDs out to many processes.
- **Other kernel subsystems.** A Bluetooth keyboard has to appear as an evdev
  device, BNEP as a `bnep0` netdev, SCO as audio. The data path runs through
  the kernel because its destination is already there.
- **Privilege.** Raw HCI is total control of the radio, address spoofing
  included. In the kernel it sits behind `CAP_NET_ADMIN`, and link keys never
  have to reach userspace.
- **Transport variety.** USB, UART (H4/H5), SDIO — `hci_dev` normalizes them.

None of it is strictly necessary. **HCI User Channel** lets a userspace stack
(BTstack, NimBLE) take a controller exclusively and bypass the kernel
completely. Kernel Bluetooth is an OS-integration decision, not a physical
requirement.

### Wirepas

```
┌─ backend application ──────────────────────
│        ▲ MQTT (protobuf)
│  Transport Service (Python)
│        ▲ D-Bus  com.wirepas.sink
│  Sink Service (C) + c-mesh-api
├─────── Dual-MCU API (serial) ──────────────  ← the split
│
└─ dongle firmware ─────────────────────────
     Data layer      endpoints address the app, MTU 102
     Routing layer   cost-based tree, self-healing
     MAC             time-sliced + CSMA-CA
     PHY             2.4GHz
```

The same picture cut in a different place. Wirepas splits *above* the stack
rather than below it: MAC and routing live in the dongle's firmware, and the
host is left with nothing to implement but command framing.

For the mesh layers the fairer comparison is Bluetooth Mesh — a spec layered on
BLE's advertising bearer — and it works differently too: managed flooding,
where every node rebroadcasts and nobody keeps a route, against Wirepas nodes
that each pick a parent by cost and form a tree.

### Side by side

| | Bluetooth | Wirepas |
|---|---|---|
| Medium access | Link Layer, connection-oriented | time-sliced + CSMA-CA |
| Multi-hop | Bluetooth Mesh: managed flooding | routing layer: cost-based tree |
| Multiplexing | L2CAP CID / PSM | — |
| Addressing an app | ATT handles, mesh models | endpoints (`src_ep` / `dst_ep`) |
| Joining | pairing / provisioning | network address, channel, key |
| **Chip / host split** | **HCI**, below L2CAP | **Dual-MCU API**, above everything |
| Host-side stack | L2CAP and up | practically nothing |
| Kernel driver | `btusb` + `bluetooth.ko` | `cdc_acm`, i.e. a plain tty |
| Daemon | `bluetoothd` | `sink_service` |
| D-Bus name | `org.bluez` | `com.wirepas.sink.sinkN` |
| Ends at | the D-Bus API | MQTT and protobuf, two layers higher |

Two things fall out of that table, and both shape these examples.

**No driver is required.** The mesh stack runs entirely on the dongle, so the
host is talking to a network processor over a serial line, closer to an AT
modem than to a protocol stack. The kernel contributes a tty and nothing else.
`sink_service` plus `c-mesh-api` play the part BlueZ plays, and even land in
the same place — a daemon publishing the radio on the system bus.

**Wirepas keeps going upward.** BlueZ stops at `org.bluez` and leaves the rest
to the application, while Wirepas ships a transport service and a backend API
above its bus. It is designed as a gateway product rather than as an OS
facility. That is why this repo has two examples instead of one.

The analogies carry over to the mocks: faking `com.wirepas.sink` in
[dbus-hello](dbus-hello/) is faking `org.bluez`, and the virtual serial port in
[#1](https://github.com/gkuga/wirepas-examples/issues/1) is `hci_vhci` — except
that a PTY is enough, because there is nothing in the kernel to displace.

### The serial link need not be a UART

The Dual-MCU API fixes the framing and the serial parameters (8N1, 125000 bps
by default; 115200 and 1000000 also work) but says nothing about the physical
layer. There is no native-USB variant of the protocol — anything that gives the
host a byte stream will do:

| Form | Device node | Example |
|---|---|---|
| USB-serial bridge | `/dev/ttyUSB0` | FTDI or CP2102 on the board |
| Debug probe | `/dev/ttyACM0` | J-Link OB on an nRF52 DK |
| Real UART pins | `/dev/ttyAMA0` | module wired to a Raspberry Pi header |

`c-mesh-api` opens a tty and sets termios, so it cannot tell them apart, and
upstream's own test command uses a USB device:
`WPC_SERIAL_PORT=/dev/ttyACM0 WPC_BAUD_RATE=125000`.

Two practical differences. The baud rate has to match on a real UART, but is
ignored by a chip presenting USB CDC itself. And FTDI's 16 ms default latency
timer hurts a request/response protocol with timeouts — `echo 1 | sudo tee
/sys/bus/usb-serial/devices/ttyUSB0/latency_timer` — whereas `cdc_acm` has no
such knob and no such problem.
