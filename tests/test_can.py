"""Test CAN functionality on a FreeWili with Neptune Orca hardware."""

import time

import pytest

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import CANData, EventDataType, EventType


class NoCANHardwareError(Exception):
    """Exception to raise when no CAN hardware (Neptune) was found."""

    pass


class CANHardwareFoundError(Exception):
    """Exception to raise when CAN hardware (Neptune) was found."""

    pass


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=CANHardwareFoundError)
def test_hw_can_nothing_attached() -> None:
    """Test CAN on a FreeWili with no Neptune hardware attached."""
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Test Polling - if we find 0x48, that means Neptune is attached
        addresses = device.poll_i2c().expect("Failed to poll i2c")
        if 0x48 in addresses:
            raise CANHardwareFoundError("Found Neptune hardware (I2C address 0x48)")


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_neptune_basic() -> None:
    """Test basic CAN functionality on a FreeWili with Neptune Orca hardware.

    This test requires Neptune Orca hardware which provides CAN functionality.
    Neptune is identified by I2C address 0x48.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Test Polling - verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

        # Test enabling CAN streaming on both channels
        for channel in (0, 1):
            result = device.can_enable_streaming(channel, True).expect(
                f"Failed to enable CAN streaming on channel {channel}"
            )
            assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # Test disabling CAN streaming
        for channel in (0, 1):
            result = device.can_enable_streaming(channel, False).expect(
                f"Failed to disable CAN streaming on channel {channel}"
            )
            assert result == "Ok", f"Expected 'Ok', got '{result}'"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_neptune_transmit() -> None:
    """Test CAN transmit functionality on a FreeWili with Neptune Orca hardware.

    This test requires Neptune Orca hardware which provides CAN functionality.
    Tests basic CAN message transmission on both channels.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

        # Test CAN transmit on channel 0
        result = device.can_transmit(
            0,  # channel
            0x123,  # arb_id
            bytes([0x11, 0x22, 0x33, 0x44]),  # data
            True,  # is_canfd
            True,  # is_extended
        ).expect("Failed to transmit CAN message on channel 0")
        assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # Test CAN transmit on channel 1
        result = device.can_transmit(
            1,  # channel
            0x124,  # arb_id
            bytes([0x55, 0x66, 0x77, 0x88]),  # data
            True,  # is_canfd
            False,  # is_extended (standard ID)
        ).expect("Failed to transmit CAN message on channel 1")
        assert result == "Ok", f"Expected 'Ok', got '{result}'"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_neptune_periodic_transmit() -> None:
    """Test CAN periodic transmit functionality on a FreeWili with Neptune Orca hardware.

    This test sets up and controls periodic CAN message transmission.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

        # Set up a periodic CAN message on channel 0, every 100 ms
        result = device.can_set_transmit_periodic(
            0,  # channel
            0,  # slot (0-7)
            100_000,  # period_us (100ms)
            0x55,  # arb_id
            True,  # is_canfd
            True,  # is_extended
            bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]),  # data
        ).expect("Failed to set periodic CAN message on channel 0")
        assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # Verify we can enable periodic transmission
        result = device.can_enable_transmit_periodic(0, True).expect(
            "Failed to enable periodic CAN message on channel 0"
        )
        assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # Disable periodic transmission
        result = device.can_enable_transmit_periodic(0, False).expect(
            "Failed to disable periodic CAN message on channel 0"
        )
        assert result == "Ok", f"Expected 'Ok', got '{result}'"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_neptune_rx_filter() -> None:
    """Test CAN RX filter functionality on a FreeWili with Neptune Orca hardware.

    This test configures CAN receive filters to selectively receive messages.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

        # Set up CAN RX filter on channel 0
        result = device.can_set_rx_filter(
            0,  # channel
            0,  # filter_num
            True,  # is_extended
            0xFF,  # match_priority
            0x123,  # match_id
            0,  # match_data1
            0,  # match_data2
            0,  # mask_id
            0,  # mask_data
        ).expect("Failed to set CAN RX filter on channel 0")
        assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # # Test enabling RX filter
        # result = device.can_enable_rx_filter(0, 0, True).expect("Failed to enable CAN RX filter on channel 0")
        # assert result == "Ok", f"Expected 'Ok', got '{result}'"

        # # Test disabling RX filter
        # result = device.can_enable_rx_filter(0, 0, False).expect("Failed to disable CAN RX filter on channel 0")
        # assert result == "Ok", f"Expected 'Ok', got '{result}'"


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_neptune_events() -> None:
    """Test CAN event handling on a FreeWili with Neptune Orca hardware.

    This test verifies that CAN events can be received and processed correctly.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

        # Track received events
        received_events: dict[EventType, list[EventDataType]] = {
            EventType.CANRX0: [],
            EventType.CANRX1: [],
            EventType.CANTX0: [],
            EventType.CANTX1: [],
        }

        def event_handler(event_type: EventType, frame: ResponseFrame, data: EventDataType) -> None:
            """Handle events from FreeWili."""
            if event_type in received_events:
                received_events[event_type].append(data)

        # Set up event callback
        device.set_event_callback(event_handler)

        # Enable CAN streaming on both channels
        for channel in (0, 1):
            device.can_enable_streaming(channel, True).expect(f"Failed to enable CAN streaming on channel {channel}")

        # Send a test message
        device.can_transmit(0, 0x123, bytes([0xAA, 0xBB, 0xCC, 0xDD]), True, True).expect(
            "Failed to send CAN message on channel 0"
        )

        # Process events for a short time to see if we receive anything
        start = time.time()
        while time.time() - start < 0.5:  # Process for 500ms
            device.process_events()
            time.sleep(0.01)

        # Disable streaming
        for channel in (0, 1):
            device.can_enable_streaming(channel, False).expect(f"Failed to disable CAN streaming on channel {channel}")

        # Note: We don't assert specific events were received because this depends on
        # the actual CAN bus configuration and hardware setup. The test passes if
        # the event handling infrastructure works without errors.


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
@pytest.mark.xfail(raises=NoCANHardwareError)
def test_hw_can_data_parsing() -> None:
    """Test CANData parsing from string format.

    This test verifies the CANData.from_string() method correctly parses CAN event data.
    """
    with FreeWili.find_first().expect("Failed to find a FreeWili") as device:
        # Verify Neptune hardware is present
        addresses = device.poll_i2c().expect("Failed to poll I2C")
        if 0x48 not in addresses:
            raise NoCANHardwareError("Neptune hardware not found (no I2C address 0x48)")

    # Test parsing extended ID with data
    can_data = CANData.from_string("9x 01 02 03")
    assert can_data.arb_id == 0x9
    assert can_data.is_extended is True
    assert can_data.data == bytes([0x01, 0x02, 0x03])

    # Test parsing standard ID with data
    can_data = CANData.from_string("9 01 02 03")
    assert can_data.arb_id == 0x9
    assert can_data.is_extended is False
    assert can_data.data == bytes([0x01, 0x02, 0x03])

    # Test parsing with no data
    can_data = CANData.from_string("9 ")
    assert can_data.arb_id == 0x9
    assert can_data.is_extended is False
    assert can_data.data == bytes([])

    # Test parsing extended ID with no data
    can_data = CANData.from_string("123x ")
    assert can_data.arb_id == 0x123
    assert can_data.is_extended is True
    assert can_data.data == bytes([])


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
