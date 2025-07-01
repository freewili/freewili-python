"""Serial Port Reader/Writer."""

import queue
import threading
import time
from queue import Queue
from typing import Any

from result import Err, Ok, Result
from serial import Serial, SerialException

from freewili.framing import ResponseFrame
from freewili.util.fifo import SafeIOFIFOBuffer


class SerialPort(threading.Thread):
    """Read/Write data to a serial port."""

    def __init__(self, port: str, baudrate: int = 1000000, name: str = ""):
        self._debug_enabled = False
        self._name = name
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
        # data other than a response frame
        self.data_queue: Queue = Queue()

        self.start()

    def shutdown(self) -> None:
        """Shutdown the reader."""
        self._running.clear()
        self.join()

    def open(self, block: bool = True, timeout_sec: float = 6.0) -> Result[None, str]:
        """Open the serial port.

        See also: is_open()

        Parameters:
        ----------
            block: bool:
                If True, block until the serial port is opened.
            timeout_sec: float:
                number of seconds to wait when blocking.

        Returns:
        -------
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
        ----------
            block: bool:
                If True, block until the serial port is closed.
            timeout_sec: float:
                number of seconds to wait when blocking.

        Returns:
        -------
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
        ----------
            None

        Returns:
        -------
            bool:
                True if open, False if closed.
        """
        return self._is_connected

    def has_error(self) -> bool:
        """Return if the serial port is in an error state.

        To clear the error state, call get_error().

        Parameters:
        ----------
            None

        Returns:
        -------
            bool:
                True if there are errors, False otherwise.
        """
        return self._in_error.is_set()

    def get_error(self) -> str:
        """Get the serial port error message. Clears the error state.

        Parameters:
        ----------
            None

        Returns:
        -------
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
        -------
            str:
                serial port descriptor.
        """
        return self._port

    @property
    def baudrate(self) -> int:
        """Get the serial port baudrate.

        Returns:
        -------
            str:
                serial port baudrate.
        """
        return self._baudrate

    def run(self) -> None:
        """Thread handler function. Call Self.start() to initialize."""
        self._debug_print(f"Started {self._port}...\n")
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
                            self._debug_print(f"[{time.time() - start_time:.3f}] Opening {self._port}...\n")
                            serial_port = Serial(
                                self._port,
                                baudrate=1000000,
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
                        self._debug_print(f"[{time.time() - start_time:.3f}] Closing {self._port}...\n")
                        serial_port.close()
                        serial_port = None
                        self._is_connected = False
                        continue
                    elif serial_port and not self.send_queue.empty():
                        self._debug_print(
                            f"[{time.time() - start_time:.3f}] Send queue not empty yet, waiting to close port...\n"
                        )
                    else:
                        # serial_port isn't valid here, tight loop back to the beginning.
                        time.sleep(0.001)
                        continue
                # Send data
                try:
                    send_data, delay_sec = self.send_queue.get_nowait()
                    # self._debug_print(f"[{time.time() - start_time:.3f}] sending: ", send_data, self._port)
                    write_len = serial_port.write(send_data)
                    # self._debug_print(f"[{time.time() - start_time:.3f}]: Delaying for {delay_sec:.3f} seconds...")
                    time.sleep(delay_sec)
                    self.send_queue.task_done()
                    if len(send_data) != write_len:
                        self._debug_print("[{time.time()-start_time:.3f}] ERROR: send_data != write_len")
                    assert len(send_data) == write_len, f"{len(send_data)} != {write_len}"
                except queue.Empty:
                    pass
                # Read data
                if serial_port.in_waiting > 0:
                    # self._debug_print(f"[{time.time() - start_time:.3f}] Reading {serial_port.in_waiting}...")
                    data = serial_port.read(4096)
                    if data != b"":
                        read_buffer.write(data)
                        # self._debug_print(f"[{time.time() - start_time:.3f}] RX: ", repr(data), len(data))
                    # self._debug_print("handle data...")
                self._handle_data(read_buffer)
            except Exception as ex:
                self._error_msg = str(ex)
                self._debug_print(f"Exception: {type(ex)}: {self._error_msg}")
                self._in_error.set()
                if serial_port and serial_port.is_open:
                    serial_port.close()
                    serial_port = None
        if serial_port:
            serial_port.close()
        self._debug_print("Done.")

    def _debug_print(self, *args: Any, **kwargs: Any) -> None:
        if self._debug_enabled:
            print(*args, **kwargs)

    _debug_count: int = 0

    def _handle_data(self, data_buffer: SafeIOFIFOBuffer) -> None:
        assert isinstance(data_buffer, SafeIOFIFOBuffer)
        if data_buffer.available() == 0:
            return
        # Match a full event response frame
        while frame := data_buffer.pop_first_match(rb"\[\*.*.\d\]\r?\n"):
            self._debug_print(f"RX Event Frame: {frame!r}")
            # self._debug_print(f"Buffer len: {data_buffer.available()} {data_buffer.peek()!r}")
            self.rf_event_queue.put(ResponseFrame.from_raw(frame))
            _debug_count = 0
        # Match a full response frame
        while frame := data_buffer.pop_first_match(rb"\[[^\*].*.\d\]\r?\n"):
            self._debug_print(f"RX Frame: {frame!r}")
            # self._debug_print(f"Buffer len: {data_buffer.available()} {data_buffer.peek()!r}")
            self.rf_queue.put(ResponseFrame.from_raw(frame))
            self._debug_count = 0
        # Match anything else
        try:
            # add anything before [ to the data queue
            start, end = data_buffer.contains(rb"\[")
            if start > 0:
                data = data_buffer.read(start)
                self._debug_print(f"RX Data: {len(data)}: {self._debug_count}: {data!r}")
                self.data_queue.put(data)
                self._debug_count += len(data)
        except ValueError:
            pass

        # At this point we should be at the start of a frame
        data_len = data_buffer.available()
        data = data_buffer.peek(data_len)
        # If we only have a single byte and it's a [, we are done
        if data_len == 1 and data == b"[":
            return
        if data_len == 2 and data == b"[*":
            return
        if data_len >= 3:
            try:
                # [*f or [a\
                _start, _end = data_buffer.contains(rb"(\[\*)|(\[.\\)|(\[. )")
                # This is probably a start of a frame, do nothing
                return
            except ValueError:
                pass
        data = data_buffer.read(-1)
        self._debug_print(f"RX Data: {len(data)}: {self._debug_count}: {data!r}")
        self.data_queue.put(data)
        self._debug_count += len(data)

    def send(
        self,
        data: bytes | str,
        append_newline: bool = True,
        newline_chars: str = "\n",
        delay_sec: float = 0.001,
        wait: bool = True,
    ) -> None:
        r"""Send data to the serial port.

        Parameters:
        ----------
            data : bytes | str:
                data to be sent to the serial port. If type is str it will be automatically encoded.
            append_newline : bool:
                Appends "\r\n" to the data if True.
            newline_chars : str:
                Appends to data if append_newline is True.
            delay_sec : float:
                Number of seconds to wait after sending.

        Returns:
        -------
            None
        """
        assert isinstance(data, (bytes, str))
        if isinstance(data, str):
            data = data.encode("ascii")
        if append_newline:
            data += newline_chars.encode("ascii")
        self._debug_print("send:", data, delay_sec)
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
