"""Example script to demonstrate NFC read events with Free-WiLi."""

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import EventDataType, EventType, NFCData


def event_callback(event_type: EventType, response_frame: ResponseFrame, event_data: EventDataType) -> None:
    """Callback function to handle events from FreeWili."""
    if isinstance(event_data, NFCData):
        if event_data.disconnected:
            print("NFC Card removed")
        elif event_data.disconnected is None:
            return
        else:
            print(f"NFC Card detected: UID={event_data.uid.hex().upper()}, " \
                    f"ATQA={event_data.atqa.hex().upper()}, " \
                    f"SAK={event_data.sak.hex().upper()}, " \
                    f"Type={event_data.card_type}")


with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
    fw.set_event_callback(event_callback)
    print("Enabling NFC events")
    fw.enable_nfc_read_events(True).expect("Failed to enable NFC events")
    print("Waiting for NFC events... Press Ctrl+C to exit.")
    while True:
        try:
            fw.process_events()
        except KeyboardInterrupt:
            print("Exiting NFC event loop")
            break
    fw.enable_nfc_read_events(False).expect("Failed to disable NFC events")
print("Done.")
