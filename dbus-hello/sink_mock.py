"""A fake Wirepas sink service.

The real sink service (C, https://github.com/wirepas/gateway/tree/master/sink_service)
talks to a USB dongle over UART and exposes it on the D-Bus system bus. This
module exposes the same D-Bus interface without any hardware, so the *real*
transport service can run on top of it and publish to MQTT.

The interface below is transcribed from the sd-bus vtables in
sink_service/source/{config,data,otap}.c -- the signatures must match exactly
or the transport service's pydbus proxies fail.

    uv run sink_mock.py
"""

import asyncio
import os
import time

from dbus_fast import BusType, PropertyAccess
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_property, method, signal

SINK_ID = os.environ.get("SINK_ID", "sink0")
BUS_NAME = f"com.wirepas.sink.{SINK_ID}"
OBJECT_PATH = "/com/wirepas/sink"

# What the fake mesh looks like.
NODE_ADDRESS = 1001
NETWORK_ADDRESS = 0x123456
NETWORK_CHANNEL = 5
UPLINK_INTERVAL_S = 5

# StackStatus is a bit field and bit 0 means "stopped", so 0 == running.
STACK_RUNNING = 0
STACK_STOPPED = 1


class ConfigInterface(ServiceInterface):
    """com.wirepas.sink.config1 -- node and network configuration."""

    def __init__(self):
        super().__init__("com.wirepas.sink.config1")
        self._stack_status = STACK_RUNNING
        self._node_address = NODE_ADDRESS
        self._network_address = NETWORK_ADDRESS
        self._network_channel = NETWORK_CHANNEL
        self._node_role = 1  # sink
        self._sink_cost = 0
        self._channel_map = 0
        self._app_config = (1, 60, bytes(8))  # seq, diag interval, data

    # --- Read-only properties: what the stack reports about itself ---------

    @dbus_property(access=PropertyAccess.READ)
    def StackProfile(self) -> "q":
        return 1

    @dbus_property(access=PropertyAccess.READ)
    def HwMagic(self) -> "q":
        return 3

    @dbus_property(access=PropertyAccess.READ)
    def MaxMtu(self) -> "y":
        return 102

    @dbus_property(access=PropertyAccess.READ)
    def ChRangeMin(self) -> "y":
        return 1

    @dbus_property(access=PropertyAccess.READ)
    def ChRangeMax(self) -> "y":
        return 40

    @dbus_property(access=PropertyAccess.READ)
    def ACRangeMin(self) -> "q":
        return 2000

    @dbus_property(access=PropertyAccess.READ)
    def ACRangeMax(self) -> "q":
        return 8000

    @dbus_property(access=PropertyAccess.READ)
    def ACRangeMinCur(self) -> "q":
        return 2000

    @dbus_property(access=PropertyAccess.READ)
    def ACRangeMaxCur(self) -> "q":
        return 8000

    @dbus_property(access=PropertyAccess.READ)
    def CurrentAC(self) -> "q":
        return 4000

    @dbus_property(access=PropertyAccess.READ)
    def PDUBufferSize(self) -> "y":
        return 16

    @dbus_property(access=PropertyAccess.READ)
    def AppConfigMaxSize(self) -> "q":
        return 80

    @dbus_property(access=PropertyAccess.READ)
    def FirmwareVersion(self) -> "aq":
        return [5, 4, 0, 0]

    @dbus_property(access=PropertyAccess.READ)
    def CipherKeySet(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def AuthenticationKeySet(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def StackStatus(self) -> "y":
        return self._stack_status

    # --- Writable properties: what a backend can reconfigure ---------------

    @dbus_property()
    def NodeAddress(self) -> "u":
        return self._node_address

    @NodeAddress.setter
    def NodeAddress(self, value: "u"):
        print(f"[sink] NodeAddress <- {value}")
        self._node_address = value

    @dbus_property()
    def NodeRole(self) -> "y":
        return self._node_role

    @NodeRole.setter
    def NodeRole(self, value: "y"):
        print(f"[sink] NodeRole <- {value}")
        self._node_role = value

    @dbus_property()
    def NetworkAddress(self) -> "u":
        return self._network_address

    @NetworkAddress.setter
    def NetworkAddress(self, value: "u"):
        print(f"[sink] NetworkAddress <- {value:#x}")
        self._network_address = value

    @dbus_property()
    def NetworkChannel(self) -> "y":
        return self._network_channel

    @NetworkChannel.setter
    def NetworkChannel(self, value: "y"):
        print(f"[sink] NetworkChannel <- {value}")
        self._network_channel = value

    @dbus_property()
    def SinkCost(self) -> "y":
        return self._sink_cost

    @SinkCost.setter
    def SinkCost(self, value: "y"):
        print(f"[sink] SinkCost <- {value}")
        self._sink_cost = value

    @dbus_property()
    def ChannelMap(self) -> "u":
        return self._channel_map

    @ChannelMap.setter
    def ChannelMap(self, value: "u"):
        self._channel_map = value

    # --- Methods -----------------------------------------------------------

    @method()
    def SetStackState(self, start: "b") -> "b":
        """Start or stop the stack. A real sink reboots the node here."""
        self._stack_status = STACK_RUNNING if start else STACK_STOPPED
        print(f"[sink] stack {'started' if start else 'stopped'}")
        if start:
            self.StackStarted()
        else:
            self.StackStopped()
        return True

    @method()
    def GetAppConfig(self) -> "yqay":
        seq, interval, data = self._app_config
        return [seq, interval, data]

    @method()
    def SetAppConfig(self, seq: "y", interval: "q", data: "ay") -> "b":
        print(f"[sink] app config <- seq={seq} interval={interval} {bytes(data)!r}")
        self._app_config = (seq, interval, bytes(data))
        return True

    @method()
    def SetACRange(self, min_ac: "q", max_ac: "q") -> "b":
        print(f"[sink] AC range <- {min_ac}..{max_ac}")
        return True

    @method()
    def GetConfigDataContent(self) -> "a(qay)":
        return []

    @method()
    def GetConfigDataItem(self, endpoint: "q") -> "ay":
        return b""

    @method()
    def SetConfigDataItem(self, endpoint: "q", payload: "ay"):
        print(f"[sink] config data item {endpoint} <- {bytes(payload)!r}")

    @method()
    def ClearCipherKey(self):
        pass

    @method()
    def ClearAuthenticationKey(self):
        pass

    # --- Signals -----------------------------------------------------------

    @signal()
    def StackStarted(self):
        """The transport service re-reads the whole config when this fires."""

    @signal()
    def StackStopped(self):
        pass


class DataInterface(ServiceInterface):
    """com.wirepas.sink.data1 -- the actual mesh traffic."""

    def __init__(self):
        super().__init__("com.wirepas.sink.data1")

    @method()
    def SendMessage(
        self,
        dst: "u",
        src_ep: "y",
        dst_ep: "y",
        buffering_delay: "u",
        qos: "y",
        is_unack_csma_ca: "b",
        hop_limit: "y",
        data: "ay",
    ) -> "u":
        """Downlink. A real sink hands this to the dongle over UART.

        The return value is a sink service return code; 0 means accepted.
        """
        print(
            f"[sink] downlink to node {dst} ep {src_ep}/{dst_ep}: {bytes(data)!r}"
        )
        return 0

    @signal()
    def MessageReceived(
        self,
        timestamp: "t",
        src: "u",
        dst: "u",
        src_ep: "y",
        dst_ep: "y",
        travel_time: "u",
        qos: "y",
        hop_count: "y",
        data: "ay",
    ) -> "tuuyyuyyay":
        """Uplink. The transport service turns this into a ReceivedDataEvent."""
        return [
            timestamp,
            src,
            dst,
            src_ep,
            dst_ep,
            travel_time,
            qos,
            hop_count,
            data,
        ]


class OtapInterface(ServiceInterface):
    """com.wirepas.sink.otap1 -- over-the-air firmware update status.

    Only the properties the transport service reads while building a config
    message are implemented; nothing here actually updates any firmware.
    """

    def __init__(self):
        super().__init__("com.wirepas.sink.otap1")

    @dbus_property(access=PropertyAccess.READ)
    def StoredLen(self) -> "u":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def StoredCrc(self) -> "q":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def StoredSeq(self) -> "y":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def StoredStatus(self) -> "y":
        return 0  # SCRATCHPAD_STATUS_SUCCESS

    @dbus_property(access=PropertyAccess.READ)
    def StoredType(self) -> "y":
        return 0  # SCRATCHPAD_TYPE_BLANK

    @dbus_property(access=PropertyAccess.READ)
    def ProcessedLen(self) -> "u":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def ProcessedCrc(self) -> "q":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def ProcessedSeq(self) -> "y":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def FirmwareAreaId(self) -> "u":
        return 0

    @method()
    def GetTargetScratchpad(self) -> "yqyy":
        return [0, 0, 0, 0]

    @method()
    def SetTargetScratchpad(
        self, action: "y", target_crc: "q", target_seq: "y", param: "y"
    ) -> "b":
        return True

    @method()
    def ClearLocalScratchpad(self):
        pass


async def generate_uplinks(data: DataInterface) -> None:
    """Pretend a node keeps sending packets into the mesh."""
    for counter in range(1, 1 << 30):
        payload = f"hello #{counter}".encode()
        data.MessageReceived(
            int(time.time() * 1000),
            NODE_ADDRESS,
            0,  # 0 is the sink: this packet travelled uplink
            1,  # src_ep
            1,  # dst_ep
            120,  # travel_time_ms
            0,  # qos
            2,  # hop_count
            payload,
        )
        print(f"[sink] uplink from node {NODE_ADDRESS}: {payload!r}")
        await asyncio.sleep(UPLINK_INTERVAL_S)


async def main() -> None:
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    config = ConfigInterface()
    data = DataInterface()
    otap = OtapInterface()

    # All three interfaces live on the same object, exactly as in sink_service.
    bus.export(OBJECT_PATH, config)
    bus.export(OBJECT_PATH, data)
    bus.export(OBJECT_PATH, otap)

    await bus.request_name(BUS_NAME)
    print(f"[sink] owning {BUS_NAME} at {OBJECT_PATH}")

    # The transport service discovers sinks by bus name, then waits for this
    # signal to read the configuration.
    config.StackStarted()

    await generate_uplinks(data)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[sink] stopping")
