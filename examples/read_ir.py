"""Example script to demonstrate IR NEC communication with Free-WiLi."""

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import EventDataType, EventType, IRData


def event_callback(event_type: EventType, response_frame: ResponseFrame, event_data: EventDataType) -> None:
    """Callback function to handle events from FreeWili."""
    if isinstance(event_data, IRData):
        print(f"IR RX {len(event_data.value)}: {event_data.value!r}")


fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    fw.set_event_callback(event_callback)
    print("Enabling IR events")
    fw.enable_ir_events(True).expect("Failed to enable IR events")
    print("Waiting for IR events... Press Ctrl+C to exit.")
    while True:
        try:
            fw.process_events()
        except KeyboardInterrupt:
            print("Exiting IR event loop")
            break
    fw.enable_ir_events(False).expect("Failed to disable IR events")
print("Done.")
