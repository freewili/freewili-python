"""Example I2C on a FreeWili with SparkFun 9DoF IMU Breakout - ISM330DHCX, MMC5983MA (Qwiic) attached.

https://www.sparkfun.com/sparkfun-9dof-imu-breakout-ism330dhcx-mmc5983ma-qwiic.html
ISM330DHCX I2C Address: 0x6B (Default)
MMC5983MA Magnetometer I2C Address: 0x30
"""

import enum
from time import time

from freewili import FreeWili

MMC5983MA_ADDR = 0x30
ISM330DHCX_ADDR = 0x6B


class MMC5983MA(enum.Enum):
    """Register list for MMC5983MA Magnetometer."""

    Xout0 = 0x00  # Xout [17:10]
    Xout1 = 0x01  # Xout [9:2]
    Yout0 = 0x02  # Yout [17:10]
    Yout1 = 0x03  # Yout [9:2]
    Zout0 = 0x04  # Zout [17:10]
    Zout1 = 0x05  # Zout [9:2]
    XYZout2 = 0x06  # Xout[1:0], Yout[1:0], Zout[1:0]
    Tout = 0x07  # Temperature output
    Status = 0x08  # Device status
    Control0 = 0x09  # Control register 0
    Control1 = 0x0A  # Control register 1
    Control2 = 0x0B  # Control register 2
    Control3 = 0x0C  # Control register 3
    ProductID = 0x2F  # Product ID


class ISM330DHCX(enum.Enum):
    """Register list for ISM330DHCX."""

    FUNC_CFG_ACCESS = 0x01
    PIN_CTRL = 0x02
    FIFO_CTRL1 = 0x07
    FIFO_CTRL2 = 0x08
    FIFO_CTRL3 = 0x09
    FIFO_CTRL4 = 0x0A
    COUNTER_BDR_REG1 = 0x0B
    COUNTER_BDR_REG2 = 0x0C
    INT1_CTRL = 0x0D
    INT2_CTRL = 0x0E
    WHO_AM_I = 0x0F
    CTRL1_XL = 0x10
    CTRL2_G = 0x11
    CTRL3_C = 0x12
    CTRL4_C = 0x13
    CTRL5_C = 0x14
    CTRL6_C = 0x15
    CTRL7_G = 0x16
    CTRL8_XL = 0x17
    CTRL9_XL = 0x18
    CTRL10_C = 0x19
    ALL_INT_SRC = 0x1
    WAKE_UP_SRC = 0x1B
    TAP_SRC = 0x1C
    DRD_SRC = 0x1D
    STATUS_REG = 0x1E
    STATUS_SPIAux = 0x1E
    OUT_TEMP_L = 0x20
    OUT_TEMP_H = 0x21
    OUTX_L_G = 0x22
    OUTX_H_G = 0x23
    OUTY_L_G = 0x24
    OUTY_H_G = 0x25
    OUTZ_L_G = 0x26
    OUTZ_H_G = 0x27
    OUTX_L_A = 0x28
    OUTX_H_A = 0x29
    OUTY_L_A = 0x2A
    OUTY_H_A = 0x2B
    OUTZ_L_A = 0x2C
    OUTZ_H_A = 0x2D
    EMB_FUNC_STATUS_MAINPAGE = 0x35
    FSM_STATUS_A_MAINPAGE = 0x36
    FSM_STATUS_B_MAINPAGE = 0x37
    MLC_STATUS_MAINPAGE = 0x38
    STATUS_MASTER_MAINPAGE = 0x39
    FIFO_STATUS1 = 0x3A
    FIFO_STATUS2 = 0x3B
    TIMESTAMP0 = 0x40
    TIMESTAMP1 = 0x41
    TIMESTAMP2 = 0x42
    TIMESTAMP3 = 0x43
    TAP_CFG0 = 0x56
    TAP_CFG1 = 0x57
    TAP_CFG2 = 0x58
    TAP_THS_6D = 0x59
    INT_DUR2 = 0x5A
    WAKE_UP_THS = 0x5B
    WAKE_UP_DUR = 0x5C
    FREE_FALL = 0x5D
    MD1_CFG = 0x5E
    MD2_CFG = 0x5F
    INTERNAL_FREQ_FINE = 0x63
    INT_OIS = 0x6F
    CTRL1_OIS = 0x70
    CTRL2_OIS = 0x71
    CTRL3_OIS = 0x72
    X_OFS_USR = 0x73
    Y_OFS_USR = 0x74
    Z_OFS_USR = 0x75
    FIFO_DATA_OUT_TAG = 0x78
    FIFO_DATA_OUT_X_L = 0x79
    FIFO_DATA_OUT_X_H = 0x7A
    FIFO_DATA_OUT_Y_L = 0x7B
    FIFO_DATA_OUT_Y_H = 0x7C
    FIFO_DATA_OUT_Z_L = 0x7D
    FIFO_DATA_OUT_Z_H = 0x7E


def get_mmc5983ma_temperature(device: FreeWili) -> float:
    """Get temperature on MMC5983MA.

    Arguments:
    ----------
        device: FreeWili
            FreeWili device to use.

    Returns:
    --------
        tuple[float, int]:
            (Temperature in degrees Celcius, timestamp in ns).
    """
    _ = device.write_i2c(MMC5983MA_ADDR, MMC5983MA.Control0.value, bytes([0x2A])).expect("Enable temp measure")
    while True:
        response = device.read_i2c(MMC5983MA_ADDR, MMC5983MA.Status.value, 1).expect("Reading Status failed")
        status = response[0]
        if (status & 0x2) == 0x2:
            # print("Temperature measurement done!")
            break
    response = device.read_i2c(MMC5983MA_ADDR, MMC5983MA.Tout.value, 1).expect("Reading Tout failed")
    # Temperature output, unsigned format. The range is -75~125°C, about 0.8°C/LSB, 00000000 stands for -75°C
    temp = response
    temp_int = int.from_bytes(temp, byteorder="little", signed=False)
    converted = temp_int * 0.8 - 75
    # print(resp._raw.strip())
    return converted


def get_mmc5983ma_magnetic_sensor(device: FreeWili) -> tuple[int, int, int]:
    """Get magnetic field data on MMC5983MA.

    Arguments:
    ----------
        device: FreeWili
            FreeWili device to use.

    Returns:
    --------
        tuple[int, int, int]:
            (x, y, z).
    """
    _ = device.write_i2c(MMC5983MA_ADDR, MMC5983MA.Control0.value, bytes([0x29])).expect("Enable magnetic field")
    while True:
        response = device.read_i2c(MMC5983MA_ADDR, MMC5983MA.Status.value, 1).expect("Reading Status failed")
        status = response[0]
        if (status & 0x1) == 0x1:
            # print("Temperature measurement done!")
            break
    data = device.read_i2c(MMC5983MA_ADDR, MMC5983MA.Xout0.value, 6).expect("Reading Tout failed")
    x = int.from_bytes(data[0:2], byteorder="little", signed=False) << 2
    y = int.from_bytes(data[2:4], byteorder="little", signed=False) << 2
    z = int.from_bytes(data[4:6], byteorder="little", signed=False) << 2
    return (x, y, z)


# find a FreeWili device
device = FreeWili.find_first().expect("Failed to find a FreeWili")
device.open().expect("Failed to open FreeWili")

try:
    # Poll the I2C to make sure we can read the breakout board
    print("Polling I2C...")
    addresses = device.poll_i2c().expect("Failed to poll I2C")
    if MMC5983MA_ADDR not in addresses or ISM330DHCX_ADDR not in addresses:
        print(f"Expected I2C addresses {MMC5983MA_ADDR} and {ISM330DHCX_ADDR} not found. Got {addresses}!")
        exit(1)

    start = time()
    while True:
        try:
            temp_c = get_mmc5983ma_temperature(device)
            temp_f = temp_c * 1.8 + 32
            print(f"[{time() - start:.3f}] Temperature: {temp_c:.1f}C ({temp_f:.1f}F)")
            magnetic_data = get_mmc5983ma_magnetic_sensor(device)
            print(f"[{time() - start:.3f}] Magnetic Field: {magnetic_data}")
        except KeyboardInterrupt:
            break
finally:
    device.close()

print("Done.")
