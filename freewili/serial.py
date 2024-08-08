"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import dataclasses
import enum
import functools
import pathlib
import re
import sys
import time
from typing import Any, Callable, List, Optional, Self, Tuple

import serial
import serial.tools.list_ports
from result import Err, Ok, Result


class FreeWiliProcessorType(enum.Enum):
    """Processor type of the FreeWili."""

    Unknown = enum.auto()
    Main = enum.auto()
    Display = enum.auto()

    def __str__(self) -> str:
        return self.name


@dataclasses.dataclass
class FreeWiliAppInfo:
    """Information of the FreeWili application."""

    processor_type: FreeWiliProcessorType
    version: int

    def __str__(self) -> str:
        return f"{self.processor_type} v{self.version}"


# Disable menu Ctrl+b
CMD_DISABLE_MENU = b"\x02"
# Enable menu Ctrl+c
CMD_ENABLE_MENU = b"\x03"

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
    # Application information of the FreeWili firmware
    app_info: FreeWiliAppInfo
    # USB Location of the FreeWili, Optional
    location: Optional[str] = None
    # Vendor ID of the FreeWili (0x2E8A), Optional
    vid: Optional[int] = None
    # Product ID of the FreeWili (0x000A), Optional
    pid: Optional[int] = None


class FreeWiliSerial:
    """Class representing a serial connection to a FreeWili."""

    # The default number of bytes to write/read at a time
    DEFAULT_SEGMENT_SIZE: int = 8

    def __init__(self, info: FreeWiliSerialInfo, stay_open: bool = False) -> None:
        self._info: FreeWiliSerialInfo = info
        self._serial: serial.Serial = serial.Serial(None, timeout=1.0)
        # Initialize to disable menus
        self._stay_open: bool = stay_open

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._info}>"

    def __str__(self) -> str:
        return f"{self._info.app_info} {self._info.port} @ {self._info.location}"

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
    def needs_open(enable_menu: bool = False) -> Callable:
        """Decorator to open and close serial port.

        Expects the class to have an attribute '_serial' that is a serial.Serial object
        and a method '_init_if_necessary' that initializes the serial port.

        Parameters:
        ----------
            enable_menu: bool
                Enable menu if True. Defaults to False.

        Example:
        -------
        >>> class MyClass:
        >>>     @needs_open(False)
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
                    self._set_menu_enabled(enable_menu)
                try:
                    result = func(self, *args, **kwargs)
                    return result
                finally:
                    if not self.stay_open:
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

    def _set_menu_enabled(self, enabled: bool) -> None:
        """Enable or disable menus.

        Parameters:
        ----------
            enabled: bool
                True to enable menus, False to disable.

        Returns:
        -------
            None
        """
        self._serial.reset_output_buffer()
        self._serial.reset_input_buffer()
        cmd = CMD_ENABLE_MENU if enabled else CMD_DISABLE_MENU
        cmd += "\r\n".encode("ascii")
        self._write_serial(cmd)
        self._serial.flush()

    def _write_serial(self, data: bytes) -> Result[str, str]:
        """Write data to the serial port."""
        # print(f"DEBUG: {repr(data)}")
        try:
            length = self._serial.write(data)
            if length != len(data):
                return Err(f"Only wrote {length} of {len(data)} bytes.")
            self._serial.flush()
        except serial.SerialException as e:
            return Err(str(e))
        return Ok(f"Wrote {length} bytes successfully.")

    @needs_open(False)
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
        command = f"{letter}\n{io}\n".encode("ascii")
        return self._write_serial(command)

    @needs_open(False)
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
        command = f"o\n{io} {freq} {duty}\n".encode("ascii")
        return self._write_serial(command)

    @needs_open(False)
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
                return Err(str(result.err()))
            # Wait for data to return, should be 4 bytes (sizeof(int) + sizeof('\n'))
            data = self._serial.read((4 * 2) + 1)
            return Ok(int(data.decode().strip(), 16))
        except serial.SerialException as e:
            return Err(str(e))

    def _write_and_read_bytes_cmd(self, command: str, data: bytes, data_segment_size: int) -> Result[bytes, str]:
        """Write and read bytes from a command.

        Parameters:
        ----------
            command : str
                The command to send. Should end with a newline.
            data : bytes
                The data to write.
            data_segment_size : int
                The number of bytes to read/write at a time.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        hex_reg = re.compile(r"[A-Fa-f0-9]{1,2}")
        read_bytes = bytearray()
        for i in range(0, len(data), data_segment_size):
            str_hex_data = " ".join(f"{i:02X}" for i in data[i : i + data_segment_size])
            self._serial.write(f"{command}{str_hex_data}\n".encode("ascii"))
            read_data = self._serial.readline().strip()
            for value in hex_reg.findall(read_data.decode()):
                read_bytes += int(value, 16).to_bytes(1, sys.byteorder)
        return Ok(bytes(read_bytes))

    @needs_open(False)
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
        return self._write_and_read_bytes_cmd("s\n", data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def write_i2c(self, address: int, register: int, data: bytes) -> Result[bytes, str]:
        """Write I2C data.

        Parameters:
        ----------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data : bytes
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        complete_data = address.to_bytes(1, sys.byteorder) + register.to_bytes(1, sys.byteorder) + data
        return self._write_and_read_bytes_cmd("i\n", complete_data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def read_i2c(self, address: int, register: int, data_size: int) -> Result[bytes, str]:
        """Read I2C data.

        Parameters:
        ----------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data_size : int
                The number of bytes to read.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        complete_data = (
            address.to_bytes(1, sys.byteorder)
            + register.to_bytes(1, sys.byteorder)
            + data_size.to_bytes(1, sys.byteorder)
        )
        return self._write_and_read_bytes_cmd("i\n", complete_data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def poll_i2c(self) -> Result[Tuple[int, ...], str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
        file_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            Result[str, str]:
                Ok(List[int]) if the command was sent successfully, Err(str) if not.
        """

        def _process_line(line: str) -> List[int]:
            """Process a line of hex values seperated by a space and returns a list of int."""
            hex_reg = re.compile(r"[A-Fa-f0-9]{1,2}")
            values = []
            for value in hex_reg.findall(line):
                values.append(int(value, 16))
            return values

        match self._write_serial("p\n".encode("ascii")):
            case Ok(_):
                found_addresses = []
                first_line_processed: bool = False
                while line := self._serial.readline():
                    if not first_line_processed:
                        first_line_processed = True
                        continue
                    addresses = _process_line(line.decode().lstrip().rstrip())
                    addr_un = addresses[0] # Address upper nibble
                    found_addresses.extend(
                            [addr_un + addr_ln for addr_ln, found in enumerate(addresses[1:]) if found != 0]
                        )
                return Ok(tuple(found_addresses))
            case Err(e):
                return Err(e)

    @needs_open(False)
    def write_radio(self, data: bytes) -> Result[bytes, str]:
        """Write radio data.

        Parameters:
        ----------
            data : bytes
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        return self._write_and_read_bytes_cmd("t\n", data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def read_radio(self, data: bytes) -> Result[bytes, str]:
        """Read radio data.

        Parameters:
        ----------
            data : bytes
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        return self._write_and_read_bytes_cmd("k\n", data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def write_uart(self, data: bytes) -> Result[bytes, str]:
        """Write uart data.

        Parameters:
        ----------
            data : bytes
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        return self._write_and_read_bytes_cmd("u\n", data, self.DEFAULT_SEGMENT_SIZE)

    @needs_open(False)
    def enable_stream(self, enable: bool) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open(False)
    def run_script(self, file_name: str) -> Result[str, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
        file_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        print(f"Running script '{file_name}' on {self}...")
        match self._write_serial(f"w\n{file_name}\n".encode("ascii")):
            case Ok(_):
                read_bytes = []
                while byte := self._serial.read(1):
                    read_bytes.append(byte.decode())
                return Ok("".join(read_bytes))
            case Err(e):
                return Err(e)

    @needs_open(False)
    def load_fpga_from_file(self, file_name: str) -> Result[str, str]:
        """Load an FGPA from a file on the FreeWili.

        Arguments:
        ----------
        file_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self._write_serial(f"m\n{file_name}\n".encode("ascii")):
            case Ok(_):
                read_bytes = []
                while byte := self._serial.read(1):
                    read_bytes.append(byte.decode())
                return Ok("".join(read_bytes))
            case Err(e):
                return Err(e)

    @needs_open(False)
    def send_file(self, source_file: pathlib.Path, target_name: str) -> Result[str, str]:
        """Send a file to the FreeWili.

        Arguments:
        ----------
        source_file: pathlib.Path
            Path to the file to be sent.
        target_name: str
            Name of the file in the FreeWili.

        Returns:
        -------
            Result[str, str]:
                Returns Ok(str) if the command was sent successfully, Err(str) if not.
        """
        if not isinstance(source_file, pathlib.Path):
            source_file = pathlib.Path(source_file)
        if not source_file.exists():
            return Err(f"{source_file} does not exist.")
        fsize = source_file.stat().st_size
        # generate the checksum
        checksum = 0
        with source_file.open("rb") as f:
            while byte := f.read(1):
                checksum += int.from_bytes(byte)
                if checksum & 0x8000:
                    checksum ^= 2054
                checksum &= 0xFFFFFF
        # send the download command
        self._serial.read_all()
        match self._write_serial(f"x\nf\n{target_name} {fsize} {checksum}\n".encode("ascii")):
            case Ok(_):
                time.sleep(0.25)  # self._wait_for_serial_data(1.0, 0.1)
                # print(self._serial.read_all())
                print(f"Downloading {source_file} ({fsize} bytes) as {target_name} on {self}")
                with source_file.open("rb") as f:
                    while byte := f.read(1):
                        # print(byte)
                        if self._serial.write(byte) != len(byte):
                            return Err(f"Failed to write {byte.decode()} to {self}")
                        # print(self._serial.read_all())
                        # time.sleep(0.002)
                return Ok(f"Downloaded {source_file} ({fsize} bytes) as {target_name} to {self}")
            case Err(e):
                return Err(e)

    @needs_open(False)
    def get_file(self, source_file: str) -> Result[bytearray, str]:
        """Get a file from the FreeWili.

        Arguments:
        ----------
        source_file: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        Returns:
        -------
            Result[bytearray, str]:
                Returns an array of bytes if the command was sent successfully, Err(str) if not.
        """
        # Clear anything in the buffer
        _ = self._serial.read_all()
        match self._write_serial(f"x\nu\n{source_file}\n".encode("ascii")):
            case Ok(_):
                time.sleep(1)
                data = self._serial.read_all()
                return Ok(data)
            case Err(e):
                return Err(e)

    def reset_to_uf2_bootloader(self) -> Result[None, str]:
        """Reset the FreeWili to the uf2 bootloader.

        Returns:
        -------
            Result[None, str]:
                Returns Ok(None) if the command was sent successfully, Err(str) if not.
        """
        original_baudrate = self._serial.baudrate
        try:
            if self._serial.is_open:
                self._serial.close()
            else:
                self._serial.port = self._info.port
            self._serial.baudrate = 1200
            self._serial.open()
            time.sleep(0.1)
            self._serial.close()
            return Ok(None)
        except serial.serialutil.SerialException as ex:
            return Err(str(ex))
        finally:
            self._serial.baudrate = original_baudrate

    def _wait_for_serial_data(self, timeout_sec: float, delay_sec: float = 0.1) -> None:
        """Wait for data to be available on the serial port.

        Parameters:
        ----------
            timeout_sec: float
                The maximum amount of time to wait for data.
            delay_sec: float
                The amount of time to wait after checks for data.

        Returns:
        -------
            None

        Raises:
        -------
            TimeoutError
                If the timeout is reached before data is available.
        """
        start = time.time()
        while self._serial.in_waiting == 0:
            time.sleep(0.001)
            if time.time() - start > timeout_sec:
                raise TimeoutError(f"Timed out waiting for data on {self}")
        time.sleep(delay_sec)

    @needs_open(True)
    def get_app_info(self) -> Result[FreeWiliAppInfo, str]:
        """Detect the processor type of the FreeWili.

        Returns:
        -------
            Result[FreeWiliProcessorType, str]:
                Returns Ok(FreeWiliProcessorType) if the command was sent successfully, Err(str) if not.
        """
        self._wait_for_serial_data(1.0)
        data = self._serial.read_all()
        # proc_type_regex = re.compile(r"(Main|Display) Processor")
        # match = proc_type_regex.search(data.decode())
        # if match is None:
        #     return Ok(FreeWiliProcessorType.Unknown)
        # elif "Main Processor" in match.group():
        #     return Ok(FreeWiliProcessorType.Main)
        # elif "Display Processor" in match.group():
        #     return Ok(FreeWiliProcessorType.Display)
        # else:
        #     return Err("Unknown processor type detected!")
        line = ""
        for line in data.decode().splitlines():
            if "Processor" in line:
                break
        proc_type_regex = re.compile(r"(?:Main|Display)|(?:App version)|(?:\d+)")
        results = proc_type_regex.findall(line)
        if len(results) != 3:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))
        processor = results[0]
        version = results[2]
        if "Main" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, int(version)))
        elif "Display" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Display, int(version)))
        else:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))


def find_all(processor_type: Optional[FreeWiliProcessorType] = None) -> tuple[FreeWiliSerial, ...]:
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
                        FreeWiliAppInfo(
                            FreeWiliProcessorType.Unknown,
                            0,
                        ),
                        port.location,
                        port.vid,
                        port.pid,
                    )
                ),
            )
            try:
                # Update the processor type
                app_info = devices[-1].get_app_info().unwrap()
                devices[-1]._info = FreeWiliSerialInfo(
                    port.device,
                    port.serial_number,
                    app_info,
                    port.location,
                    port.vid,
                    port.pid,
                )
                # Filter by processor type
                if processor_type is not None and app_info.processor_type != processor_type:
                    devices.pop()
            except Exception as ex:
                print(ex)
                pass
    return tuple(devices)
