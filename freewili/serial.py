"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import dataclasses
import functools
import pathlib
import re
import sys
from typing import Any, Callable, Optional, Self

import serial
import serial.tools.list_ports
from result import Err, Ok, Result

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

    def __init__(self, info: FreeWiliSerialInfo, stay_open: bool = False) -> None:
        self._info: FreeWiliSerialInfo = info
        self._serial: serial.Serial = serial.Serial(None, timeout=1.0)
        # Initialize to disable menus
        self._initialized: bool = False
        self._stay_open: bool = stay_open

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._info}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self._info.port} @ {self._info.location}"

    @property
    def info(self) -> FreeWiliSerialInfo:
        """Information of the COM Port of the FreeWili."""
        return self._info

    @property
    def stay_open(self) -> bool:
        """Keep serial port open, if True.

        Returns:
            bool
        """
        return self._stay_open

    @stay_open.setter
    def stay_open(self, value: bool) -> None:
        self._stay_open = value

    def close(self) -> None:
        """Close the serial port. Use in conjunction with stay_open."""
        if self._serial.is_open:
            self._serial.close()

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
                    self._serial.port = self._info.port
                    self._serial.open()
                    self._init_serial_if_necessary()
                try:
                    result = func(self, *args, **kwargs)
                    return result
                finally:
                    if not self.stay_open:
                        print("Closing serial port")
                        self._serial.close()
                    result = None

            return wrapper

        return decorator

    def __enter__(self) -> Self:
        if not self._serial.is_open:
            self._serial.port = self._info.port
            self._serial.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._serial.is_open:
            self._serial.close()

    def _init_serial_if_necessary(self) -> None:
        """Initialize the serial port if it hasn't been initialized yet."""
        if not self._initialized:
            self._serial.reset_input_buffer()
            # disable menus (ctrl-b)
            self._serial.write(bytes([2]))
            self._initialized = True

    def _write_serial(self, data: bytes) -> Result[str, str]:
        """Write data to the serial port."""
        try:
            length = self._serial.write(data)
            if length != len(data):
                return Err(f"Only wrote {length} of {len(data)} bytes.")
        except serial.SerialException as e:
            return Err(str(e))
        return Ok(f"Wrote {length} bytes successfully.")

    @needs_open()
    def set_io(self: Self, io: int, high: bool) -> Result[str, str]:
        """Set the state of an IO pin to high or low.

        Parameters:
        ----------
            io : int
                The number of the IO pin to set.
            high : bool
                Whether to set the pin to high or low.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        letter = "h" if high else "l"
        command = f"{letter}\n{io}\n".encode()
        return self._write_serial(command)

    @needs_open()
    def generate_pwm(self, io: int, freq: int, duty: int) -> Result[str, str]:
        """Set PWM on an IO pin.

        Parameters:
        ----------
            io : int
                The number of the IO pin to set.
            freq : int
                The PWM frequency in Hz.
            duty : int
                The duty cycle of the PWM. 0-100.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        command = f"o\n{io} {freq} {duty}\n".encode()
        return self._write_serial(command)

    @needs_open()
    def get_all_io(self) -> Result[int, str]:
        """Get all the IO values.

        Parameters:
        ----------
            None

        Returns:
        -------
            Result[int, str]:
                Ok(int) if the command was sent successfully, Err(str) if not.
        """
        try:
            result = self._write_serial(b"g\n")
            if result.is_err():
                return Err(result.err_value)
            # Wait for data to return, should be 4 bytes (sizeof(int) + sizeof('\n'))
            data = self._serial.read((4 * 2) + 1)
            return Ok(int(data.decode().strip(), 16))
        except serial.SerialException as e:
            return Err(str(e))

    @needs_open()
    def read_write_spi_data(self, data: bytes) -> Result[bytes, str]:
        """Read and Write SPI data.

        Parameters:
        ----------
            data : bytes
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        hex_reg = re.compile(r"[A-Fa-f0-9]{1,2}")
        read_bytes = bytearray()
        for i in range(0, len(data), 8):
            str_hex_data = " ".join(f"{i:02X}" for i in data[i : i + 8])
            self._serial.write(f"s\n{str_hex_data}\n".encode())
            read_data = self._serial.readline().strip()
            for value in hex_reg.findall(read_data.decode()):
                read_bytes += int(value, 16).to_bytes(1, sys.byteorder)
        return Ok(bytes(read_bytes))

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
    def download_file(self, source_file: pathlib.Path, target_name: str) -> Result[str, str]:
        """Download a file to the FreeWili.

        Arguments:
        ----------
        source_file: pathlib.Path
            Path to the file to be downloaded
        target_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            Result[str, str]:
                TODO
        """
        if not isinstance(source_file, pathlib.Path):
            source_file = pathlib.Path(source_file)
        if not source_file.exists():
            return Err(f"{source_file} does not exist.")
        fsize = source_file.stat().st_size
        match self._write_serial(f"x\nf\n{target_name} {fsize}\n".encode()):
            case Ok(_):
                print(f"Downloading {source_file} ({fsize} bytes) as {target_name} on {self}")
                with source_file.open("rb") as f:
                    while byte := f.read(1):
                        if self._serial.write(byte) != 1:
                            return Err(f"Failed to write {byte.decode()} to {self}")
                    print(f"Downloaded {fsize} bytes!")
                return Ok(f"Downloaded {source_file} ({fsize} bytes) as {target_name} to {self}")
            case Err(e):
                return Err(e)


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
