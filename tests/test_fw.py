"""Test code for freewili.fw module."""

import os
import time

import pytest

from freewili.fw import FileMap, FreeWili
from freewili.serial_util import FreeWiliProcessorType


def test_file_mappings() -> None:
    """Test file mapping."""
    known_maps = {
        "wasm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
        "wsm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
        "sub": (FreeWiliProcessorType.Display, "/radio", "Radio file"),
        "fwi": (FreeWiliProcessorType.Display, "/images", "Image file"),
    }

    for ext, values in known_maps.items():
        map = FileMap.from_ext(ext)
        assert map.extension == ext
        assert map.processor == values[0]
        assert map.directory == values[1]
        assert map.description == values[2]

    with pytest.raises(ValueError, match="Extension 'failure' is not a known FreeWili file type") as _exc_info:
        FileMap.from_ext(".failure")

    assert FileMap.from_fname(r"C:\dev\My Project\Output\test.wasm") == FileMap.from_ext("wasm")
    assert FileMap.from_fname(r"/home/dev/my_project/test.wasm") == FileMap.from_ext("wasm")
    assert FileMap.from_fname(r"test.wasm") == FileMap.from_ext("wasm")

    assert FileMap.from_ext("wasm").to_path("test.wasm") == "/scripts/test.wasm"
    assert FileMap.from_ext("wasm").to_path("/some/random/path/test.wasm") == "/scripts/test.wasm"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_file_send_and_get() -> None:
    """Test File uploading on a FreeWili."""
    device = FreeWili.find_first().expect("Failed to open")
    device.open().expect("Failed to open)")

    event_cb_buffer: list[str] = []

    def event_cb(msg: str) -> None:
        assert msg != ""
        print("[CB]:", msg)
        event_cb_buffer.append(msg)

    # Send File
    start_time = time.time()
    assert (
        device.send_file("tests/assets/pip_boy.fwi", "/images/pip_boy.fwi", None, event_cb).expect(
            "Failed to send file"
        )
        != ""
    )
    elapsed = time.time() - start_time
    assert elapsed < 10, f"File send took too long: {elapsed:.2f} seconds"
    assert len(event_cb_buffer) > 0
    event_cb_buffer.clear()
    # Get File
    start_time = time.time()
    assert (
        device.get_file("/images/pip_boy.fwi", "pip_boy_downloaded.fwi", None, event_cb).expect("Failed to get file.")
        != ""
    )
    elapsed = time.time() - start_time
    assert elapsed < 10, f"File send took too long: {elapsed:.2f} seconds"
    assert len(event_cb_buffer) > 0
    # Verify downloaded file matches original
    with open("tests/assets/pip_boy.fwi", "rb") as f1, open("pip_boy_downloaded.fwi", "rb") as f2:
        assert f1.read() == f2.read(), "Downloaded file does not match original file."
    # Clean up downloaded file
    os.remove("pip_boy_downloaded.fwi")
    device.close()


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
