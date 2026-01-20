"""Example script to handle events from FreeWili."""

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import AccelData, EventDataType, EventType, GPIOData


def event_handler(event_type: EventType, frame: ResponseFrame, data: EventDataType) -> None:
    """Handle events from FreeWili."""
    match event_type:
        case EventType.Accel:
            data: AccelData = data  # type:ignore
            print(f"Accel Event: {data}")
        case EventType.GPIO:
            data: GPIOData = data  # type: ignore
            print(f"GPIO Event: {data.raw}")  # type: ignore
        case _:
            # Handle other event types as needed
            if data:
                print(f"{event_type}: Event Data: {data}")
            else:
                print(f"No data for this {event_type}.")


fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to FreeWili {fw}")
    fw.set_event_callback(event_handler)

    print("Enabling events...")
    fw.enable_gpio_events(True).expect("Failed to enable GPIO events")
    fw.enable_accel_events(True, 33).expect("Failed to enable accel events")
    fw.enable_button_events(True, 33).expect("Failed to enable button events")
    fw.enable_ir_events(True).expect("Failed to enable IR events")
    fw.enable_battery_events(True).expect("Failed to enable battery events")
    # fw.enable_audio_events(True).expect("Failed to enable audio events")
    print("Listening for events...")
    while True:
        try:
            fw.process_events()
        except KeyboardInterrupt:
            break
    # Disable events before exiting
    print("Disabling events...")
    fw.enable_gpio_events(False).expect("Failed to disable GPIO events")
    fw.enable_accel_events(False).expect("Failed to disable accel events")
    fw.enable_button_events(False).expect("Failed to disable button events")
    fw.enable_ir_events(False).expect("Failed to disable IR events")
    fw.enable_battery_events(False).expect("Failed to disable battery events")
    # fw.enable_audio_events(False).expect("Failed to disable audio events")
    print("Exiting event loop")
