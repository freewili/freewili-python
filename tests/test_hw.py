"""Test I2C functionality on a FreeWili."""

import pytest

from freewili import FreeWili
from freewili.framing import ResponseFrameType


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_board_leds() -> None:
    """Test LEDs on a FreeWili."""
    device = FreeWili.find_all()[0]
    device.stay_open = True

    try:
        for led_num in range(7):
            response_frame = device.set_board_leds(led_num, 50, 50, 50).expect("Failed to set LED")
            assert response_frame.rf_type == ResponseFrameType.Standard
            assert response_frame.rf_type_data == r"g\s"
            assert response_frame.timestamp != 0
            assert response_frame.response == "Ok"
            assert response_frame.is_ok()

        for led_num in range(7):
            response_frame = device.set_board_leds(led_num, 0, 0, 0).expect("Failed to set LED")
            assert response_frame.rf_type == ResponseFrameType.Standard
            # assert response_frame.rf_type_data == r"g\s"
            assert response_frame.timestamp != 0
            assert response_frame.response == "Ok"
            assert response_frame.is_ok()
    finally:
        device.close()


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_show_gui_image() -> None:
    """Test image on a FreeWili."""
    device = FreeWili.find_all()[0]

    try:
        device.open().expect("Failed to open")
        success = device.send_file("tests/assets/pip_boy.fwi").expect("Failed to upload file")
        assert success != ""
        response_frame = device.show_gui_image("pip_boy.fwi").expect("Failed to show image")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"g\l"
        assert response_frame.timestamp != 0
        assert response_frame.response == "Ok", "Is pip_boy.fwi uploaded to the device?"
        assert response_frame.is_ok()

        response_frame = device.reset_display().expect("Failed to reset display")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"g\t"
        assert response_frame.timestamp != 0
        assert response_frame.response == "Ok"
        assert response_frame.is_ok()
    finally:
        device.close()


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_show_text_display() -> None:
    """Test show text on a FreeWili."""
    device = FreeWili.find_all()[0]
    device.stay_open = True

    try:
        response_frame = device.show_text_display("test").expect("Failed to show image")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"g\p"
        assert response_frame.timestamp != 0
        assert response_frame.response == "Ok"
        assert response_frame.is_ok()
    finally:
        device.close()


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_read_all_buttons() -> None:
    """Test read buttons on a FreeWili."""
    device = FreeWili.find_all()[0]
    device.stay_open = True

    try:
        response_frame = device.read_all_buttons().expect("Failed to show image")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"g\u"
        assert response_frame.timestamp != 0
        assert response_frame.response == "0 0 0 0 0"
        assert response_frame.is_ok()
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
