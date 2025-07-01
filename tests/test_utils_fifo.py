"""Tests for utils.fifo module."""

import threading
import time

import pytest

from freewili.util.fifo import SafeIOFIFOBuffer


def test_write_and_read() -> None:
    """Test Read and Write."""
    buf = SafeIOFIFOBuffer(blocking=False)
    buf.write(b"hello world")
    assert buf.read(5) == b"hello"
    assert buf.read() == b" world"
    assert buf.read() == b""


def test_peek_and_seek() -> None:
    """Test Peak and Seek."""
    buf = SafeIOFIFOBuffer()
    buf.write(b"abcdef")
    assert buf.peek(3) == b"abc"
    buf.seek(3)
    assert buf.read(2) == b"de"
    assert buf.tell() == 5
    assert buf.available() == 1


def test_readline() -> None:
    """Test readline."""
    buf = SafeIOFIFOBuffer()
    buf.write(b"line1\nline2\n")
    assert buf.readline() == b"line1\n"
    assert buf.available() == 6
    assert buf.readline() == b"line2\n"
    assert buf.available() == 0


def test_readuntil() -> None:
    """Test readuntil."""
    buf = SafeIOFIFOBuffer()
    buf.write(b"part1|part2|")
    assert buf.available() == 12
    assert buf.readuntil(b"|") == b"part1|"
    assert buf.readuntil(b"|") == b"part2|"
    assert buf.available() == 0


def test_blocking_read() -> None:
    """Test blocking read."""
    buf = SafeIOFIFOBuffer()
    result = []

    def reader() -> None:
        assert buf.available() == 0
        result.append(buf.read(4))
        assert buf.available() == 0

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.2)
    buf.write(b"abcd")
    t.join()
    assert result[0] == b"abcd"


def test_blocking_readline() -> None:
    """Test blocking readline."""
    buf = SafeIOFIFOBuffer()
    result = []

    def reader() -> None:
        result.append(buf.readline())

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.1)
    buf.write(b"hello\n")
    t.join()
    assert result[0] == b"hello\n"


def test_readuntil_eof_raises() -> None:
    """Test raise on readuntil."""
    buf = SafeIOFIFOBuffer()

    def reader() -> None:
        with pytest.raises(EOFError):
            buf.readuntil(b"!")

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.1)
    buf.write(b"no end")
    buf.close()
    t.join()


def test_close_wakes_readers() -> None:
    """Test close."""
    buf = SafeIOFIFOBuffer()
    results = []

    def reader() -> None:
        results.append(buf.read())

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.1)
    buf.close()
    t.join()
    assert results[0] == b""


def test_seek_out_of_bounds() -> None:
    """Test seek out of bounds."""
    buf = SafeIOFIFOBuffer()
    buf.write(b"abc")
    with pytest.raises(ValueError):
        buf.seek(10)


def test_read_after_close_raises() -> None:
    """Test read after close."""
    buf = SafeIOFIFOBuffer()
    buf.write(b"xyz")
    buf.close()
    with pytest.raises(ValueError):
        buf.read(1)


def test_pop_first_match() -> None:
    """Test pop_first_match."""
    buf = SafeIOFIFOBuffer()
    buf.write(rb"35873723\r\n35873723\r\n")
    buf.write(rb"[x\f 0DE8F4AC8194AE32 12 Send File Now 1]\r\n")
    frame = buf.pop_first_match(rb"\[.\\. .*.\d\].*\\n")
    assert frame is not None
    buf.close()


def test_contains() -> None:
    """Test contains."""
    buf = SafeIOFIFOBuffer()
    start_data = rb"35873723\r\n35873723\r\n"
    buf.write(start_data)
    assert buf.available() == len(start_data)
    frame_data = rb"[x\f 0DE8F4AC8194AE32 12 Send File Now 1]\r\n"
    buf.write(frame_data)
    start, end = buf.contains(rb"\[.\\. .*.\d\].*\\n")
    assert start == len(start_data)
    assert end == len(start_data) + len(frame_data)
    with pytest.raises(ValueError):
        buf.contains(rb"thisshouldn'tmatchanything")
    buf.close()


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
