"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import dataclasses
import enum
import functools
import pathlib
import platform
from queue import Empty
import re
import sys
import time
from typing import Any, Callable, Optional

from freewili.framing import ResponseFrame
from freewili.serialreader import SerialReader

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import serial
import serial.tools.list_ports
from result import Err, Ok, Result

from freewili.types import FreeWiliProcessorType


class IOMenuCommand(enum.Enum):
    """Free-Wili IO menu representation."""

    High = enum.auto()
    Low = enum.auto()
    Toggle = enum.auto()
    Pwm = enum.auto()
    Stream = enum.auto()
    Get = enum.auto()

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Convert a string value to an IOMenuCommand.

        Arguments:
        ----------
            value: str
                string value to convert to an enum. Case Insensitive.

        Returns:
        --------
            str:
                FreeWili menu command character.

        Raises:
            ValueError:
                When invalid enum isn't matched against provided string value.
        """
        match value.lower():
            case "high":
                return cls(cls.High)
            case "low":
                return cls(cls.Low)
            case "toggle":
                return cls(cls.Toggle)
            case "pwm":
                return cls(cls.Pwm)
        raise ValueError(f"'{value}' is not a valid IOMenuCommand")

    @property
    def menu_character(self) -> str:
        """Convert IOMenuCommand to a FreeWili menu command character.

        Arguments:
        ----------
            None

        Returns:
        --------
            str:
                FreeWili menu command character.

        Raises:
            ValueError:
                When invalid enum isn't found.
        """
        match self:
            case self.High:
                return "s"
            case self.Low:
                return "l"
            case self.Toggle:
                return "t"
            case self.Pwm:
                return "p"
            case self.Stream:
                return "o"
            case self.Get:
                return "u"
        raise ValueError(f"{self.name} ({self.value}) is not a supported menu command")


@dataclasses.dataclass
class FreeWiliAppInfo:
    """Information of the FreeWili application."""

    processor_type: FreeWiliProcessorType
    version: int

    def __str__(self) -> str:
        desc = f"{self.processor_type.name}"
        if self.processor_type in (FreeWiliProcessorType.Main, FreeWiliProcessorType.Display):
            desc += f" v{self.version}"
        return desc


# Disable menu Ctrl+b
CMD_DISABLE_MENU = b"\x02"
# Enable menu Ctrl+c
CMD_ENABLE_MENU = b"\x03"


class FreeWiliSerial:
    """Class representing a serial connection to a FreeWili."""

    # The default number of bytes to write/read at a time
    DEFAULT_SEGMENT_SIZE: int = 8

    def __init__(self, port: str, stay_open: bool = False) -> None:
        self.reader = SerialReader(port)
        self.reader.start()
        # self.port = port
        # self._serial: serial.Serial = serial.Serial(None, timeout=1.0, exclusive=True)
        # # Initialize to disable menus
        # self._stay_open: bool = stay_open

    def __repr__(self) -> str:
        return f"<{str(self)}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.reader.port}"

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

    def close(self, restore_menu: bool = True) -> None:
        """Close the serial port. Use in conjunction with stay_open."""
        if restore_menu:
            self.reader.send(CMD_ENABLE_MENU)
        self.reader.close()

    @staticmethod
    def needs_open(enable_menu: bool = False, restore_menu: bool = True) -> Callable:
        """Decorator to open and close serial port.

        Expects the class to have an attribute '_serial' that is a serial.Serial object
        and a method '_init_if_necessary' that initializes the serial port.

        Parameters:
        ----------
            enable_menu: bool
                Enable menu if True. Defaults to False.

            restore_menu: bool
                Restore the menu after we are done. Defaults to True.

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
                self._set_menu_enabled(enable_menu)
                try:
                    result = func(self, *args, **kwargs)
                    # self._set_menu_enabled(True)
                    return result
                finally:
                    if not self.stay_open:
                        self.close(restore_menu)
                    result = None

            return wrapper

        return decorator

    # def __enter__(self) -> Self:
    #     if not self._serial.is_open:
    #         self._serial.port = self.port
    #         self._serial.open()
    #     return self

    # def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
    #     if self._serial.is_open:
    #         self._serial.close()

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
        # self.reader.clear()
        self.reader.send(CMD_ENABLE_MENU if enabled else CMD_DISABLE_MENU)

        # Wait for menu to be enabled and receive some data
        timeout_sec: float = 2.0
        if enabled:
            start = time.time()
            while time.time() - start <= timeout_sec and self.reader.data_queue.empty():
                time.sleep(0.001)
            time.sleep(0.1)

    @needs_open(False)
    def set_io(
        self: Self, io: int, menu_cmd: IOMenuCommand, pwm_freq: None | int = None, pwm_duty: None | int = None
    ) -> Result[ResponseFrame, str]:
        """Set the state of an IO pin to high or low.

        Parameters:
        ----------
            io : int
                The number of the IO pin to set.
            menu_cmd : IOMenuCommand
                Whether to set the pin to high, low, toggle, or pwm.
            pwm_freq: None | int
                PWM frequency in Hertz
            pwm_duty: None | int
                PWM Duty cycle (0-100)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # s) High [25]
        # l) Low []
        # t) Toggle
        # p) PWM IO
        # u) Get All IOs (hex)
        match menu_cmd:
            case IOMenuCommand.High:
                cmd = f"o\n{menu_cmd.menu_character}\n{io}\n"
            case IOMenuCommand.Low:
                cmd = f"o\n{menu_cmd.menu_character}\n{io}\n"
            case IOMenuCommand.Toggle:
                cmd = f"o\n{menu_cmd.menu_character}\n{io}\n"
            case IOMenuCommand.Pwm:
                if pwm_freq == -1 or pwm_duty == -1:
                    return Err("pwm_freq and pwm_duty args need to be specified")
                cmd = f"o\n{menu_cmd.menu_character}\n{io} {pwm_freq} {pwm_duty}\n"
            case IOMenuCommand.Toggle:
                cmd = f"o\n{menu_cmd.menu_character}\n{io}\n"
            case _:
                return Err(f"{menu_cmd.name} is not supported.")

        self.reader.send(cmd)
        resp = self._wait_for_response_frame()
        return resp

    @needs_open(False)
    def set_board_leds(self: Self, io: int, red: int, green: int, blue: int) -> Result[ResponseFrame, str]:
        """Set the GUI RGB LEDs.

        Parameters:
        ----------
            io : int
                The number of the IO pin to set.
            red : int
                Red Color 0-255
            green : int
                Green Color 0-255
            blue : int
                Blue Color 0-255

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # s) Set Board LED [25 100 100 100]
        cmd = f"k\ns\n{io} {red} {green} {blue}"

        self.reader.send(cmd)
        resp = self._wait_for_response_frame()
        return resp

    @needs_open(False)
    def get_io(self) -> Result[tuple[int], str]:
        """Get all the IO values.

        Parameters:
        ----------
            None

        Returns:
        -------
            Result[tuple[int], str]:
                Ok(tuple[int]) if the command was sent successfully, Err(str) if not.
        """
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        cmd = f"o\n{IOMenuCommand.Get.menu_character}\n"
        match self._write_serial(cmd.encode("ascii"), 0.1):
            case Ok(_):
                resp = self._wait_for_response_frame()
                if resp.is_err():
                    return resp
                resp = resp.unwrap()
                if not resp.is_ok():
                    return Err(f"Failed to get IO values: {resp.response}")
                all_io_values = int(resp.response, 16)
                values = []
                for i in range(32):
                    io_value = (all_io_values >> i) & 0x1
                    values.append(io_value)
                return Ok(values)
            case Err(e):
                return Err(e)

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
            # if not read_data:
            #     read_data = self._serial.readline().strip()
            for value in hex_reg.findall(read_data.decode()):
                read_bytes += int(value, 16).to_bytes(1, sys.byteorder)
        return Ok(bytes(read_bytes))

    def _wait_for_response_frame(self, timeout_sec: float = 10.0) -> Result[ResponseFrame, str]:
        """Wait for a response frame after sending a command.

        Parameters:
        ----------
            timeout_sec : float
                Time to wait in seconds before we error out.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the response frame was found, Err(str) if not.
        """
        try:
            resp = self.reader.rf_queue.get(True, timeout_sec)
            self.reader.rf_queue.task_done()
            return resp
        except Empty:
            return Err(f"Failed to read response frame in {timeout_sec} seconds")

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

    @needs_open(True)
    def write_i2c(self, address: int, register: int, data: bytes) -> Result[ResponseFrame, str]:
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
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        data_bytes = " ".join(f"{i:02X}" for i in data)
        match self._write_serial(f"i\nw\n{address:02X} {register:02X} {data_bytes}\n".encode("ascii"), 0.0):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(True)
    def read_i2c(self, address: int, register: int, data_size: int) -> Result[ResponseFrame, str]:
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
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial(f"i\nr\n{address:02X} {register:02X} {data_size}\n".encode("ascii"), 0.0):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(True)
    def poll_i2c(self) -> Result[ResponseFrame, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial("i\np\n".encode("ascii"), 0.1):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(False)
    def show_gui_image(self, fwi_path: str) -> Result[ResponseFrame, str]:
        """Show a fwi image on the display.

        Arguments:
        ----------
            fwi_path: str
                path to the fwi image

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # l) Show FWI Image [pip_boy.fwi]
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial(f"k\nl\n{fwi_path}\n".encode("ascii"), 0.1):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(False)
    def reset_display(self) -> Result[ResponseFrame, str]:
        """Reset the display back to the main menu.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # t) Reset Display
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial("k\nt\n".encode("ascii"), 0.1):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(False)
    def show_text_display(self, text: str) -> Result[ResponseFrame, str]:
        """Show text on the display.

        Arguments:
        ----------
            text: str
                text to display on screen.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # p) Show Text Display
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial(f"k\np\n{text}\n".encode("ascii"), 0.1):
            case Ok(_):
                return self._wait_for_response_frame()
            case Err(e):
                return Err(e)

    @needs_open(False)
    def read_all_buttons(self) -> Result[ResponseFrame, str]:
        """Read all the buttons.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # u) Read All Buttons
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial("k\nu\n".encode("ascii"), 0.1):
            case Ok(_):
                return self._wait_for_response_frame()
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
                checksum += int.from_bytes(byte, "little")
                if checksum & 0x8000:
                    checksum ^= 2054
                checksum &= 0xFFFFFF
        # send the download command
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        match self._write_serial(f"x\nf\n{target_name} {fsize} {checksum}\n".encode("ascii"), 0.1):
            case Ok(_):
                # print(self._serial.read_all())
                print(f"Downloading {source_file} ({fsize} bytes) as {target_name} on {self}")
                with source_file.open("rb") as f:
                    while byte := f.read(1):
                        # print(byte)
                        if self._serial.write(byte) != len(byte):
                            return Err(f"Failed to write {byte.decode()} to {self}")
                        # print(self._serial.read_all())
                        # time.sleep(0.002)
                time.sleep(1)
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
                self._serial.port = self.port
            self._serial.baudrate = 1200
            try:
                self._serial.open()
            except serial.serialutil.SerialException as ex:
                if platform.system() == "Windows":
                    # SerialException("Cannot configure port, something went wrong.
                    # Original message:
                    # PermissionError(13, 'A device attached to the system is not functioning.', None, 31)")
                    return Ok(None)
                raise ex from ex
            self._serial.close()
            return Ok(None)
        except Exception as ex:
            return Err(f"Failed to reset to UF2 bootloader {str(ex)}")
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
        self._wait_for_serial_data(3.0)
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
            if "Processor" in line or "MainCPU" in line or "DisplayCPU" in line:
                break
        proc_type_regex = re.compile(r"(?:Main|Display)|(?:App version)|(?:\d+)")
        results = proc_type_regex.findall(line)
        if len(results) == 2:
            # New firmware >= 48
            processor = results[0]
            version = results[1]
        elif len(results) == 3:
            # Legacy firmware
            processor = results[0]
            version = results[2]
        else:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))
        if "Main" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, int(version)))
        elif "Display" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Display, int(version)))
        else:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))
