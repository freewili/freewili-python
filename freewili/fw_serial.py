"""Module for serial communication with FreeWili boards.

This module provides functionality to find and control FreeWili boards.
"""

import datetime
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

from freewili.types import (
    ButtonColor,
    EventType,
    FileSystemContents,
    FreeWiliAppInfo,
    FreeWiliProcessorType,
    IOMenuCommand,
)

# Disable menu Ctrl+b
CMD_DISABLE_MENU = b"\x02"
# Enable menu Ctrl+c
CMD_ENABLE_MENU = b"\x03"


class FreeWiliSerial:
    """Class representing a serial connection to a FreeWili."""

    def __init__(self, port: str, stay_open: bool = False, name: str = "", is_badge: bool = False) -> None:
        self.serial_port = SerialPort(port, 1000000, name)
        self.last_menu_option: None | bool = None
        self.user_event_callback: None | Callable[[EventType, ResponseFrame, Any], None] = None
        self._stay_open = stay_open
        self.is_badge = is_badge

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

    def set_event_callback(self, event_cb: None | Callable[[EventType, ResponseFrame, Any], None]) -> None:
        """Set the event callback for the FreeWili.

        Parameters:
        ----------
            event_cb: Callable[[EventType, ResponseFrame, Any], None]:
                The callback to call when an event is received.
                The first argument is the EventType, the second is the ResponseFrame,
                and the third is any additional data passed to the callback.
        """
        self.user_event_callback = event_cb

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
            self._set_menu_enabled(True)
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
        self.serial_port.send(f"q\nq\n{CMD_ENABLE_MENU.decode('ascii')}" if enabled else CMD_DISABLE_MENU)
        if enabled:
            self._wait_for_data(2.0, "Enter Letter:").expect("Failed to enable menu!")
            time.sleep(0.01)  # Give some time for the menu to be enabled

    def _wait_for_response_frame(self, timeout_sec: float = 6.0, what_msg: str = "") -> Result[ResponseFrame, str]:
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
        return Err(f"Failed to read response frame in {timeout_sec} seconds: {what_msg}")

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
    def toggle_high_speed_io(self, enable: bool) -> Result[str, str]:
        """Enable or disable high-speed IO.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable high-speed IO.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"o\ne\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

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
        if self.is_badge:
            self.serial_port.send("g\ng")
            self._handle_final_response_frame()
            cmd = f"s\n{io} {red} {green} {blue}\nq\nq"
            self.serial_port.send(cmd)
        else:
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
        data_bytes = " ".join(f"{i:02X}" for i in data)
        cmd = f"s\nw\n{data_bytes}"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame():
            case Ok(rf):
                if not rf.is_ok():
                    return Err(f"Failed to write to SPI data: {rf.response}")
                return rf.response_as_bytes()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

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
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        # k) GUI Functions
        # l) Show FWI Image [pip_boy.fwi]
        self._empty_all()
        if self.is_badge:
            self.serial_port.send("g\ng", delay_sec=0.1)
            self._handle_final_response_frame()
            cmd = f"l\n{fwi_path}\nq\nq"
            self.serial_port.send(cmd)
        else:
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
        if self.is_badge:
            self.serial_port.send("g\ng", delay_sec=0.0)
            self._handle_final_response_frame()
            cmd = "t\nq\nq"
            self.serial_port.send(cmd)
        else:
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
        if self.is_badge:
            self.serial_port.send("g\ng")
            self._handle_final_response_frame()
            cmd = f"p\n{text}\nq\nq"
            self.serial_port.send(cmd)
        else:
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
        if self.is_badge:
            self.serial_port.send("g\ng")
            self._handle_final_response_frame()
            cmd = "u\nq\nq"
            self.serial_port.send(cmd)
        else:
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
    def enable_accel_events(self, enable: bool, interval_ms: int | None) -> Result[str, str]:
        """Enable or disable accelerometer events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable accelerometer events.
            interval_ms: int | None
                The interval in milliseconds for accelerometer events. If None, the default value will be used.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        if interval_ms is None:
            # Use the default value
            interval_ms = 100
        self._empty_all()
        cmd = f"r\no\n{0 if not enable else int(interval_ms)}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_gpio_events(self, enable: bool, interval_ms: int | None) -> Result[str, str]:
        """Enable or disable GPIO events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable GPIO events.
            interval_ms: int | None
                The interval in milliseconds for GPIO events. If None, the default value will be used.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        if interval_ms is None:
            # Use the default value
            interval_ms = 100
        self._empty_all()
        cmd = f"o\no\n{0 if not enable else int(interval_ms)}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_button_events(self, enable: bool, interval_ms: int | None) -> Result[str, str]:
        """Enable or disable button events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable button events.
            interval_ms: int | None
                The interval in milliseconds for button events. If None, the default value will be used.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        if interval_ms is None:
            # Use the default value
            interval_ms = 100
        self._empty_all()
        cmd = f"g\no\n{0 if not enable else int(interval_ms)}"
        if self.is_badge:
            cmd = "g\n" + cmd + "\nq\nq"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_ir_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable IR events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable IR events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"i\no\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_battery_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable battery events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable battery events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"s\no\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_radio_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable radio events on currently selected radio.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable radio events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"r\nr\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_uart_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable UART events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable UART events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"u\nr\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def enable_audio_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable audio events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable audio events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"a\ns\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    def process_events(self, delay_sec: float | None = None) -> None:
        """Process events from the FreeWili.

        Parameters:
        -----------
            delay_sec: float | None
                The delay in seconds to wait before processing the next event. None uses the default value.

        This method will read events from the serial port and call the user event callback if set.
        """
        if not callable(self.user_event_callback):
            return
        if delay_sec is None:
            delay_sec = 0.001  # Default to 1 millisecond
        for k in self.serial_port.rf_events.keys():
            frames = self.serial_port.rf_events.pop(k)
            for frame in frames:
                event_type: EventType = EventType.from_frame(frame)
                data_type = event_type.get_data_type()
                data = data_type.from_string(frame.response)
                self.user_event_callback(event_type, frame, data)
        time.sleep(delay_sec)

    @needs_open()
    def select_radio(self, radio_index: int) -> Result[str, str]:
        """Select the radio to use for events.

        Arguments:
        ----------
            radio_index: int
                Index of the radio to select.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"r\ns\n{radio_index}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def set_radio_event_rssi_threshold(self, rssi: int) -> Result[str, str]:
        """Set the RSSI threshold for the specified radio.

        Arguments:
        ----------
            rssi: int
                RSSI threshold value to set.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"r\nt\n{rssi}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def set_radio_event_sample_window(self, sample_window_ms: int) -> Result[str, str]:
        """Set the sample window (ms) for the specified radio.

        Arguments:
        ----------
            sample_window_ms: int
                Sample window value to set.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"r\nf\n{sample_window_ms}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def transmit_radio_subfile(self, sub_fname: str) -> Result[str, str]:
        """Transmit a radio subfile.

        Arguments:
        ----------
            sub_fname: str
                Name of the subfile to transmit. This should be the filename with the extension.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"r\np\n{sub_fname}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def write_radio(self, data: bytes) -> Result[str, str]:
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
        self._empty_all()
        data_str = " ".join(f"{b:02x}" for b in data)
        cmd = f"r\np\n{data_str}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def write_uart(self, data: bytes | str) -> Result[str, str]:
        """Write uart data.

        Parameters:
        ----------
            data : bytes | str
                The data to write.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        assert isinstance(data, (bytes, str)), "data must be bytes or str"
        if isinstance(data, str):
            data = data.encode("utf-8")
        data_str = " ".join(f"{b:02x}" for b in data)
        cmd = f"u\nw\n{data_str}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def send_ir(self, data: bytes) -> Result[str, str]:
        """Send IR data.

        Notes: v54 firmware uses NEC format and is converted to an 32-bit integer.

        Parameters:
        ----------
            data : bytes
                The data to send. The first 4 bytes are used as the command.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        assert isinstance(data, bytes), "data must be bytes"
        data_int: int = int.from_bytes(data[:4], "big")
        cmd = f"i\na\n{data_int}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def play_audio_file(self, file_name: str) -> Result[str, str]:
        """Play an audio file on the FreeWili.

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
        cmd = f"a\nf\n{file_name}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def play_audio_asset(self, asset_value: str | int) -> Result[str, str]:
        """Play an audio asset on the FreeWili.

        Arguments:
        ----------
        asset_value: str | int
            The asset value to play.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"a\na\n{asset_value}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def play_audio_number_as_speech(self, value: int) -> Result[str, str]:
        """Play an audio number as speech on the FreeWili.

        Arguments:
        ----------
        value: int
            The audio number to play.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"a\nn\n{value}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def play_audio_tone(self, frequency_hz: int, duration_sec: float, amplitude: float) -> Result[str, str]:
        """Play an audio tone on the FreeWili.

        Arguments:
        ----------
        frequency_hz: int
            The frequency of the tone in Hertz.
        duration_sec: float
            The duration of the tone in seconds.
        amplitude: float
            The amplitude of the tone (0.0 to 1.0).

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        assert isinstance(frequency_hz, int)
        cmd = f"a\nt\n{frequency_hz} {duration_sec:.2f} {amplitude:.2f}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def record_audio(self, file_name: str) -> Result[str, str]:
        """Record audio on the FreeWili.

        Arguments:
        ----------
        file_name: str
            Name of the file in the FreeWili. (ie. "/sounds/test.wav")

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"a\nr\n{file_name}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def reset_software(self) -> Result[str, str]:
        """Soft reset the FreeWili.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        time.sleep(1)
        self.serial_port.send("z\\n\n")
        self.serial_port.close()
        time.sleep(3.0)
        return Ok("Software reset command sent. Please reconnect.")

    @needs_open()
    def stop_script(self) -> Result[str, str]:
        """Stop any running script on the FreeWili.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        # The blank after the y is required to stop all scripts
        self.serial_port.send("y \n")
        match self._handle_final_response_frame():
            case Ok(resp):
                return Ok(resp)
            case Err(msg):
                # As of v91 firmware the response frame reports back 0 for success
                if msg.lower == "ok":
                    return Ok(msg)
                return Ok(msg)
            case _:
                raise RuntimeError("Missing case statement")

    @needs_open()
    def run_script(self, file_name: str, stop_first: bool) -> Result[str, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
        file_name: str
            Name of the file in the FreeWili. 8.3 filename limit exists as of V12

        stop_first: bool
            Whether to stop any running scripts before starting the new one.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        if stop_first:
            # The blank after the y is required to stop all scripts
            self.serial_port.send("y \n")
            self._wait_for_response_frame(2.0)
        cmd = f"w\n{file_name}"
        self.serial_port.send(cmd)
        match self._wait_for_response_frame(2.0):
            case Ok(resp):
                return Ok(resp.response)
            case Err(msg):
                msg = f"{msg}:\nIs there already a script running?"
                try:
                    data = self.serial_port.data_queue.get_nowait()
                    output = data.decode("utf-8", errors="replace")
                    msg += output
                    return Err(msg)
                except queue.Empty:
                    return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

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
        match self._wait_for_response_frame(what_msg=f"starting file transfer of {source_file}"):
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
                self.serial_port.send(chunk, False, delay_sec=0.0)
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
        match self._wait_for_response_frame(what_msg=f"finalizing sent file {source_file}"):
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
        rf = self._wait_for_response_frame(what_msg=f"getting file {source_file}")
        if rf.is_err():
            return Err(f"Failed to get file {source_file}: {rf.err_value}")
        rf = rf.ok_value
        fsize: int = 0
        if not rf.is_ok():
            msg = f"Request to get file {source_file} failed: {rf.response}"
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

                # Only write up to fsize bytes to prevent frame data from being included
                # When the last chunk arrives, it might contain the final CRC response frame
                bytes_to_write = min(len(data), fsize - count)
                if bytes_to_write > 0:
                    chunk_to_write = data[:bytes_to_write]
                    f.write(chunk_to_write)
                    checksum = zlib.crc32(chunk_to_write, checksum)
                    count += bytes_to_write
                    cb_timeout_byte_count += bytes_to_write

                    if cb_timeout_byte_count >= 4096:
                        _user_cb_func(f"Saving {source_file} {count} of {fsize} bytes. {count / fsize * 100:.2f}%")
                        cb_timeout_byte_count = 0

                self.serial_port.data_queue.task_done()
                rf_event = self._wait_for_event_response_frame(0)
                if rf_event.is_ok():
                    _user_cb_func(f"Firmware response: {rf_event.ok_value.response}")
            _user_cb_func(f"Saved {source_file} {count} bytes to {destination_path}. {count / fsize * 100:.2f}%")

        # b'[u 0DF8213FA48CA2A3 295 success 153624 bytes 1743045997 crc 1]\r\n'
        rf = self._wait_for_response_frame(6.0, what_msg=f"CRC response {source_file}")
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
        attempts: int = 6
        success: bool = True
        while attempts > 0:
            try:
                serial_port = serial.Serial(self.serial_port.port, baudrate=1200, exclusive=True, timeout=0.100)
                serial_port.close()
                success = True
                break
            except serial.serialutil.SerialException:
                if platform.system() == "Windows":
                    # SerialException("Cannot configure port, something went wrong.
                    # Original message:
                    # PermissionError(13, 'A device attached to the system is not functioning.', None, 31)")
                    return Ok(None)
                attempts -= 1
                continue
        return Ok(None) if success else Err("Failed to reset to UF2 bootloader after multiple attempts.")

    @needs_open()
    def get_app_info(self) -> Result[FreeWiliAppInfo, str]:
        """Detect the processor type and version of the FreeWili.

        Returns:
        -------
            Result[FreeWiliProcessorType, str]:
                Returns Ok(FreeWiliProcessorType) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        self.serial_port.send("?")
        resp = self._wait_for_response_frame()
        if resp.is_err():
            return Err(str(resp.err()))
        proc_type_regex = re.compile(
            r"(?:MainCPU|DisplayCPU|Main|Display|DEFCON25|Winky|DEFCON24)|(?:App version)|(?:v?\d+(?:\.\d+)?)",
        )
        results = proc_type_regex.findall(resp.unwrap().response)
        if len(results) != 2:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, 0))
        # New firmware >= 48
        processor = results[0]
        version = results[1].lstrip("v")
        if "main" in processor.lower():
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, float(version)))
        elif "display" in processor.lower():
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Display, float(version)))
        elif "winky" in processor.lower():
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, float(version)))
        elif "defcon24" in processor.lower():
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, float(version)))
        elif "defcon25" in processor.lower():
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Main, float(version)))
        else:
            return Ok(FreeWiliAppInfo(FreeWiliProcessorType.Unknown, float(version)))

    @needs_open()
    def change_directory(self, directory: str) -> Result[str, str]:
        """Change the current directory on the FreeWili.

        Arguments:
        ----------
            directory: str
                The directory to change to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"x\na\n{directory}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def create_directory(self, directory: str) -> Result[str, str]:
        """Create a new directory on the FreeWili.

        Arguments:
        ----------
            directory: str
                The directory to create.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"x\nc\n{directory}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def remove_directory_or_file(self, dir_or_filename: str) -> Result[str, str]:
        """Remove a directory or file on the FreeWili.

        Arguments:
        ----------
            dir_or_filename: str
                The directory or file to remove.
                The directory to create.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"x\nr\n{dir_or_filename}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def create_blank_file(self, name: str) -> Result[str, str]:
        """Create a blank file on the FreeWili.

        Arguments:
        ----------
            name: str
                The name of the file to create.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"x\nb\n{name}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def move_directory_or_file(self, original_name: str, new_name: str) -> Result[str, str]:
        """Move a directory or file on the FreeWili.

        Arguments:
        ----------
            original_name: str
                The original name of the directory or file to move.
            new_name: str
                The new name of the directory or file.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"x\nn\n{original_name} {new_name}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def format_filesystem(self) -> Result[str, str]:
        """Format the filesystem on the FreeWili.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = "x\nt\ndestroyfiles"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open(enable_menu=True)
    def list_current_directory(self) -> Result[FileSystemContents, str]:
        """List the contents of the current directory on the FreeWili.

        Returns:
        -------
            Result[FileSystemContents, str]:
                Ok(FileSystemContents) if the command was sent successfully, Err(str) if not.
        """
        from freewili.types import FileSystemContents, FileSystemItem, FileType

        self._empty_all()
        # re-print the menu to get the filesystem listing
        cmd = ""
        self.serial_port.send(cmd)

        # Collect all output data
        collected_data = ""
        start = time.time()
        while time.time() - start <= 6.0:
            try:
                data = self.serial_port.data_queue.get_nowait().decode("utf-8", errors="ignore")
                collected_data += data
                if "Enter Letter:" in data:
                    break
            except queue.Empty:
                time.sleep(0.001)
                continue

        # Remove ANSI escape codes and normalize line endings
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        collected_data = ansi_escape.sub("", collected_data)
        collected_data = collected_data.replace("\r\n", "\n").replace("\r", "\n")

        # Parse the filesystem output
        lines = [line.strip() for line in collected_data.split("\n") if line.strip()]

        # Find the filesystem section
        fs_start_idx = None
        cwd = "/"

        for i, line in enumerate(lines):
            if "File System" in line and "bytes free" in line:
                fs_start_idx = i
                break

        if fs_start_idx is None:
            return Err("Could not find filesystem information in output")

        # Look for directory line (e.g., "/ directory contents")
        for i in range(fs_start_idx + 1, len(lines)):
            line = lines[i].strip()
            if "directory contents" in line:
                cwd = line.split(" directory contents")[0].strip()
                fs_start_idx = i
                break

        if fs_start_idx is None:
            return Err("Could not find directory contents section")

        # Parse file/directory entries
        items = []
        for i in range(fs_start_idx + 1, len(lines)):
            line = lines[i].strip()
            if not line:
                continue

            # Skip menu lines or other non-filesystem content
            menu_prefixes = (
                "a)",
                "b)",
                "c)",
                "d)",
                "e)",
                "f)",
                "g)",
                "h)",
                "i)",
                "j)",
                "k)",
                "l)",
                "m)",
                "n)",
                "o)",
                "p)",
                "q)",
                "r)",
                "s)",
                "t)",
                "u)",
                "v)",
                "w)",
                "x)",
                "y)",
                "z)",
            )
            if line.startswith(menu_prefixes):
                break

            # Parse file/dir entries: "file  settings.txt  0 bytes" or "dir   scripts"
            parts = line.split()
            if len(parts) >= 2:
                file_type_str = parts[0]
                name = parts[1]

                if file_type_str == "file" and len(parts) >= 4 and parts[3] == "bytes":
                    # File entry: "file  settings.txt  0 bytes"
                    try:
                        size = int(parts[2])
                        items.append(FileSystemItem(name=name, file_type=FileType.File, size=size))
                    except ValueError:
                        # If size parsing fails, default to 0
                        items.append(FileSystemItem(name=name, file_type=FileType.File, size=0))
                elif file_type_str == "dir":
                    # Directory entry: "dir   scripts"
                    items.append(FileSystemItem(name=name, file_type=FileType.Directory, size=0))

        return Ok(FileSystemContents(cwd=cwd, contents=items))

    def _wait_for_data(self, timeout: float, regex_pattern: str) -> Result[str, str]:
        """Wait for data to be available from the serial port.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if data was received successfully, Err(str) if not.
        """
        start = time.time()
        while (time.time() - start) < timeout:
            # print("DEBUG: Waiting for data...")
            try:
                data = self.serial_port.data_queue.get_nowait().decode("ascii", errors="ignore")
                # print("DEBUG: Received data:", data.strip())
                if res := re.search(regex_pattern, data):
                    return Ok(res.group().strip())
            except Empty:
                time.sleep(0.001)  # Sleep briefly to avoid busy waiting
                continue
        return Err(f"Timeout ({timeout:<.1f}s) waiting for data")

    @needs_open(True)
    def get_rtc(self) -> Result[tuple[datetime.datetime, int], str]:
        """Get the RTC (Real-Time Clock) from the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[tuple[datetime.datetime, int], str]:
                Ok(tuple[datetime.datetime, int]) if the command was sent successfully, Err(str) if not.
        """

        def extract_int(text: str) -> int:
            """Extract an integer from a string."""
            if match := re.search(r"\[(\d+)\]", text):
                value = int(match.group(1))
                return value
            return -999

        self._empty_all()
        self.serial_port.send("z")
        self._wait_for_data(1.0, r"Enter Letter").expect("Failed to get settings menu")
        self.serial_port.send("t")
        self._wait_for_data(1.0, r"Enter Letter").expect("Failed to get settings menu")
        self.serial_port.send("")
        year = self._wait_for_data(1.0, r"Year.*").expect("Failed to get RTC year")
        self.serial_port.send("")
        month = self._wait_for_data(1.0, r"Month.*").expect("Failed to get RTC month")
        self.serial_port.send("")
        day = self._wait_for_data(1.0, r"Day.*").expect("Failed to get RTC day")
        # day_of_week = self._wait_for_data(1.0, r"Day of Week").expect("Failed to get RTC day of week")
        self.serial_port.send("")
        hour = self._wait_for_data(1.0, r"Hour.*").expect("Failed to get RTC hour")
        self.serial_port.send("")
        minute = self._wait_for_data(1.0, r"Minute.*").expect("Failed to get RTC minute")
        self.serial_port.send("")
        second = self._wait_for_data(1.0, r"Second.*").expect("Failed to get RTC second")
        self.serial_port.send("")
        trim = self._wait_for_data(1.0, r"Trim.*").expect("Failed to get RTC trim")
        return Ok(
            (
                datetime.datetime(
                    extract_int(year),
                    extract_int(month),
                    extract_int(day),
                    extract_int(hour),
                    extract_int(minute),
                    extract_int(second),
                    0,
                    None,  # Use None for timezone to indicate naive datetime
                ),
                extract_int(trim),
            )
        )

    @needs_open()
    def set_rtc(self, dt: datetime.datetime, trim: int | None = None) -> Result[str, str]:
        """Set the RTC (Real-Time Clock) on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            dt: datetime
                The datetime to set the RTC to.
            trim: int | None
                The trim value to set. (-127 - 127). If None, no trim is set.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        days = (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        )
        values = [
            (dt.year % 2000, "y"),
            (dt.month, "n"),
            (dt.day, "d"),
            (dt.hour, "h"),
            (dt.minute, "m"),
            (days[dt.weekday()], "w"),  # 0=Monday, 6=Sunday
            (dt.second, "s"),
        ]
        self._empty_all()
        for value, letter in values:
            # We need q at the end because menu reset doesn't reset the submenu here
            cmd = f"z\nt\n{letter}\n{value}\nq\n"
            self.serial_port.send(cmd)
            # Reset to the top level menu
            self._set_menu_enabled(False)
        if trim is not None:
            cmd = f"z\nt\nt\n{trim}"
            self.serial_port.send(cmd, delay_sec=0.05)
            res = self._handle_final_response_frame()
            if res.is_err():
                return res
        return Ok("RTC set successfully")

    @needs_open(True)
    def set_settings_to_default(self) -> Result[str, str]:
        """Set the settings to default on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        time.sleep(0.1)
        self._empty_all()
        cmd = "z\nz\nq"
        self.serial_port.send(cmd)
        return self._wait_for_data(3.0, r"Done!")

    @needs_open(True)
    def set_settings_as_startup(self) -> Result[str, str]:
        """Set the settings as startup on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = "z\ns\nq\n"
        self.serial_port.send(cmd)
        return self._wait_for_data(3.0, r"Done!")

    @needs_open(True)
    def set_system_sounds(self, enable: bool) -> Result[str, str]:
        """Set the system sounds on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable system sounds.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        self.serial_port.send("z")
        self._wait_for_data(1.0, r"Enter Letter:").expect("Failed to get settings menu 1")
        time.sleep(0.1)
        self.serial_port.send("g")
        self._wait_for_data(1.0, r"Enter Letter:").expect("Failed to get settings menu 2")
        self.serial_port.send("p")
        self._wait_for_data(1.0, r"System Sounds Enter Number").expect("Failed to get settings menu 3")
        self.serial_port.send("1" if enable else "0")
        return self._wait_for_data(3.0, r"Enter Letter:")

    # WilEye Camera Commands
    @needs_open()
    def wileye_take_picture(self, destination: int, filename: str) -> Result[str, str]:
        """Take a picture using the WilEye camera.

        Arguments:
        ----------
            destination: int
                Destination processor (0 = WILEye's SDCard, 1 = FREE-WILi's Main Filesystem,
                2 = FREE-WILi's Display Filesystem)
            filename: str
                Name of the file to save the picture as

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\t {destination} {filename}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def wileye_start_recording_video(self, destination: int, filename: str) -> Result[str, str]:
        """Start recording video using the WilEye camera.

        Arguments:
        ----------
            destination: int
                Destination processor (0 = WILEye's SDCard, 1 = FREE-WILi's Main Filesystem,
                2 = FREE-WILi's Display Filesystem)
            filename: str
                Name of the file to save the video as

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\v {destination} {filename}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def wileye_stop_recording_video(self) -> Result[str, str]:
        """Stop recording video using the WilEye camera.

        Arguments:
        ----------
            None

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = "e\\c\\s"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_contrast(self, contrast: int) -> Result[str, str]:
        """Set the contrast level for the WilEye camera.

        Arguments:
        ----------
            contrast: int
                Contrast level (percentage, 0-100)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\c {contrast}\n"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_saturation(self, saturation: int) -> Result[str, str]:
        """Set the saturation level for the WilEye camera.

        Arguments:
        ----------
            saturation: int
                Saturation level (percentage, 0-100)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\i {saturation}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_brightness(self, brightness: int) -> Result[str, str]:
        """Set the brightness level for the WilEye camera.

        Arguments:
        ----------
            brightness: int
                Brightness level (percentage, 0-100)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\b {brightness}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_hue(self, hue: int) -> Result[str, str]:
        """Set the hue level for the WilEye camera.

        Arguments:
        ----------
            hue: int
                Hue level (percentage, 0-100)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\u {hue}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_flash_enabled(self, enabled: bool) -> Result[str, str]:
        """Enable or disable the flash for the WilEye camera.

        Arguments:
        ----------
            enabled: bool
                True to enable flash, False to disable

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\l {1 if enabled else 0}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_zoom_level(self, zoom_level: int) -> Result[str, str]:
        """Set the zoom level for the WilEye camera.

        Arguments:
        ----------
            zoom_level: int
                Zoom levels [1-4] (1 = no zoom, 4 = max zoom)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\m {zoom_level}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()

    @needs_open()
    def wileye_set_resolution(self, resolution_index: int) -> Result[str, str]:
        """Set the resolution for the WilEye camera.

        Arguments:
        ----------
            resolution_index: int
                Resolution index:
                    0 = 640x480
                    1 = 1280x720
                    2 = 1920x1080

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"e\\c\\y {resolution_index}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_transmit(self, channel: int, can_id: int, data: bytes, is_extended: bool, is_fd: bool) -> Result[str, str]:
        """Transmit a CAN or CAN FD frame.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            can_id: int
                CAN ID (11-bit for standard, 29-bit for extended)
            data: bytes
                Data payload (0-64 bytes for CAN FD, 0-8 bytes for standard CAN)
            is_extended: bool
                True if using extended CAN ID (29-bit), False for standard (11-bit)
            is_fd: bool
                True if using CAN FD, False for standard CAN

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e, f w Channel ArbID (hex) isCANFD isXtd Bytes (hex)
        self._empty_all()
        data_bytes = " ".join(f"{i:02X}" for i in data)
        cmd = f"e\\f\\w {channel} {can_id:02X} {1 if is_fd else 0} {1 if is_extended else 0} {data_bytes}\n"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_enable_transmit_periodic(self, index: int, enabled: bool) -> Result[str, str]:
        """Enable/Disable periodic transmission of a CAN or CAN FD frame.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                Index of the periodic frame to enable
            enabled: bool
                True to enable periodic transmission, False to disable

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e, f, p index enable period (us) Channel ArbID (hex) isCANFD isXtd Bytes (hex)
        self._empty_all()
        cmd = f"e\\f\\p {index} {1 if enabled else 0}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_set_transmit_periodic(
        self,
        channel: int,
        index: int,
        period_us: int,
        arb_id: int,
        is_fd: bool,
        is_extended: bool,
        data: bytes,
    ) -> Result[str, str]:
        """Transmit a periodic CAN or CAN FD frame.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                Index of the periodic frame to set
            period_us: int
                Period in microseconds. As of v87 firmware, minimum is 500 us.
            arb_id: int
                CAN Arbitration ID
            is_fd: bool
                True if using CAN FD, False for standard CAN
            is_extended: bool
                True if using extended CAN ID (29-bit), False for standard (11-bit)
            data: bytes | tuple[int, ...]
                Data payload (0-64 bytes for CAN FD, 0-8 bytes for standard CAN)

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e, f, p index enable period (us) Channel ArbID (hex) isCANFD isXtd Bytes (hex)
        self._empty_all()
        data_bytes = " ".join(f"{i:02X}" for i in data)
        cmd = f"e\\f\\p {index} 1 {period_us} {channel} "
        cmd += f"{arb_id:02X} {1 if is_fd else 0} {1 if is_extended else 0} {data_bytes}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_enable_streaming(self, channel: int, enabled: bool) -> Result[str, str]:
        """Enable/Disable CAN or CAN FD frame streaming.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            enabled: bool
                True to enable streaming, False to disable

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e f o Channel enable
        self._empty_all()
        cmd = f"e\\f\\o {channel} {1 if enabled else 0}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_set_rx_filter(
        self,
        channel: int,
        index: int,
        is_extended: bool,
        mask_id: int,
        id: int | None,
        mask_b0: int,
        b0: int,
        mask_b1: int,
        b1: int,
    ) -> Result[str, str]:
        """Set a CAN or CAN FD filter.

        See can_enable_rx_filter to enable/disable the filter.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                index of the filter (0-31)
            is_extended: bool
                True if using extended CAN ID (29-bit), False for standard (11-bit)
            mask_id: int
                CAN ID (11-bit for standard, 29-bit for extended)
            id: int
                ID to filter on
            mask_b0: int
                Mask byte 0
            b0: int
                Byte 0
            mask_b1: int
                Mask byte 1
            b1: int
                Byte 1

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e f f channel (0-1), index (0-32), enable, isXTD, mskID, ID, [mskb0, b0, mskb1, b1]
        # 0 0 0 1 1 1 1 1 1
        self._empty_all()
        cmd = f"e\\f\\f {channel} {index} 1 {1 if is_extended else 0} {mask_id:02X} {id:02X} "
        cmd += f" {mask_b0:02X} {b0:02X} {mask_b1:02X} {b1:02X}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_enable_rx_filter(
        self,
        channel: int,
        index: int,
        enable: bool,
    ) -> Result[str, str]:
        """Enable or disable a CAN RX filter.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                index of the filter (0-31)
            enable: bool
                True to enable the filter, False to disable

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e f f channel (0-1) index (0-32) enable isXTD mskID ID (opt) mskb0 b0 mskb1 b1
        raise RuntimeError("TODO: not implemented")
        # self._empty_all()
        # cmd = f"e\\f\\f {channel} {index} {1 if enable else 0}"
        # self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_read_registers(
        self,
        channel: int,
        address: int,
        wordcount: int,
    ) -> Result[str, str]:
        """Read CAN registers.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            address: int
                Register address (hex)
            wordcount: int
                Number of words to read

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e f r channel (0-1) address (hex) wordcount
        self._empty_all()
        cmd = f"e\\f\\r {channel} {address:02X} {wordcount}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def can_write_registers(
        self,
        channel: int,
        address: int,
        bytesize: int,
        word: int,
    ) -> Result[str, str]:
        """Write CAN registers.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            address: int
                Register address (hex)
            bytesize: int
                Bytes per word (1 or 4)
            word: int
                Word to write (hex)

        Returns:
        --------
            Result[None, str]:
                Ok(None) if the command was sent successfully, Err(str) if not.
        """
        # e f s channel (0-1) address (hex) bytesize (1,4) word (hex)
        self._empty_all()
        cmd = f"e\\f\\s {channel} {address:02X} {bytesize} {word:02X}"
        self.serial_port.send(cmd)

        return self._handle_final_response_frame()

    @needs_open()
    def enable_nfc_read_events(self, enable: bool) -> Result[str, str]:
        """Enable or disable NFC read events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable NFC read events.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        self._empty_all()
        cmd = f"n\nr\n{0 if not enable else 1}"
        self.serial_port.send(cmd)
        return self._handle_final_response_frame()
