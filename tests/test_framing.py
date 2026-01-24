"""Test ResponseFrame."""

import numpy as np

from freewili.framing import ResponseFrame, ResponseFrameType


def test_response_frame() -> None:
    """Test ResponseFrame decoding."""
    response_frame = ResponseFrame.from_raw(r"[i\w 1831A98807457841 4 Invalid 0]", strict=False).expect(
        "Failed to decode frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Standard
    assert response_frame.rf_type_data == r"i\w"
    assert response_frame.timestamp == 1743360932471732289
    assert response_frame.seq_number == 4
    assert response_frame.response == "Invalid"
    assert response_frame.success == 0
    assert not response_frame.is_ok()
    assert response_frame.response_as_bytes().is_err()
    assert response_frame.timestamp_as_datetime().expect("Failed to get timestamp as datetime") == np.datetime64(
        1743360932471732289, "ns"
    )

    response_frame = ResponseFrame.from_raw(r"[*UART1 1831A98807457841 0 Failed 0]", strict=False).expect(
        "Failed to decode frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Event
    assert response_frame.rf_type_data == r"UART1"
    assert response_frame.timestamp == 1743360932471732289


def test_response_frame_is_frame() -> None:
    """Test the is_frame static method."""
    # Test valid frames
    assert ResponseFrame.is_frame("[valid frame]")
    assert ResponseFrame.is_frame(b"[valid frame bytes]")

    # Test invalid frames
    assert not ResponseFrame.is_frame("invalid frame")
    assert not ResponseFrame.is_frame("[missing end bracket")
    assert not ResponseFrame.is_frame("missing start bracket]")
    assert not ResponseFrame.is_frame("")


def test_response_frame_is_start_of_frame() -> None:
    """Test the is_start_of_frame static method."""
    # Test valid start of frames
    assert ResponseFrame.is_start_of_frame("[start of frame")
    assert ResponseFrame.is_start_of_frame(b"[start of frame bytes")
    assert ResponseFrame.is_start_of_frame("[")

    # Test invalid start of frames
    assert not ResponseFrame.is_start_of_frame("no bracket")
    assert not ResponseFrame.is_start_of_frame("wrong]bracket")
    assert not ResponseFrame.is_start_of_frame("")


def test_response_frame_from_raw_errors() -> None:
    """Test error handling in from_raw method."""
    # Test invalid frame format
    result = ResponseFrame.from_raw("invalid frame without brackets")
    assert result.is_err()
    assert "expected frame to be enclosed []" in result.unwrap_err()

    # Test bytes input
    result = ResponseFrame.from_raw(b"[i\\w 1831A98807457841 4 Valid 1]", strict=False)
    assert result.is_ok()

    # Test frame with too few parts
    result = ResponseFrame.from_raw("[incomplete]")
    assert result.is_err()

    # Test invalid timestamp in strict mode
    result = ResponseFrame.from_raw("[i\\w INVALID_TIMESTAMP 4 Valid 1]", strict=True)
    assert result.is_err()
    assert "Failed to decode timestamp" in result.unwrap_err()


def test_response_frame_successful_response() -> None:
    """Test ResponseFrame with successful response and bytes conversion."""
    response_frame = ResponseFrame.from_raw(r"[i\w 1831A98807457841 4 3F 1]", strict=False).expect(
        "Failed to decode frame"
    )
    assert response_frame.success == 1
    assert response_frame.is_ok()

    # Test successful bytes conversion (using hex response like "3F")
    bytes_result = response_frame.response_as_bytes()
    assert bytes_result.is_ok()
    assert bytes_result.unwrap() == bytes([0x3F])


def test_response_frame_different_types() -> None:
    """Test ResponseFrame with different frame types."""
    # Test event frame
    event_frame = ResponseFrame.from_raw(r"[*EVENT 1831A98807457841 0 Event message 1]", strict=False).expect(
        "Failed to decode event frame"
    )
    assert event_frame.rf_type == ResponseFrameType.Event
    assert event_frame.rf_type_data == "EVENT"

    # Test standard frame
    std_frame = ResponseFrame.from_raw(r"[cmd 1831A98807457841 5 Response 1]", strict=False).expect(
        "Failed to decode standard frame"
    )
    assert std_frame.rf_type == ResponseFrameType.Standard
    assert std_frame.rf_type_data == "cmd"

    # Real I2C Read response frame v43
    response_frame = ResponseFrame.from_raw(r"[i\r 1831A98807457841 0 3F 1]", strict=True).expect(
        "Failed to decode frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Standard
    assert response_frame.rf_type_data == r"i\r"
    assert response_frame.timestamp == 1743360932471732289
    assert response_frame.seq_number == 0
    assert response_frame.response == "3F"
    assert response_frame.success == 1
    assert response_frame.is_ok()
    assert response_frame.response_as_bytes().is_ok()
    assert response_frame.response_as_bytes().unwrap() == bytes(
        [
            0x3F,
        ]
    )

    # Real I2C Poll response frame v43
    response_frame = ResponseFrame.from_raw(r"[i\p 1831A98807457841 16 2 30 6B 1]", strict=True).expect(
        "Failed to decode frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Standard
    assert response_frame.rf_type_data == r"i\p"
    assert response_frame.timestamp == 1743360932471732289
    assert response_frame.seq_number == 16
    assert response_frame.response == "2 30 6B"
    assert response_frame.success == 1
    assert response_frame.is_ok()
    assert response_frame.response_as_bytes().is_ok()
    assert response_frame.response_as_bytes().unwrap() == bytes([2, 0x30, 0x6B])

    # Real I2C Poll response no hardware v43
    response_frame = ResponseFrame.from_raw(r"[i\p 1831A98807457841 2 0 1]", strict=True).expect(
        "Failed to decode frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Standard
    assert response_frame.rf_type_data == r"i\p"
    assert response_frame.timestamp == 1743360932471732289
    assert response_frame.seq_number == 2
    assert response_frame.response == "0"
    assert response_frame.success == 1
    assert response_frame.is_ok()
    assert response_frame.response_as_bytes().is_ok()
    assert response_frame.response_as_bytes().unwrap() == bytes(
        [
            0,
        ]
    )

    # RTC year response frame v54
    response_frame = ResponseFrame.from_raw(r"[z\t\y 18565F820C845726 17 25 1]", strict=True).expect(
        "Failed to decode RTC year frame"
    )
    assert response_frame.rf_type == ResponseFrameType.Standard
    assert response_frame.rf_type_data == r"z\t\y"
    assert response_frame.timestamp == 1753694117067773734
    assert response_frame.seq_number == 17
    assert response_frame.response == "25"
    assert response_frame.success == 1
    assert response_frame.is_ok()


def test_response_frame_start_validation() -> None:
    """Test ResponseFrame start of frame validation."""
    assert not ResponseFrame.is_start_of_frame("asdf[*filedl ")
    assert ResponseFrame.is_start_of_frame("[*filedl ")
    assert ResponseFrame.contains_start_of_frame("[*filedl ") == (True, 0)
    assert ResponseFrame.validate_start_of_frame("[*filedl ") == (ResponseFrameType.Event, 0)
    assert ResponseFrame.validate_start_of_frame("[i\\w ") == (ResponseFrameType.Standard, 0)
    assert ResponseFrame.validate_start_of_frame("no frame") == (ResponseFrameType.Invalid, -1)

    assert ResponseFrame.contains_start_of_frame("asdf[*filedl ") == (True, 4)
    assert ResponseFrame.validate_start_of_frame("asdf[*filedl ") == (ResponseFrameType.Event, 4)
    assert ResponseFrame.validate_start_of_frame("asdf[i\\w ") == (ResponseFrameType.Standard, 4)
    assert ResponseFrame.validate_start_of_frame("no frame[asdf") == (ResponseFrameType.Invalid, -1)

    assert ResponseFrame.contains_start_of_frame(r"[z\t\y 18565F820C845726 17 25 1]") == (True, 0)
    assert ResponseFrame.validate_start_of_frame(r"[z\t\y 18565F820C845726 17 25 1]") == (ResponseFrameType.Standard, 0)
    assert ResponseFrame.validate_start_of_frame(r"asdf[z\t\y 18565F820C845726 17 25 1]") == (
        ResponseFrameType.Standard,
        4,
    )


def test_response_frame_end_validation() -> None:
    """Test ResponseFrame end of frame validation."""
    assert ResponseFrame.contains_end_of_frame("]") == (True, 0)
    assert ResponseFrame.contains_end_of_frame("asdf]extra") == (True, 4)
    assert ResponseFrame.contains_end_of_frame("] extra") == (True, 0)
    assert ResponseFrame.contains_end_of_frame("no end") == (False, -1)

    assert ResponseFrame.contains_end_of_frame(r"[z\t\y 18565F820C845726 17 25 1]") == (True, 31)
    assert ResponseFrame.contains_end_of_frame(r"[z\t\y 18565F820C845726 17 25 1]asdf") == (True, 31)


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
