"""Serial Port Reader/Writer."""

import logging
import os
import queue
import threading
import time
from queue import Queue
from typing import Any

from result import Err, Ok, Result
from serial import Serial, SerialException

from freewili.frame_parser import FrameParser, FrameParserArgs
from freewili.safe_response_frame_dict import SafeResponseFrameDict
from freewili.util.fifo import SafeIOFIFOBuffer

# Add custom TRACE level (more verbose than DEBUG)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def trace(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    """Log a message with severity 'TRACE'."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


logging.Logger.trace = trace  # type: ignore[attr-defined]

# Record program start time for elapsed time logging
_program_start_time = time.time()


class ElapsedTimeFormatter(logging.Formatter):
    """Custom formatter that shows elapsed milliseconds from program start."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with elapsed milliseconds from program start."""
        elapsed_ms = (record.created - _program_start_time) * 1000
        record.elapsed_ms = f"{elapsed_ms:8.1f}ms"
        return super().format(record)


def enable_trace_logging() -> None:
    """Enable TRACE level logging by adding trace() method to logging.Logger.

    This modifies the logging.Logger class globally. Call this function explicitly
    if you want to use logger.trace() calls throughout your application.

    Example:
        from freewili.serialport import enable_trace_logging
        enable_trace_logging()
        logger.trace("Very verbose message")
    """

    def trace(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a message with severity 'TRACE'."""
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    logging.Logger.trace = trace  # type: ignore[attr-defined]


def configure_logging(log_level: str | None = None) -> None:
    """Configure root logger with elapsed time formatting.

    This function is called automatically when the module is imported,
    using the PYFW_LOG_LEVEL environment variable. You can also call
    it explicitly to change the log level at runtime.

    Parameters:
    -----------
        log_level : str | None
            Log level to set. Can be 'trace', 'debug', 'info', 'warning', 'error'.
            If None, reads from PYFW_LOG_LEVEL environment variable.
            Defaults to 'warning' if not specified.

    Example:
        from freewili.serialport import configure_logging
        configure_logging('debug')  # Change log level at runtime
    """
    if log_level is None:
        log_level = os.getenv("PYFW_LOG_LEVEL", "warning").lower()
    else:
        log_level = log_level.lower()

    root_logger = logging.getLogger()
    if log_level == "trace":
        root_logger.setLevel(TRACE)
    elif log_level == "debug":
        root_logger.setLevel(logging.DEBUG)
    elif log_level == "info":
        root_logger.setLevel(logging.INFO)
    elif log_level == "error":
        root_logger.setLevel(logging.ERROR)
    else:
        root_logger.setLevel(logging.WARNING)

    # Ensure we have a handler with the right format
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ElapsedTimeFormatter("[%(elapsed_ms)s] %(levelname)-5s %(name)s: %(message)s"))
        root_logger.addHandler(handler)


class SerialPort(threading.Thread):
    """Read/Write data to a serial port."""

    def __init__(self, port: str, baudrate: int = 1000000, name: str = ""):
        self._name = name
        self.logger = logging.getLogger(f"SerialPort.{port}.{name}" if name else f"SerialPort.{port}")
        super().__init__(daemon=True, name=f"Thread-SerialPort-{port}-{name}")
        self._port = port
        self._baudrate = baudrate
        self._running = threading.Event()
        self._running.set()
        self._connect = threading.Event()
        self._is_connected: bool = False
        self._in_error = threading.Event()
        self._error_msg: str = ""

        self.send_queue: Queue = Queue()
        # Response frame queue
        self.rf_queue: Queue = Queue()
        self.rf_event_queue: Queue = Queue()
        self.rf_events: SafeResponseFrameDict = SafeResponseFrameDict()
        # data other than a response frame
        self.data_queue: Queue = Queue()

        # Initialize the frame parser
        self.frame_parser = FrameParser(
            FrameParserArgs(
                data_buffer=SafeIOFIFOBuffer(blocking=False),
                rf_queue=self.rf_queue,
                rf_event_queue=self.rf_event_queue,
                rf_events=self.rf_events,
                data_queue=self.data_queue,
            ),
            logger=self.logger,
        )

        self.start()

    def shutdown(self) -> None:
        """Shutdown the reader."""
        self._running.clear()
        self.join()

    def open(self, block: bool = True, timeout_sec: float = 6.0) -> Result[None, str]:
        """Open the serial port.

        See also: is_open()

        Parameters:
        -----------
            block: bool:
                If True, block until the serial port is opened.
            timeout_sec: float:
                number of seconds to wait when blocking.

        Returns:
        --------
            None

        Raises:
        ------
            TimeoutError:
                When blocking is True and time elapsed is greater than timeout_sec
        """
        assert isinstance(block, bool)
        assert isinstance(timeout_sec, float)
        self._connect.set()
        if block:
            start = time.time()
            while time.time() - start < timeout_sec and not self.is_open():
                if self.has_error():
                    break
                time.sleep(0.001)
            if not self.is_open():
                return Err(f"Failed to open in {timeout_sec:.1f} seconds: {self.get_error()}")
        else:
            return Ok(None)
        if not self.is_open():
            return Err(f"Failed to open serial Port: {self.get_error()}")
        return Ok(None)

    def close(self, block: bool = True, timeout_sec: float = 6.0) -> None:
        """Close the serial port.

        See also: is_open()

        Parameters:
        -----------
            block: bool:
                If True, block until the serial port is closed.
            timeout_sec: float:
                number of seconds to wait when blocking.

        Returns:
        --------
            None

        Raises:
        ------
            TimeoutError:
                When blocking is True and time elapsed is greater than timeout_sec
        """
        assert isinstance(block, bool)
        assert isinstance(timeout_sec, float)
        self._connect.clear()
        if block:
            start = time.time()
            current = time.time()
            while current - start < timeout_sec and self.is_open():
                current = time.time()
                time.sleep(0.001)
            if self.is_open():
                raise TimeoutError(f"Failed to close serial port in {timeout_sec:.1f} seconds.")

    def is_open(self) -> bool:
        """Return if the serial port is open.

        Parameters:
        -----------
            None

        Returns:
        --------
            bool:
                True if open, False if closed.
        """
        return self._is_connected

    def has_error(self) -> bool:
        """Return if the serial port is in an error state.

        To clear the error state, call get_error().

        Parameters:
        -----------
            None

        Returns:
        --------
            bool:
                True if there are errors, False otherwise.
        """
        return self._in_error.is_set()

    def get_error(self) -> str:
        """Get the serial port error message. Clears the error state.

        Parameters:
        -----------
            None

        Returns:
        --------
            str:
                Error message if present, empty str otherwise.
        """
        if not self.has_error():
            return ""
        msg = self._error_msg
        self._in_error.clear()
        return msg

    @property
    def port(self) -> str:
        """Get the serial port descriptor.

        Returns:
        --------
            str:
                serial port descriptor.
        """
        return self._port

    @property
    def baudrate(self) -> int:
        """Get the serial port baudrate.

        Returns:
        --------
            str:
                serial port baudrate.
        """
        return self._baudrate

    def run(self) -> None:
        """Thread handler function. Call Self.start() to initialize."""
        self.logger.debug(f"Started {self._port}...")
        serial_port: None | Serial = None
        # read_buffer_data: bytearray = bytearray()
        # read_buffer = io.BytesIO()
        read_buffer = SafeIOFIFOBuffer(blocking=False)
        start_time = time.time()
        while self._running.is_set():
            if self._in_error.is_set():
                time.sleep(0.001)
                continue
            try:
                # Configure the serial port
                if self._connect.is_set():
                    # We are allowed to connect
                    if not serial_port:
                        try:
                            self.logger.debug(f"[{time.time() - start_time:.3f}] Opening {self._port}...")
                            serial_port = Serial(
                                self._port,
                                baudrate=self._baudrate,
                                timeout=0.001,
                                exclusive=True,
                                rtscts=False,
                                xonxoff=False,
                                dsrdtr=False,
                            )
                            # This is absolutely needed, for some reason writing data too fast after open
                            # will corrupt things and the read buffer does strange things.
                            # 0.1 was successful 50% of the time in my testing and 0.2 was 100% successful.
                            # 0.5 should allow for other slower systems if its a timing issue on the OS kernel level?
                            time.sleep(0.5)
                            self._is_connected = True
                        except SerialException as ex:
                            print(ex)
                            self._error_msg = str(ex)
                            self._in_error.set()
                            continue
                else:
                    # We are allowed to disconnect
                    if serial_port and self.send_queue.empty():
                        self.logger.debug(f"[{time.time() - start_time:.3f}] Closing {self._port}...")
                        serial_port.close()
                        serial_port = None
                        self._is_connected = False
                        continue
                    elif serial_port and not self.send_queue.empty():
                        self.logger.debug(
                            f"[{time.time() - start_time:.3f}] Send queue not empty yet, waiting to close port..."
                        )
                    else:
                        # serial_port isn't valid here, tight loop back to the beginning.
                        time.sleep(0.001)
                        continue
                # Send data
                try:
                    send_data, delay_sec = self.send_queue.get_nowait()
                    if not serial_port or not serial_port.is_open:
                        self.logger.error(
                            f"[{time.time() - start_time:.3f}] ERROR: Attempted to write but serial port is not open."
                        )
                        self.send_queue.task_done()
                        continue
                    self.logger.trace(f"[{time.time() - start_time:.3f}] sending: {send_data!r} {self._port}")  # type: ignore[attr-defined]
                    write_len = serial_port.write(send_data)
                    self.logger.trace(f"[{time.time() - start_time:.3f}]: Delaying for {delay_sec:.3f} seconds...")  # type: ignore[attr-defined]
                    time.sleep(delay_sec)
                    self.send_queue.task_done()
                    if len(send_data) != write_len:
                        self.logger.error(f"[{time.time() - start_time:.3f}] ERROR: send_data != write_len")
                    assert len(send_data) == write_len, f"{len(send_data)} != {write_len}"
                except queue.Empty:
                    pass
                # Read data
                if serial_port and serial_port.is_open and serial_port.in_waiting > 0:
                    self.logger.trace(f"[{time.time() - start_time:.3f}] Reading {serial_port.in_waiting}...")  # type: ignore[attr-defined]
                    data = serial_port.read(4096)
                    if data != b"":
                        read_buffer.write(data)
                        self.logger.trace(f"[{time.time() - start_time:.3f}] RX: {data!r} {len(data)}")  # type: ignore[attr-defined]
                    self.logger.trace("handle data...")  # type: ignore[attr-defined]
                # Process data through frame parser
                self.frame_parser.args.data_buffer.write(read_buffer.readall())
                self.frame_parser.parse()
            except Exception as ex:
                self._error_msg = str(ex)
                self.logger.error(f"Exception: {type(ex)}: {self._error_msg}")
                self._in_error.set()
                if serial_port and serial_port.is_open:
                    serial_port.close()
                    serial_port = None
                self._is_connected = False
        if serial_port:
            serial_port.close()
        self._is_connected = False
        self.logger.debug("Done.")

    _debug_count: int = 0

    def send(
        self,
        data: bytes | str,
        append_newline: bool = True,
        newline_chars: str = "\n",
        delay_sec: float = 0.000,
        wait: bool = True,
    ) -> None:
        r"""Send data to the serial port.

        Parameters:
        -----------
            data : bytes | str:
                data to be sent to the serial port. If type is str it will be automatically encoded.
            append_newline : bool:
                Appends "\r\n" to the data if True.
            newline_chars : str:
                Appends to data if append_newline is True.
            delay_sec : float:
                Number of seconds to wait after sending.

        Returns:
        --------
            None
        """
        assert isinstance(data, (bytes, str))
        if isinstance(data, str):
            data = data.encode("ascii")
        if append_newline:
            data += newline_chars.encode("ascii")
        self.logger.debug(f"send: {data!r} {delay_sec}")
        self.send_queue.put((data, delay_sec))
        if wait:
            self.send_queue.join()

    def clear(self) -> None:
        """Clear all the data in the queues."""
        queues = (self.rf_queue, self.data_queue)
        for q in queues:
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass
