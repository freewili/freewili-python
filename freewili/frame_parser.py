"""Frame parser state machine for FreeWili serial communication."""

import enum
import logging
import time
from typing import Any

from freewili.framing import ResponseFrame
from freewili.util.fifo import SafeIOFIFOBuffer


class ParserState(enum.Enum):
    """State machine states for frame parsing."""

    IDLE = enum.auto()
    IN_POSSIBLE_FRAME = enum.auto()
    IN_EVENT_FRAME = enum.auto()
    IN_COMMAND_FRAME = enum.auto()
    IN_BINARY_DATA = enum.auto()


class FrameParser:
    """State machine for parsing FreeWili serial frames."""

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the frame parser.

        Parameters:
        -----------
            logger: logging.Logger | None
                Logger instance for debug output
        """
        self.state = ParserState.IDLE
        self.logger = logger or logging.getLogger(__name__)
        self._debug_count: int = 0
        self._frame_buffer: bytearray = bytearray()
        self._frame_start_time: float = 0.0
        self._binary_buffer: bytearray = bytearray()
        self._binary_only_mode: bool = False  # When True, treat all data as binary

    def reset(self) -> None:
        """Reset the parser state to initial conditions."""
        self.state = ParserState.IDLE
        self._debug_count = 0
        self._frame_buffer.clear()
        self._frame_start_time = 0.0
        self._binary_buffer.clear()
        self._binary_only_mode = False

    def set_binary_only_mode(self, enabled: bool) -> None:
        """Enable or disable binary-only mode.

        When enabled, all data is treated as binary and no frame parsing occurs.
        This is useful during file transfers to avoid mistaking binary data for frames.
        """
        self._binary_only_mode = enabled
        if enabled:
            # If switching to binary mode, flush any accumulated frame data as binary
            if len(self._frame_buffer) > 0:
                # This will be handled by the data_queue in the next parse call
                pass
            self.state = ParserState.IDLE

    def parse(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data from the buffer using state machine logic.

        Parameters:
        -----------
            data_buffer: SafeIOFIFOBuffer
                Buffer containing incoming serial data
            rf_queue: Queue
                Queue for standard response frames
            rf_event_queue: Queue
                Queue for event response frames
            rf_events: SafeResponseFrameDict
                Dictionary for storing event frames
            data_queue: Queue
                Queue for binary data
        """
        # Loop until no more data or we're waiting for more data
        max_iterations = 1000  # Prevent infinite loops
        iterations = 0

        while data_buffer.available() > 0 and iterations < max_iterations:
            iterations += 1
            prev_available = data_buffer.available()
            prev_state = self.state

            # In binary-only mode, treat everything as binary data
            if self._binary_only_mode:
                chunk = data_buffer.read(-1)
                if chunk:
                    self.logger.trace(f"RX Binary Data (binary-only mode): {len(chunk)} bytes")  # type: ignore[attr-defined]
                    data_queue.put(chunk)
                break

            match self.state:
                case ParserState.IDLE:
                    self._parse_idle(
                        data_buffer,
                        rf_queue,
                        rf_event_queue,
                        rf_events,
                        data_queue,
                    )
                case ParserState.IN_POSSIBLE_FRAME:
                    self._parse_possible_frame(
                        data_buffer,
                        rf_queue,
                        rf_event_queue,
                        rf_events,
                        data_queue,
                    )
                case ParserState.IN_EVENT_FRAME:
                    self._parse_event_frame(
                        data_buffer,
                        rf_queue,
                        rf_event_queue,
                        rf_events,
                        data_queue,
                    )
                case ParserState.IN_COMMAND_FRAME:
                    self._parse_command_frame(
                        data_buffer,
                        rf_queue,
                        rf_event_queue,
                        rf_events,
                        data_queue,
                    )
                case ParserState.IN_BINARY_DATA:
                    self._parse_binary_data(
                        data_buffer,
                        rf_queue,
                        rf_event_queue,
                        rf_events,
                        data_queue,
                    )
                case _:
                    self.logger.error(f"Unknown parser state: {self.state}")
                    raise RuntimeError(f"Unknown parser state: {self.state}")

            # Throttle iterations to avoid busy looping
            if iterations % 100 == 0:
                time.sleep(0.001)

            # If buffer size didn't change AND state didn't change, we're waiting for more data
            # Break to avoid infinite loop
            # But if state changed (e.g., IDLE -> IN_EVENT_FRAME), continue even if buffer unchanged
            if data_buffer.available() == prev_available and self.state == prev_state:
                break

    def _parse_idle(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data in IDLE state - check for '[' to enter frame detection."""
        if data_buffer.available() == 0:
            return

        first_byte = data_buffer.peek(1)

        if first_byte == b"[":
            # Possible frame start, transition to IN_POSSIBLE_FRAME
            self.logger.debug("Transitioning to IN_POSSIBLE_FRAME")
            self.state = ParserState.IN_POSSIBLE_FRAME
            self._frame_buffer.clear()
            self._frame_start_time = time.time()
        else:
            # Not a frame start - binary data
            self.logger.debug("Transitioning to IN_BINARY_DATA")
            self.state = ParserState.IN_BINARY_DATA
            self._binary_buffer.clear()

    def _parse_possible_frame(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data in IN_POSSIBLE_FRAME state - determine if event or command frame.

        Event frames: [*word ...]
        Command frames: [x ...] where x is a letter followed by space or backslash
        """
        # Need at least 3 bytes to check: [* or [x followed by space/backslash
        if data_buffer.available() < 3:
            # Check timeout while waiting
            if time.time() - self._frame_start_time > 1.0:
                # Waited too long, probably binary
                self.logger.debug("Possible frame timeout, treating as binary")
                self.state = ParserState.IN_BINARY_DATA
                self._binary_buffer.clear()
            return

        first_three = data_buffer.peek(3)

        if first_three[:2] == b"[*":
            # Event frame starts with [*
            self.logger.debug("Detected event frame ([*)")
            self.state = ParserState.IN_EVENT_FRAME
            # Consume the [* prefix
            self._frame_buffer.extend(data_buffer.read(2))
        elif first_three[0:1] == b"[" and first_three[1:2].isalpha():
            # Might be a command frame - check if followed by space or backslash
            second_char = first_three[1:2]
            third_char = first_three[2:3]

            if third_char in (b" ", b"\\"):
                # Looks like a command frame: [letter followed by space or backslash
                self.logger.debug(
                    f"Detected command frame ([{second_char.decode('ascii', errors='ignore')} "
                    f"{third_char.decode('ascii', errors='ignore')})"
                )
                self.state = ParserState.IN_COMMAND_FRAME
                # Consume the [letter prefix
                self._frame_buffer.extend(data_buffer.read(2))
            else:
                # [letter but not followed by space/backslash - probably binary
                self.logger.debug(
                    f"Not a valid frame ([{second_char.decode('ascii', errors='ignore')}"
                    f"{third_char.decode('ascii', errors='ignore')}), transitioning to IN_BINARY_DATA"
                )
                self.state = ParserState.IN_BINARY_DATA
                self._binary_buffer.clear()
        else:
            # Not a valid frame start, treat as binary
            self.logger.debug("Not a valid frame, transitioning to IN_BINARY_DATA")
            self.state = ParserState.IN_BINARY_DATA
            self._binary_buffer.clear()

    def _parse_event_frame(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data in IN_EVENT_FRAME state - wait for closing bracket ]."""
        # Check timeout
        elapsed = time.time() - self._frame_start_time
        if elapsed > 6.0:
            self.logger.error(f"Event frame timeout after {elapsed:.1f}s: {bytes(self._frame_buffer)!r}")
            # Output as binary data since it's not a valid frame
            if len(self._frame_buffer) > 0:
                data_queue.put(bytes(self._frame_buffer))
            self._frame_buffer.clear()
            self.state = ParserState.IDLE
            return

        # Check size limit
        if len(self._frame_buffer) > 200:
            self.logger.error(f"Event frame exceeded 200 bytes: {bytes(self._frame_buffer)!r}")
            # Output as binary data since it's not a valid frame
            if len(self._frame_buffer) > 0:
                data_queue.put(bytes(self._frame_buffer))
            self._frame_buffer.clear()
            self.state = ParserState.IDLE
            return

        # Read byte by byte looking for closing bracket ]
        while data_buffer.available() > 0:
            byte = data_buffer.read(1)
            self._frame_buffer.extend(byte)

            # Check for closing bracket
            if byte == b"]":
                # Found closing bracket, now consume the newline
                if data_buffer.available() == 0:
                    # Wait for more data (the newline)
                    return

                next_byte = data_buffer.peek(1)
                if next_byte == b"\n":
                    # Frame ends with ]\n
                    self._frame_buffer.extend(data_buffer.read(1))
                    frame = bytes(self._frame_buffer)
                    self.logger.debug(f"RX Event Frame: {frame!r}")
                    rf_result = ResponseFrame.from_raw(frame)
                    if rf_result.is_ok():
                        rf_events.add(rf_result.unwrap())
                    rf_event_queue.put(rf_result)
                    self._frame_buffer.clear()
                    self.state = ParserState.IDLE
                    return
                elif next_byte == b"\r":
                    # Might be ]\r\n
                    if data_buffer.available() < 2:
                        # Wait for more data
                        return
                    next_two = data_buffer.peek(2)
                    if next_two == b"\r\n":
                        # Frame ends with ]\r\n
                        self._frame_buffer.extend(data_buffer.read(2))
                        frame = bytes(self._frame_buffer)
                        self.logger.debug(f"RX Event Frame: {frame!r}")
                        rf_result = ResponseFrame.from_raw(frame)
                        if rf_result.is_ok():
                            rf_events.add(rf_result.unwrap())
                        rf_event_queue.put(rf_result)
                        self._frame_buffer.clear()
                        self.state = ParserState.IDLE
                        return

            # Check size limit after each byte
            if len(self._frame_buffer) > 200:
                self.logger.error(f"Event frame exceeded 200 bytes: {bytes(self._frame_buffer)!r}")
                # Output accumulated data as binary instead of discarding it
                data_queue.put(bytes(self._frame_buffer))
                self._frame_buffer.clear()
                self.state = ParserState.IDLE
                return

    def _parse_command_frame(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data in IN_COMMAND_FRAME state - wait for closing bracket ]."""
        # Check timeout
        elapsed = time.time() - self._frame_start_time
        if elapsed > 6.0:
            self.logger.error(f"Command frame timeout after {elapsed:.1f}s: {bytes(self._frame_buffer)!r}")
            # Output as binary data since it's not a valid frame
            if len(self._frame_buffer) > 0:
                data_queue.put(bytes(self._frame_buffer))
            self._frame_buffer.clear()
            self.state = ParserState.IDLE
            return

        # Check size limit
        if len(self._frame_buffer) > 200:
            buffer_bytes = bytes(self._frame_buffer)
            self.logger.error(f"Command frame exceeded 200 bytes: {buffer_bytes[:100]!r}...")
            # Check if there's a valid frame ending somewhere in the buffer
            # This handles the case where binary data starting with [letter is followed by a real frame

            # Look for ]\r\n or ]\n patterns
            frame_end_rn = buffer_bytes.find(b"]\r\n")
            frame_end_n = buffer_bytes.find(b"]\n")

            # Use whichever comes first (if any)
            frame_end = -1
            end_length = 0
            if frame_end_rn != -1 and (frame_end_n == -1 or frame_end_rn < frame_end_n):
                frame_end = frame_end_rn
                end_length = 3
            elif frame_end_n != -1:
                frame_end = frame_end_n
                end_length = 2

            if frame_end != -1:
                # Found a frame ending! Split the buffer
                # Everything before frame_end is binary, frame_end to frame_end+end_length is the frame
                if frame_end > 0:
                    data_queue.put(buffer_bytes[:frame_end])

                # Search backwards from the frame end to find [letter pattern
                frame_start = -1
                for i in range(frame_end - 1, -1, -1):
                    if buffer_bytes[i : i + 1] == b"[" and i + 1 < frame_end:
                        next_char = buffer_bytes[i + 1 : i + 2]
                        if next_char and next_char.isalpha():
                            frame_start = i
                            break

                if frame_start != -1:
                    # Found the frame start
                    frame_data = buffer_bytes[frame_start : frame_end + end_length]
                    self.logger.debug(f"RX Command Frame (extracted): {frame_data!r}")
                    rf_queue.put(ResponseFrame.from_raw(frame_data))
                    # Put any remaining data after the frame back for reprocessing
                    if frame_end + end_length < len(buffer_bytes):
                        # Put remaining bytes back into the buffer
                        remainder = buffer_bytes[frame_end + end_length :]
                        for _ in remainder:
                            pass  # data_buffer.putback(bytes([byte]))
                else:
                    # No valid frame start found, output everything as binary
                    data_queue.put(buffer_bytes)
            else:
                # No frame ending found, output all as binary
                data_queue.put(buffer_bytes)

            self._frame_buffer.clear()
            self.state = ParserState.IDLE
            return

        # Read byte by byte looking for closing bracket ]
        while data_buffer.available() > 0:
            byte = data_buffer.read(1)
            self._frame_buffer.extend(byte)

            # Check for closing bracket
            if byte == b"]":
                # Found closing bracket, now consume the newline
                if data_buffer.available() == 0:
                    # Wait for more data (the newline)
                    return

                next_byte = data_buffer.peek(1)
                if next_byte == b"\n":
                    # Frame ends with ]\n
                    self._frame_buffer.extend(data_buffer.read(1))
                    frame = bytes(self._frame_buffer)
                    self.logger.debug(f"RX Command Frame: {frame!r}")
                    rf_queue.put(ResponseFrame.from_raw(frame))
                    self._frame_buffer.clear()
                    self.state = ParserState.IDLE
                    return
                elif next_byte == b"\r":
                    # Might be ]\r\n
                    if data_buffer.available() < 2:
                        # Wait for more data
                        return
                    next_two = data_buffer.peek(2)
                    if next_two == b"\r\n":
                        # Frame ends with ]\r\n
                        self._frame_buffer.extend(data_buffer.read(2))
                        frame = bytes(self._frame_buffer)
                        self.logger.debug(f"RX Command Frame: {frame!r}")
                        rf_queue.put(ResponseFrame.from_raw(frame))
                        self._frame_buffer.clear()
                        self.state = ParserState.IDLE
                        return

            # Check size limit after each byte
            if len(self._frame_buffer) > 200:
                buffer_bytes = bytes(self._frame_buffer)
                self.logger.error(f"Command frame exceeded 200 bytes: {buffer_bytes[:100]!r}...")
                # Check if there's a valid frame ending somewhere in the buffer
                # This handles the case where binary data starting with [letter is followed by a real frame

                # Look for ]\r\n or ]\n patterns
                frame_end_rn = buffer_bytes.find(b"]\r\n")
                frame_end_n = buffer_bytes.find(b"]\n")

                # Use whichever comes first (if any)
                frame_end = -1
                end_length = 0
                if frame_end_rn != -1 and (frame_end_n == -1 or frame_end_rn < frame_end_n):
                    frame_end = frame_end_rn
                    end_length = 3
                elif frame_end_n != -1:
                    frame_end = frame_end_n
                    end_length = 2

                if frame_end != -1:
                    # Found a frame ending! Split the buffer
                    # Everything before frame_end is binary, frame_end to frame_end+end_length is the frame
                    if frame_end > 0:
                        data_queue.put(buffer_bytes[:frame_end])

                    # Search backwards from the frame end to find [letter pattern
                    frame_start = -1
                    for i in range(frame_end - 1, -1, -1):
                        if buffer_bytes[i : i + 1] == b"[" and i + 1 < frame_end:
                            next_char = buffer_bytes[i + 1 : i + 2]
                            if next_char and next_char.isalpha():
                                frame_start = i
                                break

                    if frame_start != -1:
                        # Found the frame start
                        frame_data = buffer_bytes[frame_start : frame_end + end_length]
                        self.logger.debug(f"RX Command Frame (extracted): {frame_data!r}")
                        rf_queue.put(ResponseFrame.from_raw(frame_data))
                        # Put any remaining data after the frame back for reprocessing
                        if frame_end + end_length < len(buffer_bytes):
                            # Put remaining bytes back into the buffer
                            remainder = buffer_bytes[frame_end + end_length :]
                            for _ in remainder:
                                pass  # data_buffer.putback(bytes([byte]))
                    else:
                        # No valid frame start found, output everything as binary
                        data_queue.put(buffer_bytes)
                else:
                    # No frame ending found, output all as binary
                    data_queue.put(buffer_bytes)

                self._frame_buffer.clear()
                self.state = ParserState.IDLE
                return

    def _parse_binary_data(
        self,
        data_buffer: SafeIOFIFOBuffer,
        rf_queue: Any,
        rf_event_queue: Any,
        rf_events: Any,
        data_queue: Any,
    ) -> None:
        """Parse data in IN_BINARY_DATA state - accumulate until frame start or chunk limit."""
        # Read data looking for potential frame starts
        while data_buffer.available() > 0:
            byte = data_buffer.peek(1)

            # Check if this might be a frame start
            if byte == b"[" and data_buffer.available() >= 2:
                next_two = data_buffer.peek(2)

                # Check if this looks like a real frame start
                if next_two == b"[*" or (len(next_two) == 2 and next_two[1:2].isalpha()):
                    # Found a potential frame start
                    # First, output any accumulated binary data
                    if len(self._binary_buffer) > 0:
                        chunk = bytes(self._binary_buffer)
                        self.logger.trace(f"RX Binary Data: {len(chunk)} bytes")  # type: ignore[attr-defined]
                        data_queue.put(chunk)
                        self._binary_buffer.clear()

                    # Transition to IDLE to determine frame type
                    self.state = ParserState.IDLE
                    return

            # Not a frame start, accumulate as binary data
            byte = data_buffer.read(1)
            self._binary_buffer.extend(byte)

            # Send chunks of binary data to avoid memory issues
            if len(self._binary_buffer) >= 8192:
                chunk = bytes(self._binary_buffer[:8192])
                self.logger.trace(f"RX Binary Data: {len(chunk)} bytes")  # type: ignore[attr-defined]
                data_queue.put(chunk)
                self._binary_buffer = self._binary_buffer[8192:]

        # Buffer exhausted - if we have accumulated binary data, send it now
        # Don't wait for more data or a chunk threshold
        if len(self._binary_buffer) > 0:
            chunk = bytes(self._binary_buffer)
            self.logger.trace(f"RX Binary Data (flush): {len(chunk)} bytes")  # type: ignore[attr-defined]
            data_queue.put(chunk)
            self._binary_buffer.clear()
            # Stay in IDLE state to check for new data type
            self.state = ParserState.IDLE
