"""Test I2C functionality on a FreeWili."""

import pytest

from freewili import FreeWili

MMC5983MA_ADDR = 0x30
ISM330DHCX_ADDR = 0x6B


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
    device = FreeWili.find_first().expect("Failed to find a FreeWili")
    device.open().expect("Failed to open FreeWili")
    try:
        # Test Polling
        addresses = device.poll_i2c().expect("Failed to poll i2c")
        if len(addresses) != 0:
            if len(addresses) != 1 and 0x20 not in addresses:
                raise I2CHardwareFoundError(f"Poll found {len(addresses)} I2C devices: {addresses}")
            else:
                raise I2CHardwareFoundError(f"Poll found {len(addresses)} I2C devices: {addresses}")

        with pytest.raises(Exception):  # noqa: B017
            _ = device.write_i2c(0x0, 0x0, bytes([0, 1, 2, 3, 4, 5, 6, 7])).expect("Failed to write I2C")

        with pytest.raises(Exception):  # noqa: B017
            _ = device.read_i2c(0x0, 0x0, 8).expect("Failed to read i2c")
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
    device = FreeWili.find_first().expect("Failed to find a FreeWili")
    device.open().expect("Failed to open FreeWili")

    try:
        # Test Polling
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if len(addresses) == 0:
            raise NoI2CHardwareError(f"Poll found {len(addresses)} I2C devices")
        # This is a workaround for firmware bug in v49. Issue #13
        if len(addresses) == 1 and 0x20 in addresses:
            raise NoI2CHardwareError(f"Poll found {len(addresses)} I2C devices")
        assert MMC5983MA_ADDR in addresses, f"Expected I2C address {MMC5983MA_ADDR} not found. Got {addresses}!"
        assert ISM330DHCX_ADDR in addresses, f"Expected I2C address {ISM330DHCX_ADDR} not found. Got {addresses}!"

        # Lets read from ISM330DHCX
        # https://cdn.sparkfun.com/assets/d/4/6/d/f/ism330dhcx_Datasheet.pdf
        response = device.read_i2c(0x6B, 0x02, 1).expect("Failed to read address 0x6B on ISM330DHCX")
        assert response[0] == 0x3F

        # Lets write to ISM330DHCX
        # 0x14 Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’. Default value: 0
        response = device.write_i2c(0x6B, 0x14, bytes([0b10000000])).expect("Failed to write 0x14 on ISM330DHCX")
        assert response == "Ok", f"Expected 'OK', got '{response}'"
        # Set to 0 to complete the reset
        response = device.write_i2c(0x6B, 0x14, bytes([0b00000000])).expect("Failed to write 0x14 on ISM330DHCX")
        assert response == "Ok", f"Expected 'OK', got '{response}'"
        # Verify we reset the register to defaults
        response = device.read_i2c(0x6B, 0x14, 1).expect("Failed to read address 0x6B on ISM330DHCX")
        assert response[0] == 0x00, f"Expected 0x00, got {response[0]:02X}"

        # Lets read from MMC5983MA
        # https://cdn.sparkfun.com/assets/a/b/7/7/2/19921-09102019_MMC5983MA_Datasheet_Rev_A-1635338.pdf
        # Product ID1 0x2F
        response = device.read_i2c(0x30, 0x2F, 1).expect("Failed to read register 0x6B on ISM330DHCX")
        assert response[0] == 0x30, f"Expected 0x30, got {response[0]:02X}"
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
