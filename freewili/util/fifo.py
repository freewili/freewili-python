"""FIFO buffer classes."""

import io
import re
import sys
import threading

if sys.version_info >= (3, 12):
    from typing import SupportsBuffer  # type: ignore

    BufferType = SupportsBuffer
else:
    BufferType = bytes | bytearray | memoryview


class SafeIOFIFOBuffer(io.RawIOBase):
    """A thread-safe, in-memory, FIFO byte stream buffer.

    Supports:
        - Blocking reads
        - Seeking and telling
        - Peeking
        - readline() and readuntil()
    Compatible with io.BufferedReader and other stream consumers.
    """

    def __init__(self, blocking: bool = True) -> None:
        """Initialize the FIFO buffer."""
        super().__init__()
        self._blocking = blocking
        self._buffer = bytearray()
        self._read_pos = 0
        self._lock = threading.RLock()
        self._not_empty = threading.Condition(self._lock)
        self._closed = False

    def write(self, b: BufferType) -> int:  # type: ignore
        """Write bytes to the end of the buffer.

        Arguments:
        ----------
            b (bytes or bytearray): Data to write.

        Returns:
        -------
            int: Number of bytes written.
        """
        if not isinstance(b, (bytes, bytearray)):
            raise TypeError("Input must be bytes or bytearray")
        with self._not_empty:
            self._buffer += b
            self._not_empty.notify_all()
            return len(b)

    def read(self, size: int = -1) -> bytes:
        """Read up to `size` bytes from the buffer.

        If `size` is negative, read all available data.
        In blocking mode blocks until enough data is available or the stream is closed.
        In non-blocking mode, returns up to size bytes or b"" if none.

        Arguments:
        ----------
            size (int): Number of bytes to read.

        Returns:
        -------
            bytes: Bytes read from the buffer.
        """
        with self._not_empty:
            self._check_closed()
            if not self._blocking:
                available = len(self._buffer) - self._read_pos
                if available == 0:
                    return b""
                if size < 0 or size > available:
                    size = available
                data = self._buffer[self._read_pos : self._read_pos + size]
                self._read_pos += size
                self._compact()
                return bytes(data)

            while True:
                available = len(self._buffer) - self._read_pos
                if size < 0 and available > 0:
                    break
                elif size >= 0 and available >= size:
                    break
                elif self._closed:
                    break
                self._not_empty.wait()

            available = len(self._buffer) - self._read_pos
            if size < 0 or size > available:
                size = available
            data = self._buffer[self._read_pos : self._read_pos + size]
            self._read_pos += size
            self._compact()
            return bytes(data)

    def readline(self, limit: int | None = -1) -> bytes:
        r"""Read a line ending in '\n' from the buffer.

        In blocking mode blocks until a full line is available, the limit is reached, or the stream is closed.
        In non-blocking mode, returns up to limit bytes or b"" if line not found.

        Arguments:
        ----------
            limit (int): Optional maximum number of bytes to read.

        Returns:
        -------
            bytes: A single line, including the trailing newline.
        """
        if limit is None:
            limit = -1
        with self._not_empty:
            self._check_closed()
            if not self._blocking:
                newline_pos = self._buffer.find(b"\n", self._read_pos)
                available = len(self._buffer) - self._read_pos
                if newline_pos != -1:
                    end = newline_pos + 1
                elif limit >= 0 and available >= limit:
                    end = self._read_pos + limit
                elif available > 0:
                    end = len(self._buffer)
                else:
                    return b""
                line = self._buffer[self._read_pos : end]
                self._read_pos = end
                self._compact()
                return bytes(line)

            while True:
                newline_pos = self._buffer.find(b"\n", self._read_pos)
                if newline_pos != -1:
                    end = newline_pos + 1
                    break
                available = len(self._buffer) - self._read_pos
                if limit >= 0 and available >= limit:
                    end = self._read_pos + limit
                    break
                if self._closed:
                    if available == 0:
                        return b""
                    end = len(self._buffer)
                    break
                self._not_empty.wait()
            line = self._buffer[self._read_pos : end]
            self._read_pos = end
            self._compact()
            return bytes(line)

    def readuntil(self, delimiter: bytes = b"\n") -> bytes:
        """Read from the buffer until the delimiter is found.

        Arguments:
        ----------
            delimiter (bytes): Byte sequence to read until.

        Returns:
        -------
            bytes: Data including the delimiter.

        Raises:
            EOFError: If the delimiter is not found before stream is closed.
            BlockingIOError: If the delimiter is not found.
        """
        if not delimiter:
            raise ValueError("Delimiter must not be empty")
        with self._not_empty:
            self._check_closed()
            if not self._blocking:
                idx = self._buffer.find(delimiter, self._read_pos)
                if idx == -1:
                    raise BlockingIOError("Delimiter not found in non-blocking mode")
                end = idx + len(delimiter)
                data = self._buffer[self._read_pos : end]
                self._read_pos = end
                self._compact()
                return bytes(data)

            while True:
                idx = self._buffer.find(delimiter, self._read_pos)
                if idx != -1:
                    end = idx + len(delimiter)
                    break
                if self._closed:
                    raise EOFError("Delimiter not found before EOF")
                self._not_empty.wait()
            data = self._buffer[self._read_pos : end]
            self._read_pos = end
            self._compact()
            return bytes(data)

    def peek(self, size: int = -1) -> bytes:
        """Return up to `size` bytes without advancing the read position.

        Arguments:
        ----------
            size (int): Number of bytes to peek.

        Returns:
        -------
            bytes: Peeked data.
        """
        with self._lock:
            self._check_closed()
            available = len(self._buffer) - self._read_pos
            if size < 0 or size > available:
                size = available
            return bytes(self._buffer[self._read_pos : self._read_pos + size])

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Change the current read position.

        Arguments:
        ----------
            offset (int): Byte offset.
            whence (int): io.SEEK_SET, io.SEEK_CUR, or io.SEEK_END.

        Returns:
        -------
            int: New position.
        """
        with self._lock:
            self._check_closed()
            if whence == io.SEEK_SET:
                new_pos = offset
            elif whence == io.SEEK_CUR:
                new_pos = self._read_pos + offset
            elif whence == io.SEEK_END:
                new_pos = len(self._buffer) + offset
            else:
                raise ValueError("Invalid whence")
            if not (0 <= new_pos <= len(self._buffer)):
                raise ValueError("Seek out of bounds")
            self._read_pos = new_pos
            return self._read_pos

    def tell(self) -> int:
        """Return the current read position.

        Returns:
        -------
            int: Current read position in buffer.
        """
        with self._lock:
            self._check_closed()
            return self._read_pos

    def available(self) -> int:
        """Return the number of bytes available for reading.

        Returns:
        -------
            int: Number of bytes available for reading.
        """
        with self._lock:
            self._check_closed()
            return len(self._buffer) - self._read_pos

    def pop_first_match(self, pattern: bytes) -> bytes | None:
        r"""Searches for the first regex match in the bytearray, removes it, and returns the match.

        Arguments:
        ---------
            pattern (bytes): A regex pattern in bytes (e.g. rb'abc\d+').

        Returns:
        -------
            Optional[bytes]: The matched bytes if found and removed, otherwise None.
        """
        with self._lock:
            search_region = self._buffer[self._read_pos :]
            match = re.search(pattern, search_region)
            if match:
                start = self._read_pos + match.start()
                end = self._read_pos + match.end()
                matched_bytes = bytes(self._buffer[start:end])
                del self._buffer[start:end]
                if end <= self._read_pos:
                    self._read_pos -= end - start
                elif start < self._read_pos < end:
                    self._read_pos = start
                return matched_bytes
            return None

    def contains(self, pattern: bytes) -> tuple[int, int]:
        r"""Searches for the first regex match in the bytearray without removing it.

        Arguments:
        ---------
            pattern (bytes): A regex pattern in bytes (e.g. rb'abc\d+').

        Returns:
        -------
            (int, int): (start, end) if buffer contains pattern, otherwise raises ValueError.

        Raises:
        ------
            ValueError: If pattern not found in buffer.
        """
        with self._lock:
            search_region = self._buffer[self._read_pos :]
            match = re.search(pattern, search_region)
            if match:
                start = match.start()
                end = match.end()
                return (start, end)
            else:
                raise ValueError("Pattern not found in buffer")

    def close(self) -> None:
        """Close the buffer and wake up all waiting readers."""
        with self._not_empty:
            self._closed = True
            self._not_empty.notify_all()
            self._buffer.clear()
            self._read_pos = 0
            super().close()

    def readable(self) -> bool:
        """Return True; the buffer supports reading."""
        return True

    def writable(self) -> bool:
        """Return True; the buffer supports writing."""
        return True

    def seekable(self) -> bool:
        """Return True; the buffer supports seeking."""
        return True

    def _compact(self) -> None:
        """Compact the buffer by removing consumed bytes."""
        if self._read_pos > 4096:
            self._buffer = self._buffer[self._read_pos :]
            self._read_pos = 0

    def _check_closed(self) -> None:
        """Raise ValueError if buffer is closed."""
        if self.closed:
            raise ValueError("I/O operation on closed buffer")
