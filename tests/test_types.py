"""Test code for freewili.types module."""

from freewili.fw_serial import FreeWiliProcessorType


def test_processor_type() -> None:
    """Test processor type for ABI breakage."""
    assert FreeWiliProcessorType.Main.value == 1
    assert FreeWiliProcessorType.Display.value == 2
    assert FreeWiliProcessorType.FTDI.value == 3
    assert FreeWiliProcessorType.ESP32.value == 4
    assert FreeWiliProcessorType.Unknown.value == 5


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
