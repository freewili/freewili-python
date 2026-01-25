"""Frame parser state machine for FreeWili serial communication."""

import enum
import logging
import queue
import time
from dataclasses import dataclass

from freewili.framing import ResponseFrame, ResponseFrameType
from freewili.safe_reponse_frame_dict import SafeResponseFrameDict
from freewili.util.fifo import SafeIOFIFOBuffer


class ParserState(enum.Enum):
    """State machine states for frame parsing."""

    IDLE = enum.auto()
    IN_POSSIBLE_FRAME = enum.auto()
    IN_EVENT_FRAME = enum.auto()
    IN_COMMAND_FRAME = enum.auto()
    IN_BINARY_DATA = enum.auto()


@dataclass(frozen=True)
class FrameParserArgs:
    """Arguments for FrameParser methods."""

    data_buffer: SafeIOFIFOBuffer
    rf_queue: queue.Queue
    rf_event_queue: queue.Queue
    rf_events: SafeResponseFrameDict
    data_queue: queue.Queue


class FrameParser:
    """State machine for parsing FreeWili serial frames."""

    def __init__(self, args: FrameParserArgs, logger: logging.Logger | None = None):
        """Initialize the frame parser.

        Parameters:
        -----------
            logger: logging.Logger | None
                Logger instance for debug output
        """
        self.args: FrameParserArgs = args
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

    def parse(self) -> None:
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

        while self.args.data_buffer.available() > 0 and iterations < max_iterations:
            iterations += 1
            prev_available = self.args.data_buffer.available()
            prev_state = self.state

            # In binary-only mode, treat everything as binary data
            if self._binary_only_mode:
                chunk = self.args.data_buffer.read(-1)
                if chunk:
                    self.logger.trace(f"RX Binary Data (binary-only mode): {len(chunk)} bytes")  # type: ignore[attr-defined]
                    self.args.data_queue.put(chunk)
                break

            match self.state:
                case ParserState.IDLE:
                    self._parse_idle()
                case ParserState.IN_EVENT_FRAME:
                    self._parse_frame()
                case ParserState.IN_COMMAND_FRAME:
                    self._parse_frame()
                case _:
                    self.logger.error(f"Unknown parser state: {self.state}")
                    raise RuntimeError(f"Unknown parser state: {self.state}")

            # Throttle iterations to avoid busy looping
            if iterations % 100 == 0:
                time.sleep(0.001)

            # If buffer size didn't change AND state didn't change, we're waiting for more data
            # Break to avoid infinite loop
            # But if state changed (e.g., IDLE -> IN_EVENT_FRAME), continue even if buffer unchanged
            if self.args.data_buffer.available() == prev_available and self.state == prev_state:
                break

    def _parse_idle(self) -> None:
        """Parse data in IDLE state - check for '[' to enter frame detection."""
        if self.args.data_buffer.available() == 0:
            return

        data: bytes = self.args.data_buffer.peek(-1)
        is_start, index = ResponseFrame.contains_start_of_frame(data)
        if not is_start:
            self.args.data_queue.put(self.args.data_buffer.read(len(data)))
            return
        # we need to dump any data before the frame start as binary (ie. 'asdf[' )
        if index - 1 > 0:
            self.args.data_queue.put(self.args.data_buffer.read(index - 1))
        # Found a frame start at index
        match ResponseFrame.validate_start_of_frame(data[index:]):
            case (ResponseFrameType.Event, _):
                self.logger.debug("Detected event frame start in IDLE")
                self.state = ParserState.IN_EVENT_FRAME
            case (ResponseFrameType.Standard, _):
                self.logger.debug("Detected command frame start in IDLE")
                self.state = ParserState.IN_COMMAND_FRAME
            case (ResponseFrameType.Invalid, _):
                self.logger.debug("Not a valid frame start in IDLE")
                # recursively call to handle remaining data incase we have another frame start
                # eat the first byte which should be a '['
                self.args.data_queue.put(self.args.data_buffer.read(1))
                self._parse_idle()
            case _:
                raise RuntimeError("Unexpected result from validate_start_of_frame")

    def _parse_frame(self) -> None:
        """Parse data in IN_EVENT_FRAME state - wait for closing bracket ]."""
        data: bytes = self.args.data_buffer.peek(-1)
        is_end, index = ResponseFrame.contains_end_of_frame(data)
        if not is_end and len(data) >= 100:
            # No end found and buffer is large - treat as binary data
            self.logger.error(f"Event frame exceeded 100 bytes: {data[:100]!r}")
            self.args.data_queue.put(self.args.data_buffer.read(len(data)))
            self.state = ParserState.IDLE
            return
        frame_data = data[: index + 1]
        # Consume frame data from buffer
        self.args.data_queue.put(self.args.data_buffer.read(len(frame_data)))
        rf = ResponseFrame.from_raw(frame_data)
        if not rf.is_ok():
            # Invalid frame - treat as binary data
            self.logger.error(f"Invalid event frame: {frame_data!r}")
            self.state = ParserState.IDLE
            return
        match rf.unwrap().rf_type:
            case ResponseFrameType.Event:
                self.logger.debug(f"RX Event Frame: {frame_data!r}")
                self.args.rf_event_queue.put(rf)
            case ResponseFrameType.Standard:
                self.logger.debug(f"RX Frame: {frame_data!r}")
                self.args.rf_queue.put(rf)
            case _:
                self.logger.error(f"Expected event frame but got {rf.unwrap().rf_type}: {frame_data!r}")
                raise RuntimeError("Unexpected frame type in event frame parser")
        self.state = ParserState.IDLE
