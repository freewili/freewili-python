"""Example script to demonstrate UART communication with Free-WiLi."""

# Note: v54 firmware has a limitation of 22 bytes per UART message, so we use 16 to be safe.
# Note: v54 firmware enable_uart_events is a toggle only, so we enable it once and disable it at the end.

import time

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import EventDataType, EventType, UART1Data


def event_callback(event_type: EventType, response_frame: ResponseFrame, event_data: EventDataType) -> None:
    """Callback function to handle events from FreeWili."""
    if isinstance(event_data, UART1Data):
        print(f"UART1 RX {len(event_data.data)}: {event_data.data!r}")


fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    fw.set_event_callback(event_callback)
    fw.enable_uart_events(True).expect("Failed to enable UART events")
    data = b"Hello Free-WiLi from UART1!"
    chunk_size = 16  # v54 firmware has a limitation of 22 bytes per UART message, so we use 16 to be safe.
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        print(f"Sending UART Data: {chunk!r}")
        fw.write_uart(chunk).expect("Failed to send UART message")
    # Wait for the device to process and send back any events. If we close too soon, we won't see the events.
    time.sleep(0.5)
    try:
        fw.process_events()
    except KeyboardInterrupt:
        print("Exiting UART event loop")
    fw.enable_uart_events(False).expect("Failed to disable UART events")
print("Done.")
