"""Test I2C functionality on a FreeWili."""

import pytest

from freewili import FreeWili
from freewili.framing import ResponseFrameType


class NoI2CHardwareError(Exception):
    """Exception to raise when no I2C hardware was found."""

    pass


class I2CHardwareFoundError(Exception):
    """Exception to raise when I2C hardware was found."""

    pass


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=I2CHardwareFoundError)
def test_hw_i2c_nothing_attached() -> None:
    """Test i2c on a FreeWili with nothing attached."""
    device = FreeWili.find_all()[0]
    device.stay_open = True
    try:
        # Test Polling
        response_frame = device.poll_i2c().expect("Failed to poll i2c")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\p"
        assert response_frame.timestamp != 0
        # assert response_frame.seq_number == 4
        # '[i\\p 0DFA6AF1068E68BB 2 1 20 1]'
        i2c_count_str, *address_list = response_frame.response.split(" ")
        i2c_count: int = int(i2c_count_str, 10)
        addresses: tuple = tuple([int(x, 16) for x in address_list])
        assert i2c_count == len(addresses)
        if i2c_count > 0:
            raise I2CHardwareFoundError(f"Poll found {i2c_count} I2C devices. Ensure VIO jumper is correct.")
        assert response_frame.response == "0"
        assert response_frame.success == 1

        response_frame = device.write_i2c(0x0, 0x0, bytes([0, 1, 2, 3, 4, 5, 6, 7])).expect("Failed to write i2c")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\w"
        assert response_frame.timestamp != 0
        # assert response_frame.seq_number == 4
        # assert response_frame.response == "Invalid"
        assert response_frame.success == 0

        response_frame = device.read_i2c(0x0, 0x0, 8).expect("Failed to read i2c")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\r"
        assert response_frame.timestamp != 0
        # assert response_frame.seq_number == 4
        # assert response_frame.response == "Invalid"
        assert response_frame.success == 0
    finally:
        device.close()


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoI2CHardwareError)
def test_hw_i2c_sparkfun_9dof_imu_breakout() -> None:
    """Test i2c on a FreeWili with SparkFun 9DoF IMU Breakout - ISM330DHCX, MMC5983MA (Qwiic) attached.

    https://www.sparkfun.com/sparkfun-9dof-imu-breakout-ism330dhcx-mmc5983ma-qwiic.html
    ISM330DHCX I2C Address: 0x6B (Default)
    MMC5983MA Magnetometer I2C Address: 0x30
    """
    device = FreeWili.find_all()[0]
    device.stay_open = True

    try:
        # Test Polling
        response_frame = device.poll_i2c().expect("Failed to poll i2c")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\p"
        assert response_frame.timestamp != 0
        # '[i\\p 0DFA6AF1068E68BB 2 1 20 1]'
        i2c_count_str, *address_list = response_frame.response.split(" ")
        i2c_count: int = int(i2c_count_str, 10)
        addresses: tuple = tuple([int(x, 16) for x in address_list])
        assert i2c_count == len(addresses)
        if i2c_count == 0:
            raise NoI2CHardwareError(f"Poll found {i2c_count} I2C devices")
        if i2c_count == 1 and addresses[0] == 0x20:
            raise NoI2CHardwareError(f"Poll found {i2c_count} I2C devices")
        assert response_frame.response == "3 20 30 6B", "If 1 20, this is a hardware bug, VIO isn't connected"
        assert response_frame.success == 1

        # Lets read from ISM330DHCX
        # https://cdn.sparkfun.com/assets/d/4/6/d/f/ism330dhcx_Datasheet.pdf
        response_frame = device.read_i2c(0x6B, 0x02, 1).expect("Failed to read address 0x6B on ISM330DHCX")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\r"
        assert response_frame.timestamp != 0
        assert response_frame.response == "3F "
        assert response_frame.success == 1

        # Lets write to ISM330DHCX
        # 0x14 Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’. Default value: 0
        response_frame = device.write_i2c(0x6B, 0x14, bytes([0b10000000])).expect("Failed to write 0x14 on ISM330DHCX")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\w"
        assert response_frame.timestamp != 0
        assert response_frame.response == "Ok"
        assert response_frame.success == 1
        # Set to 0 to complete the reset
        response_frame = device.write_i2c(0x6B, 0x14, bytes([0b00000000])).expect("Failed to write 0x14 on ISM330DHCX")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\w"
        assert response_frame.timestamp != 0
        assert response_frame.response == "Ok"
        assert response_frame.success == 1
        # Verify we reset the register to defaults
        response_frame = device.read_i2c(0x6B, 0x14, 1).expect("Failed to read address 0x6B on ISM330DHCX")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\r"
        assert response_frame.timestamp != 0
        # assert response_frame.seq_number == 4
        assert response_frame.response == "00 "
        assert response_frame.success == 1

        # Lets read from MMC5983MA
        # https://cdn.sparkfun.com/assets/a/b/7/7/2/19921-09102019_MMC5983MA_Datasheet_Rev_A-1635338.pdf
        # Product ID1 0x2F
        response_frame = device.read_i2c(0x30, 0x2F, 1).expect("Failed to read register 0x6B on ISM330DHCX")
        assert response_frame.rf_type == ResponseFrameType.Standard
        assert response_frame.rf_type_data == r"i\r"
        assert response_frame.timestamp != 0
        # assert response_frame.seq_number == 4
        assert response_frame.response == "30 "
        assert response_frame.success == 1
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
