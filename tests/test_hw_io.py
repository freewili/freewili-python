"""Test I2C functionality on a FreeWili."""

import pytest

from freewili import FreeWili
from freewili.types import IOMenuCommand


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_io() -> None:
    """Test IO on a FreeWili."""
    device = FreeWili.find_first().expect("Failed to open")
    device.open().expect("Failed to open)")

    try:
        # Set IO low
        assert device.set_io(25, IOMenuCommand.Low).expect("Failed to set IO low") != ""
        # Check to make sure IO is low
        assert device.get_io().expect("Failed to get IO")[25] == 0
        # Set IO High
        assert device.set_io(25, IOMenuCommand.High).expect("Failed to set IO high") != ""
        # Check to make sure IO is high
        assert device.get_io().expect("Failed to get IO")[25] == 1
        # Set IO toggle to low
        assert device.set_io(25, IOMenuCommand.Toggle).expect("Failed to set IO high") != ""
        # Check to make suruve IO is low
        assert device.get_io().expect("Failed to get IO")[25] == 0
    finally:
        device.close()


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
