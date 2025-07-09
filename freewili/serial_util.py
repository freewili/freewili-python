"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import dataclasses
import functools
import pathlib
import platform
import queue
import re
import sys
import time
import zlib
from queue import Empty
from typing import Any, Callable, Optional

from freewili.framing import ResponseFrame
from freewili.serialport import SerialPort

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import serial
import serial.tools.list_ports
from result import Err, Ok, Result

from freewili.types import ButtonColor, FreeWiliProcessorType, IOMenuCommand


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

    def __init__(self, port: str, stay_open: bool = False, name: str = "") -> None:
        self.serial_port = SerialPort(port, 1000000, name)
        self.last_menu_option: None | bool = None
        # self.port = port
        # self._serial: serial.Serial = serial.Serial(None, timeout=1.0, exclusive=True)
        # # Initialize to disable menus
        # self._stay_open: bool = stay_open

    def __repr__(self) -> str:
        return f"<{str(self)}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.serial_port.port}"

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
            Result[None, str]:
                Ok(None) if successful, Err(str) otherwise.

        """
        return self.serial_port.open(block, timeout_sec)

    def close(self, restore_menu: bool = True, block: bool = True, timeout_sec: float = 6.0) -> None:
        """Close the serial port.

        See also: is_open()

        Parameters:
        ----------
            restore_menu: bool:
                Re-enable the menu before close if True.
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
        if self.serial_port.is_open() and restore_menu:
            self.serial_port.send(CMD_ENABLE_MENU)
        self.serial_port.close()

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
        return self.serial_port.is_open()

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
        >>>     @needs_open()
        >>>     def my_method(self):
        >>>         pass
        >>>

        """

        def decorator(func: Callable) -> Callable:
            """Decorator function that wraps the given function."""

            @functools.wraps(func)
            def wrapper(self: Self, *args: Optional[Any], **kwargs: Optional[Any]) -> Any | None:
                was_open = self.is_open()
                self.open().expect("Failed to open")
                self._set_menu_enabled(enable_menu)
                # if self.last_menu_option != enable_menu:
                #     self._set_menu_enabled(enable_menu)
                #     self.last_menu_option = enable_menu
                try:
                    result = func(self, *args, **kwargs)
                    # self._set_menu_enabled(True)
                    return result
                finally:
                    if not self.stay_open and not was_open:
                        self.close(restore_menu)
                    result = None

            return wrapper

        return decorator

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

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
        self.serial_port.send(CMD_ENABLE_MENU if enabled else CMD_DISABLE_MENU)
        # if enabled:
        #     self.serial_port.send("", True, "\r\n")

        # Wait for menu to be enabled and receive some data
        timeout_sec: float = 2.0
        if enabled:
            start = time.time()
            current = time.time()
            while current - start < timeout_sec and self.serial_port.data_queue.empty():
                current = time.time()
                time.sleep(0.001)
            if current - start >= timeout_sec:
                raise TimeoutError(f"Failed to enable menus in {timeout_sec} seconds")
            time.sleep(0.05)

    def _wait_for_response_frame(self, timeout_sec: float = 6.0) -> Result[ResponseFrame, str]:
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
        # return ResponseFrame.from_raw("[k\\s 0DE8F442FBC41063 14 Ok 1]")
        start = time.time()
        while time.time() - start <= timeout_sec or timeout_sec == 0:
            try:
                # We do get_nowait here because we don't want to block
                return self.serial_port.rf_queue.get_nowait()
            except Empty:
                pass
            if timeout_sec == 0:
                break
        return Err(f"Failed to read response frame in {timeout_sec} seconds")

    def _wait_for_event_response_frame(self, timeout_sec: float = 6.0) -> Result[ResponseFrame, str]:
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
        # return ResponseFrame.from_raw("[*filedl 0DE8F442FBC41063 14 Ok 1]")
        start = time.time()
        while time.time() - start <= timeout_sec or timeout_sec == 0:
            try:
                # We do get_nowait here because we don't want to block
                return self.serial_port.rf_event_queue.get_nowait()
            except Empty:
                pass
            if timeout_sec == 0:
                break
        return Err(f"Failed to read event response frame in {timeout_sec} seconds")

    def _empty_data_queue(self) -> None:
        """Empty the data queue.

        This is used to clear the data queue before sending a command
        to ensure that we don't process stale data.
        """
        while not self.serial_port.data_queue.empty():
            self.serial_port.data_queue.get()

    def _empty_event_response_frame_queue(self) -> None:
        """Empty the response frameevent queue.

        This is used to clear the event queue before sending a command
        to ensure that we don't process stale data.
        """
        while not self.serial_port.rf_event_queue.empty():
            self.serial_port.rf_event_queue.get()

    def _empty_response_frame_queue(self) -> None:
        """Empty the response frameevent queue.

        This is used to clear the event queue before sending a command
        to ensure that we don't process stale data.
        """
        while not self.serial_port.rf_event_queue.empty():
            self.serial_port.rf_event_queue.get()

    def _empty_all(self) -> None:
        """Empty all queues.

        This is used to clear the event queue before sending a command
        to ensure that we don't process stale data.
        """
        self._empty_data_queue()
        self._empty_event_response_frame_queue()
        self._empty_response_frame_queue()

    def _handle_final_response_frame(self) -> Result[str, str]:
        match self._wait_for_response_frame():
            case Ok(rf):
                if rf.is_ok():
                    return Ok(rf.response)
                else:
                    return Err(rf.response)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
    def set_io(
        self: Self, io: int, menu_cmd: IOMenuCommand, pwm_freq: None | int = None, pwm_duty: None | int = None
    ) -> Result[str, str]:
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
        self._empty_all()
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

        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def set_board_leds(self: Self, io: int, red: int, green: int, blue: int) -> Result[str, str]:
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
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # s) Set Board LED [25 100 100 100]
        cmd = f"g\ns\n{io} {red} {green} {blue}"

        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def get_io(self) -> Result[tuple[int, ...], str]:
        """Get all the IO values.

        Parameters:
        ----------
            None

        Returns:
        -------
            Result[tuple[int], str]:
                Ok(tuple[int]) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"o\n{IOMenuCommand.Get.menu_character}"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(f"Failed to get IO values: {rf.response}")
                all_io_values = int(rf.response, 16)
                values = []
                for i in range(32):
                    io_value = (all_io_values >> i) & 0x1
                    values.append(io_value)
                return Ok(tuple(values))
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

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
        raise NotImplementedError("TODO")

    @needs_open()
    def write_i2c(self, address: int, register: int, data: bytes) -> Result[str, str]:
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
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
                The str is the response in the Response Frame from the FreeWili.
        """
        data_bytes = " ".join(f"{i:02X}" for i in data)
        cmd = f"i\nw\n{address:02X} {register:02X} {data_bytes}"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(f"Failed to write to I2C address {address:02X}: {rf.response}")
                return Ok(rf.response)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
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
        self._empty_all()
        cmd = f"i\nr\n{address:02X} {register:02X} {data_size}"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(f"Failed to read I2C addresses: {rf.response}")
                match rf.response_as_bytes():
                    case Ok(response):
                        return Ok(response)
                    case Err(msg):
                        return Err(msg)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
    def poll_i2c(self) -> Result[tuple[int, ...], str]:
        """Poll I2C addresses connected to the FreeWili.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[tuple[int, ...], str]:
                Ok(tuple[int, ...]) if the command was sent successfully, Err(str) if not.
                The tuple is a list of I2C addresses found.
        """
        self._empty_all()
        cmd = "i\np"
        self.serial_port.send(cmd)

        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(f"Failed to poll I2C addresses: {rf.response}")
                match rf.response_as_bytes():
                    case Ok(response):
                        return Ok(tuple(response[1:]))
                    case Err(msg):
                        return Err(msg)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
    def show_gui_image(self, fwi_path: str) -> Result[str, str]:
        """Show a fwi image on the display.

        Arguments:
        ----------
            fwi_path: str
                path to the fwi image

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # l) Show FWI Image [pip_boy.fwi]
        self._empty_all()
        cmd = f"g\nl\n{fwi_path}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def reset_display(self) -> Result[str, str]:
        """Reset the display back to the main menu.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # t) Reset Display
        self._empty_all()
        cmd = "g\nt"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def show_text_display(self, text: str) -> Result[str, str]:
        """Show text on the display.

        Arguments:
        ----------
            text: str
                text to display on screen.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # p) Show Text Display
        self._empty_all()
        cmd = f"g\np\n{text}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def read_all_buttons(self) -> Result[dict[ButtonColor, bool], str]:
        """Read all the buttons.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[dict[ButtonColor, bool], str]:
                Ok(dict[ButtonColor, bool]) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # u) Read All Buttons
        button_colors = [ButtonColor.White, ButtonColor.Yellow, ButtonColor.Green, ButtonColor.Blue, ButtonColor.Red]
        self._empty_all()
        cmd = "g\nu"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(rf.response)
                button_responses = {}
                match rf.response_as_bytes():
                    case Ok(resp):
                        for i, button_state in enumerate(resp):
                            button_responses[button_colors[i]] = button_state != 0
                        return Ok(button_responses)
                    case Err(msg):
                        return Err(msg)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")
        return self._handle_final_response_frame()

    @needs_open()
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
        raise NotImplementedError("TODO")

    @needs_open()
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
        raise NotImplementedError("TODO")

    @needs_open()
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
        raise NotImplementedError("TODO")

    @needs_open()
    def enable_stream(self, enable: bool) -> None:
        """TODO: Docstring."""
        raise NotImplementedError

    @needs_open()
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
        self._empty_all()
        cmd = f"w\n{file_name}"
        self.serial_port.send(cmd)
        resp = self._wait_for_response_frame()
        return resp

    @needs_open()
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
        self._empty_all()
        cmd = f"m\n{file_name}"
        self.serial_port.send(cmd)
        resp = self._wait_for_response_frame()
        return resp

    @needs_open()
    def send_file(
        self, source_file: pathlib.Path, target_name: str, event_cb: Callable | None, chunk_size: int = 0
    ) -> Result[str, str]:
        """Send a file to the FreeWili.

        Arguments:
        ----------
        source_file: pathlib.Path
            Path to the file to be sent.
        target_name: str
            Name of the file in the FreeWili.
        event_cb: Callable | None
            event callback function. Takes one arguments - a string.
                def user_callback(msg: str) -> None
        chunk_size: int
            Size of the chunks to send in bytes. Typically this should be left at the default value.

        Returns:
        -------
            Result[str, str]:
                Returns Ok(str) if the command was sent successfully, Err(str) if not.
        """

        def _user_cb_func(msg: str) -> None:
            if callable(event_cb):
                event_cb(msg)

        start = time.time()
        self._empty_all()
        # Adjust the chunk_size
        if chunk_size == 0:
            # 32768 seemed to be the fastest from testing.
            # Below 1024 the transfer was slow and caused firmware resets
            chunk_size = 32768
        # verify the file exists
        if not isinstance(source_file, pathlib.Path):
            source_file = pathlib.Path(source_file)
        if not source_file.exists():
            msg = f"{source_file} does not exist."
            _user_cb_func(msg)
            return Err(msg)
        fsize = source_file.stat().st_size
        # generate the checksum
        _user_cb_func("Generating checksum...")
        checksum = 0
        with source_file.open("rb") as f:
            while chunk := f.read(65535):
                checksum = zlib.crc32(chunk, checksum)
        # send the file
        _user_cb_func(f"Requesting file transfer of {source_file} ({fsize} bytes) to {target_name}...")
        cmd = f"x\nf\n{target_name} {fsize} {checksum}"
        self.serial_port.send(cmd, delay_sec=0.0)
        match self._wait_for_response_frame():
            case Ok(rf):
                _user_cb_func(f"Firmware response: {rf.response}")
            case Err(msg):
                _user_cb_func(msg)
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")
        with source_file.open("rb") as f:
            total_sent = 0
            while chunk := f.read(chunk_size):
                total_sent += len(chunk)
                self.serial_port.send(chunk, False, delay_sec=0)
                _user_cb_func(f"Sent {total_sent}/{fsize} bytes of {source_file}. {total_sent / fsize * 100:.2f}%")
                rf_event = self._wait_for_event_response_frame(0)
                if rf_event.is_ok():
                    _user_cb_func(f"Firmware response: {rf_event.ok_value.response}")
        while (rf_event := self._wait_for_event_response_frame(1)).is_ok():
            _user_cb_func(f"Firmware response: {rf_event.ok_value.response}")
        if total_sent != fsize:
            msg = f"Sent {total_sent} bytes but expected {fsize} bytes."
            _user_cb_func(msg)
            return Err(msg)
        match self._wait_for_response_frame():
            case Ok(rf):
                msg = f"Sent {target_name} in {time.time() - start:.2f} seconds: {rf.response}"
                _user_cb_func(msg)
                return Ok(msg)
            case Err(msg):
                _user_cb_func(msg)
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
    def get_file(self, source_file: str, destination_path: pathlib.Path, event_cb: Callable | None) -> Result[str, str]:
        """Get a file from the FreeWili.

        Arguments:
        ----------
        source_file: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12
        destination_path: pathlib.Path
            file path to save on the PC
        event_cb: Callable | None
            event callback function. Takes one arguments - a string.
                def user_callback(msg: str) -> None

        Returns:
        -------
            Result[str, str]:
                Returns Ok(str) if the command was sent successfully, Err(str) if not.
        """

        def _user_cb_func(msg: str) -> None:
            if callable(event_cb):
                event_cb(msg)

        # send the download command
        start_time = time.time()
        self._empty_all()
        _user_cb_func("Sending command...")
        self.serial_port.send(f"x\nu\n{source_file} \n", False, delay_sec=0.1)
        _user_cb_func("Waiting for response frame...")
        rf = self._wait_for_response_frame()
        if rf.is_err():
            return Err(f"Failed to get file {source_file}: {rf.err_value}")
        rf = rf.ok_value
        fsize: int = 0
        if not rf.is_ok():
            msg = f"Request to get file {source_file} failed: {rf.unwrap().response}"
            _user_cb_func(msg)
            return Err(msg)
        else:
            fsize = int(rf.response.split(" ")[-1])
            _user_cb_func(f"Requested file {source_file} successfully with {fsize} bytes.")
        _user_cb_func(f"Opening/Creating file {destination_path}")
        checksum = 0
        with open(destination_path, "wb") as f:
            count = 0
            _user_cb_func("Waiting for data...")
            # Count how many bytes we have collected since last user callback
            cb_timeout_byte_count: int = 0
            last_bytes_received = time.time()
            while count < fsize:
                # Make sure we aren't sitting here spinning forever
                if time.time() - last_bytes_received >= 6.0:
                    return Err(f"Failed to get all file data {source_file}: Got {count} of expected {fsize} bytes.")
                try:
                    data = self.serial_port.data_queue.get_nowait()
                except queue.Empty:
                    time.sleep(0.001)
                    continue
                last_bytes_received = time.time()
                count += len(data)
                cb_timeout_byte_count += len(data)
                if cb_timeout_byte_count >= 4096:
                    _user_cb_func(f"Saving {source_file} {count} of {fsize} bytes. {count / fsize * 100:.2f}%")
                    cb_timeout_byte_count = 0
                f.write(data)
                checksum = zlib.crc32(data, checksum)
                self.serial_port.data_queue.task_done()
                rf_event = self._wait_for_event_response_frame(0)
                if rf_event.is_ok():
                    _user_cb_func(f"Firmware response: {rf_event.ok_value.response}")
            _user_cb_func(f"Saved {source_file} {count} bytes to {destination_path}. {count / fsize * 100:.2f}%")
        # b'[u 0DF8213FA48CA2A3 295 success 153624 bytes 1743045997 crc 1]\r\n'
        rf = self._wait_for_response_frame()
        if rf.is_ok():
            _user_cb_func(rf.ok_value.response)
            # success 153624 bytes 1743045997 crc
            values = rf.ok_value.response.split(" ")
            crc = int(values[-2])
            sent_size = int(values[-4])
            if sent_size != count:
                return Err(f"Failed to get file {source_file}: Sent size mismatch. Expected {fsize}, received {count}")
            if crc != checksum:
                return Err(f"Failed to get file {source_file}: CRC mismatch. calculated {checksum}, received {crc}")
            return Ok(f"Saved {destination_path} with {count} bytes in {time.time() - start_time:.3f} seconds")
        else:
            return rf

    def reset_to_uf2_bootloader(self) -> Result[None, str]:
        """Reset the FreeWili to the uf2 bootloader.

        Returns:
        -------
            Result[None, str]:
                Returns Ok(None) if the command was sent successfully, Err(str) if not.
        """
        self.serial_port.close()
        try:
            serial_port = serial.Serial(self.serial_port.port, baudrate=1200, exclusive=True)
            serial_port.close()
        except serial.serialutil.SerialException as ex:
            if platform.system() == "Windows":
                # SerialException("Cannot configure port, something went wrong.
                # Original message:
                # PermissionError(13, 'A device attached to the system is not functioning.', None, 31)")
                return Ok(None)
            return Err(f"Failed to reset to UF2 bootloader {str(ex)}")
        return Ok(None)

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
        raise NotImplementedError("TODO")
        # start = time.time()
        # while self._serial.in_waiting == 0:
        #     time.sleep(0.001)
        #     if time.time() - start > timeout_sec:
        #         raise TimeoutError(f"Timed out waiting for data on {self}")
        # time.sleep(delay_sec)

    @needs_open()
    def get_app_info(self) -> Result[FreeWiliAppInfo, str]:
        """Detect the processor type of the FreeWili.

        Returns:
        -------
            Result[FreeWiliProcessorType, str]:
                Returns Ok(FreeWiliProcessorType) if the command was sent successfully, Err(str) if not.
        """
        self.serial_port.send("?")
        resp = self._wait_for_response_frame()
        if resp.is_err():
            return Err(resp.err())
        proc_type_regex = re.compile(r"(?:Main|Display)|(?:App version)|(?:\d+)")
        results = proc_type_regex.findall(resp.unwrap().response)
        if len(results) != 2:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))
        # New firmware >= 48
        processor = results[0]
        version = results[1]
        if "Main" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, int(version)))
        elif "Display" in processor:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Display, int(version)))
        else:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, int(version)))

        self.serial_port.send("", True, "\r\n\r\n")
        time.sleep(3)
        all_data = []
        while True:
            try:
                data = self.serial_port.data_queue.get_nowait()
                all_data.append(data)
            except Empty:
                break

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
