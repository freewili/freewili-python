"""Test I2C functionality on a FreeWili."""

import time

import pytest

from freewili import FreeWili


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_board_leds() -> None:
    """Test LEDs on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
        for led_num in range(7):
            assert device.set_board_leds(led_num, 50, 50, led_num * 10).expect("Failed to set LED") != "", (
                f"Failed to set LED {led_num}"
            )

        for led_num in range(7):
            assert device.set_board_leds(led_num, 0, 0, 0).expect("Failed to set LED") != "", (
                f"Failed to set LED {led_num}"
            )


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_show_gui_image() -> None:
    """Test image on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
        assert device.send_file("tests/assets/pip_boy.fwi").expect("Failed to upload file") != ""
        assert device.show_gui_image("pip_boy.fwi").expect("Failed to show image") != ""
        time.sleep(1)
        assert device.reset_display().expect("Failed to reset display") != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_show_text_display() -> None:
    """Test show text on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
        assert device.show_text_display("test").expect("Failed to show image") != ""
        time.sleep(1)
        assert device.reset_display().expect("Failed to reset display") != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_read_all_buttons() -> None:
    """Test read buttons on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
        button_states = device.read_all_buttons().expect("Failed to read all buttons")
        for button_color, button_state in button_states.items():
            assert button_state == 0, f"Button {button_color.name} should be 0"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_spi_read_write_data() -> None:
    """Test SPI read/write data on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as device:
        device.read_write_spi_data(b"\x01\x02\x03\x04").expect("Failed to read/write SPI data")


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
