"""Support for FreeWili serial framing."""

import enum
import sys
from dataclasses import dataclass

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import numpy as np
from result import Err, Ok, Result


class ResponseFrameType(enum.Enum):
    """FreeWili serial response frame types."""

    # response frames that start with a menu letter. i\w = i2c write
    Standard = enum.auto()
    # response frames that start with an *[EVENT_NAME]
    Event = enum.auto()


@dataclass(frozen=True)
class ResponseFrame:
    """Response Frame from a FreeWili serial."""

    rf_type: ResponseFrameType
    rf_type_data: str
    # unix epoch timestamp in nanoseconds
    timestamp: int
    seq_number: int
    response: str
    success: int
    _raw: str

    @staticmethod
    def is_frame(frame: bytes | str) -> bool:
        """Identify if the frame value is something we can parse.

        Parameters:
        ----------
            frame : bytes | str:
                response frame string to decode.

        Returns:
        -------
            bool:
                True if is a frame, False otherwise.
        """
        if isinstance(frame, bytes):
            frame = frame.decode("ascii")
        assert isinstance(frame, str)
        return frame.startswith("[") and frame.endswith("]")

    @staticmethod
    def is_start_of_frame(frame: bytes | str) -> bool:
        """Identify if the frame value is something we might be able to parse when complete.

        Parameters:
        ----------
            frame : bytes | str:
                response frame string to decode.

        Returns:
        -------
            bool:
                True if is a frame, False otherwise.
        """
        if isinstance(frame, bytes):
            frame = frame.decode("ascii")
        assert isinstance(frame, str)
        return frame.startswith("[")

    @classmethod
    def from_raw(cls, frame: str | bytes, strict: bool = True) -> Result[Self, str]:
        """Take a response frame string and create a ResponseFrame.

        Parameters:
        ----------
            frame : str
                response frame string to decode.
            strict : bool
                allows the timestamp to be invalid.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if decoded successfully, Err(str) if not.
        """
        # Verify we are a frame, we should be enclosed with []
        if isinstance(frame, bytes):
            frame = frame.decode("ascii")
        frame = frame.strip()
        raw = frame
        if not cls.is_frame(frame):
            return Err("Invalid data, expected frame to be enclosed []")
        # Strip the brackets
        frame = frame.lstrip("[").rstrip().rstrip("]")
        # Seperate the frame, every item is space seperated.
        items = frame.split(" ")
        if len(items) < 5:
            return Err("Invalid frame contents, not enough items")
        # example I2C: [i\w YXNkZmFzZGY= 4 Invalid 0]
        rf_type = ResponseFrameType.Standard
        if items[0].startswith("*"):
            rf_type = ResponseFrameType.Event
            items[0] = items[0].lstrip("*")
        try:
            # Convert the timestamp to nanoseconds.
            # value is sent as big endian hex.
            big_endian_hex_ts = items[1]
            # unix_epoch_nanoseconds = int(little_endian_hex_ts, 16)
            unix_epoch_nanoseconds = int(big_endian_hex_ts, 16)
        except ValueError as ex:
            if strict:
                return Err(f"Failed to decode timestamp: {str(ex)}")
            unix_epoch_nanoseconds = 0
        return Ok(
            cls(
                rf_type,  # rf_type
                str(items[0]),  # rf_type_data
                unix_epoch_nanoseconds,  # timestamp
                int(items[2]),  # seq_number
                " ".join(items[3:-1]),  # response
                int(items[-1]),  # success
                raw,  # _raw
            )
        )

    def is_ok(self) -> bool:
        """Validates if the frame was successful.

        Parameters:
        ----------
            None

        Returns:
        -------
            bool:
                True if success == 1, False otherwise.
        """
        return self.success == 1

    def response_as_bytes(self, check_ok: bool = True) -> Result[bytes, str]:
        """Convert the response into bytes.

        Parameters:
        ----------
            check_ok: bool
                Calls is_ok() to make sure the frame is valid.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if valid, False if data couldn't be converted.
        """
        if check_ok and not self.is_ok():
            return Err("Response success is not ok")
        try:
            response = self.response.rstrip(" ")
            if not response:
                return Ok(bytes())
            data: bytes = bytes([int(x, 16) for x in response.split(" ")])
            return Ok(data)
        except TypeError as ex:
            return Err(ex)
        except ValueError as ex:
            return Err(ex)

    def timestamp_as_datetime(self, check_ok: bool = False) -> Result[np.datetime64, str]:
        """Convert the timestamp into a datetime.

        Parameters:
        ----------
            check_ok: bool
                Calls is_ok() to make sure the frame is valid.

        Returns:
        -------
            Result[np.datetime64, str]:
                Ok(np.datetime64) if valid, Err(str) if timestamp couldn't be converted.
        """
        if check_ok and not self.is_ok():
            return Err("Response success is not ok")
        return Ok(np.datetime64(self.timestamp, "ns"))
