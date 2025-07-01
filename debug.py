# noqa
import time

from freewili import FreeWili
from freewili.types import FreeWiliProcessorType


def event_cb(msg: str) -> None:
    """Temporary."""
    print(f"[CB]: {msg}")


count: int = 0
while True:
    count += 1
    device = FreeWili.find_first().expect("Failed to find a FreeWili")
    print(device)
    # device.stay_open = True
    device.open().expect("Failed to open")
    # rf = device.send_file("tests/assets/pip_boy.fwi", "/images/pip_boy.fwi", FreeWiliProcessorType.Display).expect(
    #     "Failed to send file"
    # )
    # print(rf)
    # print("\n" * 2)
    # print("=" * 80)
    # print("\n" * 2)
    rf = device.get_file(
        "/images/pip_boy.fwi", "pip_boy_downloaded.fwi", event_cb, FreeWiliProcessorType.Display
    ).expect(f"Failed to get file. {count}")
    print(rf)
    device.close()
    print(f"Done. {count}")
    time.sleep(2)
