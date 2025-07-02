# noqa
from freewili import FreeWili


def send_event_cb(msg: str) -> None:
    """Temporary."""
    print(f"\r[Send File Callback]: {msg}" + " " * (120 - len(msg)), end="\r")


def get_event_cb(msg: str) -> None:
    """Temporary."""
    print(f"\r[Get File Callback]: {msg}" + " " * (120 - len(msg)), end="\r")


device = FreeWili.find_first().expect("Failed to find a FreeWili")
print(f"Using {device}")
# device.stay_open = True
device.open().expect("Failed to open")
ret = device.send_file("tests/assets/pip_boy.fwi", "/images/pip_boy.fwi", None, send_event_cb, 32768).expect(
    "Failed to send file"
)
print()
print(ret)
print("=" * 80)
ret = device.get_file("/images/pip_boy.fwi", "pip_boy_downloaded.fwi", None, get_event_cb).expect("Failed to get file.")
print()
print(ret)
device.close()
print("Done!")
