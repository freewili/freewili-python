"""Example script to set FreeWili settings. Currently unstable and subject to API changes."""

from datetime import datetime

from freewili import FreeWili
from freewili.types import FreeWiliProcessorType

fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to {fw}")
    # Set default settings for both processors
    for processor in (FreeWiliProcessorType.Main, FreeWiliProcessorType.Display):
        print("Setting defaulting settings for", processor.name)
        fw.set_settings_to_default(processor).expect(
            f"Failed to set {processor.name.lower()} processor settings to default"
        )
    # Set system sounds to off
    print("Disabling system sounds...")
    fw.set_system_sounds(False).expect("Failed to disable system sounds")
    # Save these settings for both processors on startup
    for processor in (FreeWiliProcessorType.Main, FreeWiliProcessorType.Display):
        print("Setting", processor.name, "processor settings on startup...")
        fw.set_settings_as_startup(processor).expect(
            f"Failed to set {processor.name.lower()} processor settings on startup"
        )
    # Set the current RTC time
    print("Setting RTC to current time...")
    fw.set_rtc(datetime.now()).expect("Failed to set RTC")
    print("RTC set successfully.")
print("Goodbye!")
