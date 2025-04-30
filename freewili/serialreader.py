import queue
import threading
import time
from serial import Serial
from freewili.framing import ResponseFrame


class SerialReader(threading.Thread):
    def __init__(self, port: str):
        super().__init__()
        self._port = port
        self._running = threading.Event()
        self._running.set()
        # Allows the thread to close when main program exits
        self.daemon = True

        self.send_queue = queue.Queue()
        # Response frame queue
        self.rf_queue = queue.Queue()
        # data other than a response frame
        self.data_queue = queue.Queue()

    def close(self) -> None:
        """Shutdown the reader."""
        self._running.clear()
        self.join()

    @property
    def port(self) -> str:
        """Get the serial port descriptor.

        Returns:
        -------
            str:
                serial port descriptor.
        """
        return self._port

    def run(self) -> None:
        """Thread handler function. Call Self.start() to initialize."""
        serial_port = Serial(self._port, baudrate=9600, timeout=1.0, exclusive=True)
        while self._running.is_set():
            # Send data
            try:
                send_data = self.send_queue.get_nowait()
                print("got: ", send_data)
                write_len = serial_port.write(send_data)
                self.send_queue.task_done()
                assert len(send_data) == write_len
            except queue.Empty:
                pass
            # Read data
            if serial_port.in_waiting == 0:
                time.sleep(0.5)
                # print("DEBUG: in_waiting == 0 send qsize:", self.send_queue.qsize())
                continue
            data = serial_port.readline().decode("utf-8").strip()
            print("DEBUG RX: ", repr(data), len(data))
            self._handle_data(data)
        serial_port.close()

    def _handle_data(self, data: str) -> None:
        assert isinstance(data, str)
        if ResponseFrame.is_frame(data):
            self.rf_queue.put(ResponseFrame.from_raw(data))
        else:
            self.data_queue.put(data)

    def send(self, data: bytes | str, append_newline=True) -> None:
        """Send data to the serial port.

        Parameters:
        ----------
            data : bytes | str:
                data to be sent to the serial port. If type is str it will be automatically encoded.
            append_newline : bool:
                Appends "\r\n" to the string if True.

        Returns:
        -------
            None
        """
        assert isinstance(data, (bytes, str))
        if isinstance(data, str):
            data = data.encode("ascii")
        if append_newline:
            data += b"\r\n"
        print("send:", data)
        self.send_queue.put(data)

    def clear(self) -> None:
        """Clear all the data in the queues."""
        queues = (self.rf_queue, self.data_queue)
        for q in queues:
            try:
                while True:
                    q.get_nowait()
                    q.task_done()
            except queue.Empty:
                pass
