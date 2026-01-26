"""Test event handling functionality on a FreeWili device."""

import time
from typing import Any, List

import pytest

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import EventType


class TestEvents:
    """Test class for event handling functionality."""

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_set_event_callback(self) -> None:
        """Test setting an event callback."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            events_received: List[tuple] = []

            def test_callback(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
                events_received.append((event_type, frame, data))

            # Set callback
            fw.set_event_callback(test_callback)

            # Verify we can clear callback
            fw.set_event_callback(None)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_gpio_events(self) -> None:
        """Test enabling and disabling GPIO events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable GPIO events
            result = fw.enable_gpio_events(True)
            assert result.is_ok(), f"Failed to enable GPIO events: {result.unwrap_err()}"

            # Disable GPIO events
            result = fw.enable_gpio_events(False)
            assert result.is_ok(), f"Failed to disable GPIO events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_accel_events(self) -> None:
        """Test enabling and disabling accelerometer events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable accel events with 33ms interval
            result = fw.enable_accel_events(True, 33)
            assert result.is_ok(), f"Failed to enable accel events: {result.unwrap_err()}"

            # Disable accel events
            result = fw.enable_accel_events(False)
            assert result.is_ok(), f"Failed to disable accel events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_button_events(self) -> None:
        """Test enabling and disabling button events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable button events with 33ms interval
            result = fw.enable_button_events(True, 33)
            assert result.is_ok(), f"Failed to enable button events: {result.unwrap_err()}"

            # Disable button events
            result = fw.enable_button_events(False)
            assert result.is_ok(), f"Failed to disable button events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_ir_events(self) -> None:
        """Test enabling and disabling IR events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable IR events
            result = fw.enable_ir_events(True)
            assert result.is_ok(), f"Failed to enable IR events: {result.unwrap_err()}"

            # Disable IR events
            result = fw.enable_ir_events(False)
            assert result.is_ok(), f"Failed to disable IR events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_battery_events(self) -> None:
        """Test enabling and disabling battery events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable battery events
            result = fw.enable_battery_events(True)
            assert result.is_ok(), f"Failed to enable battery events: {result.unwrap_err()}"

            # Disable battery events
            result = fw.enable_battery_events(False)
            assert result.is_ok(), f"Failed to disable battery events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_radio_events(self) -> None:
        """Test enabling and disabling radio events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable radio events
            result = fw.enable_radio_events(True)
            assert result.is_ok(), f"Failed to enable radio events: {result.unwrap_err()}"

            # Disable radio events
            result = fw.enable_radio_events(False)
            assert result.is_ok(), f"Failed to disable radio events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_uart_events(self) -> None:
        """Test enabling and disabling UART events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable UART events
            result = fw.enable_uart_events(True)
            assert result.is_ok(), f"Failed to enable UART events: {result.unwrap_err()}"

            # Disable UART events
            result = fw.enable_uart_events(False)
            assert result.is_ok(), f"Failed to disable UART events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_enable_disable_audio_events(self) -> None:
        """Test enabling and disabling audio events."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Enable audio events
            result = fw.enable_audio_events(True)
            assert result.is_ok(), f"Failed to enable audio events: {result.unwrap_err()}"

            # Disable audio events
            result = fw.enable_audio_events(False)
            assert result.is_ok(), f"Failed to disable audio events: {result.unwrap_err()}"

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_process_events_no_callback(self) -> None:
        """Test process_events without a callback set."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Should not raise an error even without a callback
            fw.process_events()

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_process_events_with_callback(self) -> None:
        """Test process_events with a callback set."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            events_received: List[tuple] = []

            def event_callback(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
                events_received.append((event_type, frame, data))
                print(f"Event received: {event_type}")

            fw.set_event_callback(event_callback)

            # Process events (should not raise an error)
            fw.process_events()

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_accel_events_with_callback(self) -> None:
        """Test receiving accelerometer events with callback."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            events_received: List[EventType] = []

            def accel_callback(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
                events_received.append(event_type)
                if event_type == EventType.Accel:
                    print(f"Accel event: {data}")

            fw.set_event_callback(accel_callback)

            try:
                # Enable accel events
                result = fw.enable_accel_events(True, 100)
                assert result.is_ok(), f"Failed to enable accel events: {result.unwrap_err()}"

                # Process events for a short time to potentially receive some
                start_time = time.time()
                while time.time() - start_time < 1.0:  # Process for 1 second
                    fw.process_events()
                    time.sleep(0.01)

                # Note: We may or may not receive events depending on device state
                # The important thing is that it doesn't crash
                print(f"Received {len(events_received)} events")

            finally:
                # Disable events
                fw.enable_accel_events(False)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_multiple_event_types_enabled(self) -> None:
        """Test enabling multiple event types simultaneously."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            events_received: List[EventType] = []

            def multi_event_callback(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
                events_received.append(event_type)
                print(f"Event: {event_type}")

            fw.set_event_callback(multi_event_callback)

            try:
                # Enable multiple event types
                assert fw.enable_gpio_events(True).is_ok(), "Failed to enable GPIO events"
                assert fw.enable_button_events(True, 50).is_ok(), "Failed to enable button events"
                assert fw.enable_ir_events(True).is_ok(), "Failed to enable IR events"
                assert fw.enable_battery_events(True).is_ok(), "Failed to enable battery events"

                # Process events for a short time
                start_time = time.time()
                while time.time() - start_time < 0.5:  # Process for 0.5 seconds
                    fw.process_events()
                    time.sleep(0.01)

                print(f"Total events received: {len(events_received)}")

            finally:
                # Disable all events
                fw.enable_gpio_events(False)
                fw.enable_button_events(False)
                fw.enable_ir_events(False)
                fw.enable_battery_events(False)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_event_callback_exception_handling(self) -> None:
        """Test that exceptions in event callbacks are handled gracefully."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:

            def failing_callback(event_type: EventType, frame: ResponseFrame, data: Any) -> None:
                raise ValueError("Test exception in callback")

            fw.set_event_callback(failing_callback)

            try:
                fw.enable_battery_events(True).expect("Failed to enable battery events")

                # Process events - should handle callback exceptions gracefully
                # (implementation may log the error but shouldn't crash)
                for _ in range(10):
                    fw.process_events()
                    time.sleep(0.01)

            finally:
                fw.enable_battery_events(False)
                fw.set_event_callback(None)


if __name__ == "__main__":
    pytest.main([__file__, "--verbose", "-s"])
