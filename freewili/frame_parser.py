"""Frame parser state machine for FreeWili serial communication."""

import enum
import logging
from typing import Any

from freewili.framing import ResponseFrame
from freewili.util.fifo import SafeIOFIFOBuffer


class ParserState(enum.Enum):
    """State machine states for frame parsing."""

    SEARCHING = enum.auto()
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
        self.state = ParserState.SEARCHING
        self.logger = logger or logging.getLogger(__name__)
        self._debug_count: int = 0

    def reset(self) -> None:
        """Reset the parser state to initial conditions."""
        self.state = ParserState.SEARCHING
        self._debug_count = 0

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
        if data_buffer.available() == 0:
            return

        # First, try to match complete response frames (these have specific patterns)
        # Match a full event response frame: [*...number]\r?\n
        while frame := data_buffer.pop_first_match(rb"\[\*.*\d\]\r?\n"):
            self.logger.debug(f"RX Event Frame: {frame!r}")
            rf_result = ResponseFrame.from_raw(frame)
            if rf_result.is_ok():
                rf_events.add(rf_result.unwrap())
            rf_event_queue.put(rf_result)
            self._debug_count = 0

        # Match a full response frame: [letter/command...number]\r?\n
        while frame := data_buffer.pop_first_match(rb"\[[a-zA-Z][^\]]*\d\]\r?\n"):
            self.logger.debug(f"RX Frame: {frame!r}")
            rf_queue.put(ResponseFrame.from_raw(frame))
            self._debug_count = 0

        # After removing all complete frames, handle remaining data in the buffer
        data_len = data_buffer.available()
        if data_len == 0:
            return

        # Look at the beginning of the buffer to determine what to do
        peek_size = min(data_len, 100)
        data = data_buffer.peek(peek_size)

        # Check for partial frame patterns at the very beginning
        if data.startswith(b"["):
            # Look for common frame start patterns
            frame_patterns = [
                rb"\[\*",  # Event frame start like [*filedl...]
                rb"\[[a-zA-Z]",  # Command response frame start like [u...]
            ]

            is_likely_frame_start = any(data.startswith(pattern) for pattern in frame_patterns)

            if is_likely_frame_start:
                # Look for the end of this potential frame
                frame_end_found = False
                try:
                    # Look for frame end patterns
                    end_pos = data.find(b"]\r\n")
                    if end_pos == -1:
                        end_pos = data.find(b"]\n")

                    if end_pos != -1:
                        frame_end_found = True
                    elif data_len < 200:  # Small buffer, might be incomplete frame
                        return  # Wait for more data
                    # If large buffer but no frame end, treat as binary data
                except Exception:
                    is_likely_frame_start = False

                if not frame_end_found and data_len > 200:
                    is_likely_frame_start = False

            if not is_likely_frame_start:
                # This '[' is probably binary data, not a frame start
                # Find the next potential real frame or take a reasonable chunk
                next_frame_pos = -1
                search_limit = min(data_len, 2048)  # Don't search too far

                for i in range(1, search_limit):
                    # Look for patterns that are very likely to be real frame starts
                    if i + 1 < search_limit:
                        two_byte_pattern = data[i : i + 2]
                        if two_byte_pattern in [b"[*", b"[u", b"[f", b"[g", b"[i", b"[o", b"[s"]:
                            # Additional validation - check if this looks like a real frame
                            remaining = data[i : i + 50] if i + 50 < data_len else data[i:]
                            if b"]" in remaining:  # Has potential frame end
                                next_frame_pos = i
                                break

                if next_frame_pos > 0:
                    # Take data up to the next potential frame
                    chunk = data_buffer.read(next_frame_pos)
                else:
                    # Take a reasonable chunk to avoid memory issues
                    chunk_size = min(data_len, 8192)  # 8KB chunks for binary data
                    chunk = data_buffer.read(chunk_size)

                if chunk:
                    self.logger.trace(f"RX Binary Data: {len(chunk)} bytes")  # type: ignore[attr-defined]
                    data_queue.put(chunk)
                    self._debug_count += len(chunk)
                return
            else:
                # This looks like a valid frame start, but incomplete
                # Wait for more data if buffer is small
                if data_len < 200:
                    return
        else:
            # Data doesn't start with '[', so it's clearly binary data
            # Take all available data
            chunk = data_buffer.read(-1)
            if chunk:
                self.logger.trace(f"RX Binary Data: {len(chunk)} bytes")  # type: ignore[attr-defined]
                data_queue.put(chunk)
                self._debug_count += len(chunk)
            return

        # If we reach here, we have what looks like a partial frame at the start
        # For very small buffers, wait for more data
        if data_len <= 3:
            return
