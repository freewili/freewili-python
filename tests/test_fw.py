"""Test code for freewili.fw module."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from freewili.fw import FileMap, FreeWili
from freewili.fw_serial import FreeWiliProcessorType


def test_file_mappings() -> None:
    """Test file mapping."""
    known_maps = {
        "wasm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
        "wsm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
        "zio": (FreeWiliProcessorType.Main, "/scripts", "ZoomIO script file"),
        "bin": (FreeWiliProcessorType.Main, "/fpga", "FPGA bin file"),
        "sub": (FreeWiliProcessorType.Main, "/radio", "Radio file"),
        "fwi": (FreeWiliProcessorType.Display, "/images", "Image file"),
        "wav": (FreeWiliProcessorType.Display, "/sounds", "Audio file"),
        "py": (FreeWiliProcessorType.Main, "/scripts", "rthon script"),
    }

    for ext, values in known_maps.items():
        map = FileMap.from_ext(ext)
        assert map.extension == ext
        assert map.processor == values[0]
        assert map.directory == values[1]
        assert map.description == values[2]

    with pytest.raises(ValueError, match="Extension 'failure' is not a known FreeWili file type") as _exc_info:
        FileMap.from_ext(".failure")


def test_freewili_find_methods() -> None:
    """Test FreeWili find methods."""
    # Mock the fwf.find_all to avoid hardware dependency
    with patch("pyfwfinder.find_all", return_value=[]):
        # Test find_first with no devices
        result = FreeWili.find_first()
        assert result.is_err()
        assert "No FreeWili devices found" in result.unwrap_err()

        # Test find_all with no devices
        devices = FreeWili.find_all()
        assert devices == ()


# def test_freewili_with_mock_device() -> None:
#     """Test FreeWili with a mocked device."""
#     mock_device = MagicMock()
#     mock_device.usb_devices = []
#     mock_device.serial = "TEST123"

#     fw = FreeWili(mock_device)

#     # Test basic properties
#     assert fw.usb_devices == []
#     assert fw.device == mock_device

#     # Test string representations
#     assert str(fw) == "Free-Wili TEST123"
#     assert "TEST123" in repr(fw)

#     # Test get_usb_device with empty devices
#     mock_device.get_usb_devices.return_value = []
#     assert fw.get_usb_device(FreeWiliProcessorType.Main) is None
#     assert fw.get_usb_device(FreeWiliProcessorType.Display) is None


def test_freewili_find_first_success() -> None:
    """Test FreeWili find_first with mock device."""
    mock_device = MagicMock()
    mock_device.serial = "MOCK123"

    with patch("pyfwfinder.find_all", return_value=[mock_device]):
        result = FreeWili.find_first()
        assert result.is_ok()
        fw = result.unwrap()
        assert fw.device == mock_device


def test_file_map_invalid_extension() -> None:
    """Test FileMap with invalid extension."""
    with pytest.raises(ValueError) as exc_info:
        FileMap.from_ext("invalid")
    assert "Extension 'invalid' is not a known FreeWili file type" in str(exc_info.value)

    # Test with extension that has a dot (it strips the dot)
    with pytest.raises(ValueError) as exc_info:
        FileMap.from_ext(".unknown")
    assert "Extension 'unknown' is not a known FreeWili file type" in str(exc_info.value)

    assert FileMap.from_fname(r"C:\dev\My Project\Output\test.wasm") == FileMap.from_ext("wasm")
    assert FileMap.from_fname(r"/home/dev/my_project/test.wasm") == FileMap.from_ext("wasm")
    assert FileMap.from_fname(r"test.wasm") == FileMap.from_ext("wasm")

    assert FileMap.from_ext("wasm").to_path("test.wasm") == "/scripts/test.wasm"
    assert FileMap.from_ext("wasm").to_path("/some/random/path/test.wasm") == "/scripts/test.wasm"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_file_send_and_get() -> None:
    """Test File uploading on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
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
        time.sleep(1)  # Wait a moment before getting the file
        event_cb_buffer.clear()
        # Get File
        start_time = time.time()
        assert (
            device.get_file("/images/pip_boy.fwi", "pip_boy_downloaded.fwi", None, event_cb).expect(
                "Failed to get file."
            )
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


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
            "-s",
        ]
    )
