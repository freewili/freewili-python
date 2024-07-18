"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import dataclasses
import functools
import pathlib
import time
from typing import Any, Callable, Optional, Self

import serial
import serial.tools.list_ports

# Raspberry Pi Vendor ID
RPI_VID = 0x2E8A
# Raspberry Pi Pico SDK CDC UART Product ID
RPI_CDC_PID = 0x000A


@dataclasses.dataclass(frozen=True)
class FreeWiliSerialInfo:
    """Information of the COM Port of the FreeWili."""

    # COM port of the FreeWili, e.g. 'COM1' or '/dev/ttyACM0'
    port: str
    # Serial number of the FreeWili
    serial: str
    # USB Location of the FreeWili, Optional
    location: Optional[str] = None
    # Vendor ID of the FreeWili (0x2E8A), Optional
    vid: Optional[int] = None
    # Product ID of the FreeWili (0x000A), Optional
    pid: Optional[int] = None


class FreeWiliSerial:
    """Class representing a serial connection to a FreeWili."""

    def __init__(self, info: FreeWiliSerialInfo) -> None:
        self._info: FreeWiliSerialInfo = info
        self._serial: serial.Serial = serial.Serial(self._info.port)
        # Initialize to disable menus
        self._initialized: bool = False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._info}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self._info.port} @ {self._info.location}"

    @property
    def info(self) -> FreeWiliSerialInfo:
        """Information of the COM Port of the FreeWili."""
        return self._info

    @staticmethod
    def needs_open() -> Callable:
        """Decorator to open and close serial port.

        Expects the class to have an attribute '_serial' that is a serial.Serial object
        and a method '_init_if_necessary' that initializes the serial port.

        Parameters:
        ----------
            None

        Example:
        -------
        >>> class MyClass:
        >>>     @needs_open
        >>>     def my_method(self):
        >>>         pass
        >>>

        """

        def decorator(func: Callable) -> Callable:
            """Decorator function that wraps the given function."""

            @functools.wraps(func)
            def wrapper(self: Self, *args: Optional[Any], **kwargs: Optional[Any]) -> Any | None:
                if not self._serial.is_open:
                    self._serial.open()
                    self._init_serial_if_necessary()
                try:
                    result = func(self, *args, **kwargs)
                finally:
                    self._serial.close()
                    result = None
                return result

            return wrapper

        return decorator

    def _init_serial_if_necessary(self) -> None:
        """Initialize the serial port if it hasn't been initialized yet."""
        if not self._initialized:
            self._serial.reset_input_buffer()
            # disable menus (ctrl-b)
            self._serial.write(bytes([2]))
            self._initialized = True

    @needs_open()
    def set_io(self, io: int, value: int) -> None:
        """TODO: Docstring."""
        if value > 0:
            stosend = "h\n" + str(io) + "\n"
        else:
            stosend = "l\n" + str(io) + "\n"
        self._serial.write(bytes(stosend, "ascii"))
        # sreturn = self._serial.read(2)

    @needs_open()
    def gen_pwm(self, io_number: int, freq: float, duty: float) -> None:
        """TODO: Docstring."""
        stosend = "o\n" + str(io_number) + " " + str(freq) + " " + str(duty) + "\n"
        self._serial.write(bytes(stosend, "ascii"))

    @needs_open()
    def get_all_io(self) -> bytes:
        """TODO: Docstring."""
        self._serial.reset_input_buffer()
        stosend = "g\n"
        self._serial.write(bytes(stosend, "ascii"))
        time.sleep(0.2)
        return self._serial.readline()

    @needs_open()
    def read_write_spi_data(self, data: bytes) -> bytes:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def write_i2c(self, address: int, register: int, data: bytes) -> int:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def write_radio(self, radio: int, data: bytes) -> int:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def read_radio(self, radio: int, length: int) -> bytes:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def write_uart(self, data: bytes) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def enable_stream(self, enable: bool) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def run_script(self, script_path: str) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def load_fpga_from_file(self, bit_file_path: pathlib.Path) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
    def download_file(self, source_file: pathlib.Path, target_name: str) -> None:
        """Download a file to the FreeWili.

        Arguments:
        ----------
        source_file: pathlib.Path
            Path to the file to be downloaded
        target_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            None
        """
        if not isinstance(source_file, pathlib.Path):
            source_file = pathlib.Path(source_file)
        if not source_file.exists():
            raise FileNotFoundError(source_file)
        fsize = source_file.stat().st_size
        print(f"Downloading {source_file} ({fsize} bytes) as {target_name} on {self}")
        self._serial.write(f"x\nf\n{target_name} {fsize}\n".encode())
        with source_file.open("rb") as f:
            while byte := f.read(1):
                if self._serial.write(byte) != 1:
                    raise RuntimeError(f"Failed to write {byte.decode()} to {self}")
        print(f"Downloaded {fsize} bytes!")


def find_all() -> tuple[FreeWiliSerial, ...]:
    """Finds all FreeWili connected to the computer.

    Returns:
    -------
        tuple[FreeWiliComPort]
    """
    # All port attributes:
    #
    # description Pico - Board CDC
    # device /dev/ttyACM0
    # device_path /sys/devices/pci0000:00/0000:00:01.2/0000:02:00.0/usb1/1-2/1-2.1/1-2.1:1.0
    # hwid USB VID:PID=2E8A:000A SER=E463A8574B151439 LOCATION=1-2.1:1.0
    # interface Board CDC
    # location 1-2.1:1.0
    # manufacturer Raspberry Pi
    # name ttyACM0
    # pid 10
    # product Pico
    # read_line <bound method SysFS.read_line of <serial.tools.list_ports_linux.SysFS object at 0x7d2135365e80>>
    # serial_number E463A8574B151439
    # subsystem usb
    # usb_description <bound method ListPortInfo.usb_description of <serial.tools.list_ports_linux.SysFS object at 0x7d2135365e80>> # noqa
    # usb_device_path /sys/devices/pci0000:00/0000:00:01.2/0000:02:00.0/usb1/1-2/1-2.1
    # usb_info <bound method ListPortInfo.usb_info of <serial.tools.list_ports_linux.SysFS object at 0x7d2135365e80>>
    # usb_interface_path /sys/devices/pci0000:00/0000:00:01.2/0000:02:00.0/usb1/1-2/1-2.1/1-2.1:1.0
    # vid 11914
    devices: list[FreeWiliSerial] = []
    for port in serial.tools.list_ports.comports():
        if port.vid == RPI_VID and port.pid == RPI_CDC_PID:
            devices.append(
                FreeWiliSerial(
                    FreeWiliSerialInfo(
                        port.device,
                        port.serial_number,
                        port.location,
                        port.vid,
                        port.pid,
                    )
                ),
            )
    return tuple(devices)
