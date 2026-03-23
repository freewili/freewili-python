"""Test MDIO functionality on a FreeWili.

Hardware Setup: Connect MDC to pin 17 and MDIO to pin 14.
"""

import pytest

from freewili import FreeWili


class NoMDIOHardwareError(Exception):
    """Exception to raise when no MDIO PHY hardware was found."""

    pass


class MDIOHardwareFoundError(Exception):
    """Exception to raise when MDIO PHY hardware was found."""

    pass


# --- SFP Operations ---


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_poll_sfp() -> None:
    """Test SFP polling on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        result = device.mdio_poll_sfp()
        if result.is_err():
            raise NoMDIOHardwareError(f"SFP poll failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_sfp() -> None:
    """Test SFP register read on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Read register 0x00FF on device address 0x1A
        result = device.mdio_read_sfp(0x1A, b"\x00\xFF")
        if result.is_err():
            raise NoMDIOHardwareError(f"SFP read failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_write_sfp() -> None:
    """Test SFP register write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Write 0x1234 to register 0x00FF on device 0x1A
        result = device.mdio_write_sfp(0x1A, b"\x00\xFF\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"SFP write failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_modify_write_sfp() -> None:
    """Test SFP read-modify-write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # RMW register 0x00FF on device 0x1A, mask 0xFF00, data 0x1234
        result = device.mdio_read_modify_write_sfp(0x1A, b"\x00\xFF\xFF\x00\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"SFP RMW failed: {result.err()}")
        assert result.ok() != ""


# --- PHY Address Discovery ---


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_poll_phy() -> None:
    """Test PHY address polling on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        result = device.mdio_poll_phy()
        if result.is_err():
            raise NoMDIOHardwareError(f"PHY poll failed: {result.err()}")
        assert result.ok() != ""


# --- Clause 22 Operations ---


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_22() -> None:
    """Test Clause 22 read on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Read register 0x02 on PHY 0x01
        result = device.mdio_read_22(0x01, 0x02)
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 22 read failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_write_22() -> None:
    """Test Clause 22 write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Write 0x1234 to register 0x02 on PHY 0x01
        result = device.mdio_write_22(0x01, 0x02, b"\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 22 write failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_modify_write_22() -> None:
    """Test Clause 22 read-modify-write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # RMW register 0x02 on PHY 0x01, mask 0xFF00, data 0x1234
        result = device.mdio_read_modify_write_22(0x01, 0x02, b"\xFF\x00\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 22 RMW failed: {result.err()}")
        assert result.ok() != ""


# --- Clause 45 Operations ---


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_45() -> None:
    """Test Clause 45 read on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Read register 0x0003 on MMD 0x01 on PHY 0x01
        result = device.mdio_read_45(0x01, 0x01, 0x0003)
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 45 read failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_write_45() -> None:
    """Test Clause 45 write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Write 0xABCD to register 0x0003 on MMD 0x01 on PHY 0x01
        result = device.mdio_write_45(0x01, 0x01, 0x0003, b"\xAB\xCD")
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 45 write failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_modify_write_45() -> None:
    """Test Clause 45 read-modify-write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # RMW register 0x0003 on MMD 0x01 on PHY 0x01, mask 0xFF00, data 0x1234
        result = device.mdio_read_modify_write_45(0x01, 0x01, 0x0003, b"\xFF\x00\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"Clause 45 RMW failed: {result.err()}")
        assert result.ok() != ""


# --- Clause 22 Access to Clause 45 (Emulation) Operations ---


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_emu() -> None:
    """Test Clause 22 Access to Clause 45 (emulation) read on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Read register 0x0003 on MMD 0x01 on PHY 0x01
        result = device.mdio_read_emu(0x01, 0x01, 0x0003)
        if result.is_err():
            raise NoMDIOHardwareError(f"Emulation read failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_write_emu() -> None:
    """Test Clause 22 Access to Clause 45 (emulation) write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Write 0xABCD to register 0x0003 on MMD 0x01 on PHY 0x01
        result = device.mdio_write_emu(0x01, 0x01, 0x0003, b"\xAB\xCD")
        if result.is_err():
            raise NoMDIOHardwareError(f"Emulation write failed: {result.err()}")
        assert result.ok() != ""


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoMDIOHardwareError)
def test_hw_mdio_read_modify_write_emu() -> None:
    """Test Clause 22 Access to Clause 45 (emulation) read-modify-write on a FreeWili."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # RMW register 0x0003 on MMD 0x01 on PHY 0x01, mask 0xFF00, data 0x1234
        result = device.mdio_read_modify_write_emu(0x01, 0x01, 0x0003, b"\xFF\x00\x12\x34")
        if result.is_err():
            raise NoMDIOHardwareError(f"Emulation RMW failed: {result.err()}")
        assert result.ok() != ""


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
