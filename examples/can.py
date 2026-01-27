"""Example script to handle CAN from FreeWili with a Neptune Orca."""

import time

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import CANData, EventDataType, EventType


def event_handler(event_type: EventType, frame: ResponseFrame, data: EventDataType) -> None:
    """Handle events from FreeWili."""
    match event_type:
        case EventType.CANRX0:
            data: CANData = data  # type:ignore
            print(f"CAN0 RX Event: {data}")
        case EventType.CANRX1:
            data: CANData = data  # type: ignore
            print(f"CAN1 RX Event: {data}")
        case EventType.CANTX0:
            data: CANData = data  # type: ignore
            print(f"CAN0 TX Event: {data}")
        case EventType.CANTX1:
            data: CANData = data  # type: ignore
            print(f"CAN1 TX Event: {data}")
        case _:
            # Handle other event types as needed
            if data:
                print(f"{event_type}: Event Data: {data}")
            else:
                print(f"No data for this {event_type}.")


with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
    fw: FreeWili = fw  # type: ignore
    print(f"Connected to FreeWili {fw}")

    # v87 firmware currently just returns "Ok" for CAN register reads
    # print(fw.can_read_registers(0, 0, 10).expect("Failed to read CAN0 registers"))
    # fw.can_write_registers(0, 0, 4, 0x90770).expect("Failed to write CAN0 registers")

    fw.set_event_callback(event_handler)
    # Enable CAN events
    for channel in (0, 1):
        fw.can_enable_streaming(channel, True).expect("Failed to enable CAN streaming")
    # Set up a periodic CAN message on channel 0, every 100 ms
    fw.can_set_transmit_periodic(
        0, 0, 100_000, 0x55, True, True, bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
    ).expect("Failed to set periodic CAN message on channel 0")
    # Enable the periodic CAN message, this is redundant as can_set_transmit_periodic enables it by default
    fw.can_enable_transmit_periodic(0, True).expect("Failed to enable periodic CAN message on channel 0")

    # Setup CAN RX filters
    fw.can_set_rx_filter(0, 0, True, 0xFF, 0x123, 0, 0, 0, 0).expect("Failed to set CAN0 RX filter")

    print("Listening for events...")
    start = time.time()
    while True:
        elapsed = time.time() - start
        try:
            fw.process_events()
            if elapsed >= 1.0:
                start = time.time()
                # Transmit CAN messages every 1 second
                fw.can_transmit(0, 0x123, bytes([0x11, 0x22, 0x33, 0x44]), True, True).expect(
                    "Failed to send CAN message on channel 0"
                )
                fw.can_transmit(1, 0x124, bytes([0x11, 0x22, 0x33, 0x44]), True, True).expect(
                    "Failed to send CAN message on channel 1"
                )
        except KeyboardInterrupt:
            break
    # Disable events before exiting
    print("Disabling CAN events...")
    for channel in (0, 1):
        fw.can_enable_streaming(channel, False).expect("Failed to disable CAN streaming")
    fw.can_enable_transmit_periodic(0, False).expect("Failed to disable periodic CAN message on channel 0")
    print("Exiting event loop")
