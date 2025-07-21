"""Example script to handle events from FreeWili."""

from typing import Any

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import EventType


def event_handler(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
    """Handle events from FreeWili."""
    match event_type:
        case EventType.Accel:
            print(f"Accel Event: {data}")
        case _:
            # Handle other event types as needed
            if data:
                print(f"{event_type}: Event Data: {data}")
            else:
                print(f"No data for this {event_type}.")


with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
    fw.set_event_callback(event_handler)

    fw.enable_accel_events(True, 33).expect("Failed to enable accel events")
    fw.enable_button_events(True, 33).expect("Failed to enable button events")
    fw.enable_ir_events(True).expect("Failed to enable IR events")
    fw.enable_battery_events(True).expect("Failed to enable battery events")

    while True:
        try:
            fw.process_events()
        except KeyboardInterrupt:
            break
    fw.enable_accel_events(False).expect("Failed to disable accel events")
    fw.enable_button_events(False).expect("Failed to disable button events")
    fw.enable_ir_events(False).expect("Failed to disable IR events")
    fw.enable_battery_events(False).expect("Failed to disable battery events")
    print("Exiting event loop")
