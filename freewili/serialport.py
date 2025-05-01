"""Serial Port Reader/Writer."""

import queue
import threading
import time
from queue import Queue

from result import Err, Ok, Result
from serial import Serial, SerialException

from freewili.framing import ResponseFrame


class SerialPort(threading.Thread):
    """Read/Write data to a serial port."""

    def __init__(self, port: str, baudrate: int = 115200):
        super().__init__(daemon=True)
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
        print(f"Started {self._port}...\n")
        serial_port: None | Serial = None
        while self._running.is_set():
            if self._in_error.is_set():
                time.sleep(0.001)
                continue
            try:
                # Configure the serial port
                if self._connect.is_set() and not serial_port:
                    try:
                        serial_port = Serial(self._port, baudrate=9600, timeout=0.0, exclusive=True)
                        self._is_connected = True
                    except SerialException as ex:
                        print(ex)
                        self._error_msg = str(ex)
                        self._in_error.set()
                        continue
                else:
                    if serial_port:
                        serial_port.close()
                        serial_port = None
                        self._is_connected = False
                    time.sleep(0.001)
                    continue
                # Send data
                try:
                    send_data = self.send_queue.get(block=True, timeout=1.0)
                    print("sending: ", send_data, self._port)
                    write_len = serial_port.write(send_data)
                    time.sleep(0.25)
                    serial_port.flush()
                    assert len(send_data) == write_len
                except queue.Empty:
                    pass
                # Read data
                print("Reading...")
                data = serial_port.readline()
                print("Done Reading...")
                if not data:
                    continue
                data = data.decode("utf-8").strip()
                print("RX: ", repr(data), len(data))
                self._handle_data(data)
            except Exception as ex:
                self._error_msg = str(ex)
                self._in_error.set()
                if serial_port and serial_port.is_open:
                    serial_port.close()
                    serial_port = None
        if serial_port:
            serial_port.close()
        print("Done.")

    def _handle_data(self, data: str) -> None:
        assert isinstance(data, str)
        if ResponseFrame.is_frame(data):
            self.rf_queue.put(ResponseFrame.from_raw(data))
        else:
            self.data_queue.put(data)

    def send(self, data: bytes | str, append_newline: bool = True, newline_chars: str = "\n") -> None:
        r"""Send data to the serial port.

        Parameters:
        ----------
            data : bytes | str:
                data to be sent to the serial port. If type is str it will be automatically encoded.
            append_newline : bool:
                Appends "\r\n" to the data if True.
            newline_chars : str:
                Appends to data if append_newline is True.

        Returns:
        -------
            None
        """
        assert isinstance(data, (bytes, str))
        if isinstance(data, str):
            data = data.encode("ascii")
        if append_newline:
            data += newline_chars.encode("ascii")
        print("send:", data)
        self.send_queue.put(data)

    def clear(self) -> None:
        """Clear all the data in the queues."""
        queues = (self.rf_queue, self.data_queue)
        for q in queues:
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass
