"""For Interfacing to Free-Wili Devices."""

import datetime
import pathlib
import platform
import sys
from dataclasses import dataclass
from typing import Any, Callable, List

from freewili.fw_serial import FreeWiliSerial

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import pyfwfinder as fwf
from result import Err, Ok, Result

from freewili.framing import ResponseFrame
from freewili.types import (
    ButtonColor,
    EventType,
    FileSystemContents,
    FreeWiliAppInfo,
    FreeWiliProcessorType,
    IOMenuCommand,
)

# USB Locations:
# first address = FTDI
FTDI_HUB_LOC_INDEX = 2
# second address = Display
DISPLAY_HUB_LOC_INDEX = 1
# third address = Main
MAIN_HUB_LOC_INDEX = 0


class FreeWili:
    """Free-Wili device used to access FTDI and serial functionality."""

    def __init__(self, device: fwf.FreeWiliDevice):
        self.device = device
        self._stay_open = False

        self._main_serial: None | FreeWiliSerial = None
        self._display_serial: None | FreeWiliSerial = None

    def __str__(self) -> str:
        return f"{self.device.name} {self.device.serial} ({self.device.device_type.name})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.device.serial}>"

    def __enter__(self) -> Self:
        self.open().expect("Failed to open FreeWili")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, FreeWili):
            return False
        return self.device == value.device

    def set_event_callback(self, event_cb: None | Callable[[EventType, ResponseFrame, Any], None]) -> None:
        """Set the event callback for the FreeWili.

        Parameters:
        -----------
            event_cb: Callable[[EventType, ResponseFrame, Any], None]
                Callback function to be called when an event occurs.
                The function should accept three arguments: the event type, the response frame,
                and any additional data.
                Set to None to disable the callback.
        """
        if self.main_serial:
            self.main_serial.set_event_callback(event_cb)
        if self.display_serial:
            self.display_serial.set_event_callback(event_cb)

    @property
    def standalone(self) -> bool:
        """Check if the FreeWili is a standalone device.

        Returns:
        bool:
            True if the FreeWili is a standalone device, False otherwise.
        """
        return self.device.standalone

    @property
    def unique_id(self) -> int:
        """Get the unique ID of the FreeWili device.

        Returns:
        int:
            Unique ID of the FreeWili device.
        """
        return self.device.unique_id

    @property
    def usb_devices(self) -> List[fwf.USBDevice]:
        """Grab all the USB devices attached to the FreeWili."""
        return self.device.usb_devices

    @property
    def hub(self) -> None | fwf.USBDevice:
        """Get the Hub USB Device.

        Returns:
        None | fwf.USBDevice:
            USB Device on success, None otherwise.
        """
        try:
            return self.device.get_hub_usb_device()
        except Exception as _e:
            return None

    @property
    def fpga(self) -> None | fwf.USBDevice:
        """Get the FPGA USB Device.

        Returns:
        None | fwf.USBDevice:
            USB Device on success, None otherwise.
        """
        try:
            return self.device.get_fpga_usb_device()
        except Exception as _e:
            return None

    @property
    def main(self) -> None | fwf.USBDevice:
        """Get the Main USB Device.

        Returns:
        None | fwf.USBDevice:
            USB Device on success, None otherwise.
        """
        try:
            return self.device.get_main_usb_device()
        except Exception as _e:
            return None

    @property
    def display(self) -> None | fwf.USBDevice:
        """Get the Display USB Device.

        Returns:
        None | fwf.USBDevice:
            USB Device on success, None otherwise.
        """
        try:
            return self.device.get_display_usb_device()
        except Exception as _e:
            return None

    @property
    def main_serial(self) -> None | FreeWiliSerial:
        """Get Main FreeWiliSerial.

        Arguments:
        ----------
            None

        Returns:
        ---------
            None | FreeWiliSerial:
                FreeWiliSerial on success, None otherwise.
        """
        if self._main_serial:
            return self._main_serial
        elif self.main and self.main.port:
            self._main_serial = FreeWiliSerial(self.main.port, self._stay_open, "Main: " + str(self), self.standalone)
            return self._main_serial
        else:
            return None

    @property
    def display_serial(self) -> None | FreeWiliSerial:
        """Get Display FreeWiliSerial.

        Arguments:
        ----------
            None

        Returns:
        ---------
            None | FreeWiliSerial:
                FreeWiliSerial on success, None otherwise.
        """
        if self._display_serial:
            return self._display_serial
        elif self.display and self.display.port:
            self._display_serial = FreeWiliSerial(
                self.display.port, self._stay_open, "Display: " + str(self), self.standalone
            )
            return self._display_serial
        else:
            return None

    def get_serial_from(self, processor_type: FreeWiliProcessorType) -> Result[FreeWiliSerial, str]:
        """Get FreeWiliSerial from processor type.

        Arguments:
        ----------
            processor_type: FreeWiliProcessorType
                Processor type to get serial port for.

        Returns:
        ---------
            Result[FreeWiliSerial, str]:
                Ok(FreeWiliSerial) on success, Err(str) otherwise.
        """
        match processor_type:
            case FreeWiliProcessorType.Main:
                if self.main_serial:
                    return Ok(self.main_serial)
                else:
                    return Err("Main serial isn't valid")
            case FreeWiliProcessorType.Display:
                if self.display_serial:
                    return Ok(self.display_serial)
                elif self.standalone:
                    return self.get_serial_from(FreeWiliProcessorType.Main)
                else:
                    return Err("Display serial isn't valid")

    def open(self, block: bool = True, timeout_sec: float = 6.0) -> Result[None, str]:
        """Open the serial port. Use in conjunction with stay_open.

        Arguments:
        ----------
            block: bool:
                If True, block until the serial port is opened.
            timeout_sec: float:
                number of seconds to wait when blocking.

        Returns:
        ---------
            Result[None, str]:
                Ok(None) if successful, Err(str) otherwise.
        """
        if self.main_serial:
            result = self.main_serial.open(block, timeout_sec)
            if result.is_err():
                return Err(str(result.err()))
        if self.display_serial:
            result = self.display_serial.open(block, timeout_sec)
            if result.is_err():
                return Err(str(result.err()))
        return Ok(None)

    def close(self, restore_menu: bool = True) -> None:
        """Close the serial port. Use in conjunction with stay_open.

        Arguments:
        ----------
            restore_menu: bool
                Restore the menu functionality before close

        Returns:
        ---------
            None
        """
        if self.main_serial:
            self.main_serial.close()
        if self.display_serial:
            self.display_serial.close()

    @classmethod
    def find_first(cls) -> Result[Self, str]:
        """Find first Free-Wili device attached to the host.

        Parameters:
        ------------
            None

        Returns:
        ---------
            Result[FreeWili, str]:
                Ok(FreeWili) if successful, Err(str) otherwise.

        Raises:
        -------
            None
        """
        try:
            devices = cls.find_all()
            if not devices:
                return Err("No FreeWili devices found!")
            return Ok(devices[0])
        except Exception as ex:
            return Err(str(ex))

    @classmethod
    def find_all(cls) -> tuple[Self, ...]:
        """Find all Free-Wili devices attached to the host.

        Parameters:
        ------------
            None

        Returns:
        ---------
            tuple[FreeWili, ...]:
                Tuple of FreeWili devices.

        Raises:
        -------
            None
        """
        found_devices: List[fwf.FreeWiliDevice] = fwf.find_all()
        fw_devices: list[Self] = []
        for device in found_devices:
            fw_devices.append(cls(device))
        return tuple(fw_devices)

    def send_file(
        self,
        source_file: str | pathlib.Path,
        target_name: None | str = None,
        processor: None | FreeWiliProcessorType = None,
        event_cb: Callable | None = None,
        chunk_size: int = 0,
    ) -> Result[str, str]:
        """Send a file to the FreeWili.

        Arguments:
        ----------
            source_file: pathlib.Path
                Path to the file to be sent.
            target_name: None | str
                Name of the file in the FreeWili. If None, will be determined automatically based on the filename.
            processor: None | FreeWiliProcessorType
                Processor to upload the file to. If None, will be determined automatically based on the filename.
            event_cb: Callable | None
                event callback function. Takes one argument of a string.
                    def user_callback(msg: str) -> None
            chunk_size: int
                Size of the chunks to send in bytes. Typically this should be left at the default value.

        Returns:
        ---------
            Result[str, str]:
                Returns Ok(str) if the command was sent successfully, Err(str) if not.
        """
        try:
            # Auto assign values that are None
            if not target_name:
                target_name = FileMap.from_fname(str(source_file)).to_path(str(source_file))
            if not processor:
                processor = FileMap.from_fname(str(source_file)).processor
        except ValueError as ex:
            return Err(str(ex))
        assert target_name is not None
        assert processor is not None

        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.send_file(source_file, target_name, event_cb, chunk_size)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def get_file(
        self,
        source_file: str,
        destination_path: str | pathlib.Path,
        processor: FreeWiliProcessorType | None = None,
        event_cb: Callable | None = None,
    ) -> Result[str, str]:
        """Send a file to the FreeWili.

        Arguments:
        ----------
            source_file: pathlib.Path
                Path to the file to be sent.
            destination_path: pathlib.Path
                file path to save on the PC
            processor: None | FreeWiliProcessorType
                Processor to upload the file to. If None, will be determined automatically based on the filename.
            event_cb: Callable | None
                event callback function. Takes one argument of a string.
                    def user_callback(msg: str) -> None

        Returns:
        ---------
            Result[str, str]:
                Returns Ok(str) if the command was sent successfully, Err(str) if not.
        """
        try:
            # Auto assign values that are None
            if not processor:
                processor = FileMap.from_fname(str(source_file)).processor
        except ValueError as ex:
            return Err(str(ex))
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.get_file(source_file, destination_path, event_cb)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def reset_software(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main) -> Result[str, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.reset_software()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def stop_script(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main) -> Result[str, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.stop_script()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def run_script(
        self, file_name: str, stop_first: bool, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Run a script on the FreeWili.

        Arguments:
        ----------
            file_name: str
                Name of the file in the FreeWili. 8.3 filename limit exists as of V12
            stop_first: bool
                Whether to stop any running scripts before starting the new one.
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.run_script(file_name, stop_first)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def load_fpga_from_file(
        self, file_name: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Load FPGA from file.

        Arguments:
        ----------
            file_name: str
                Name of the file in the FreeWili. 8.3 filename limit exists as of V12
                'spi','uart','i2c' or a filename name with extension.
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.load_fpga_from_file(file_name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def get_io(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main) -> Result[tuple[int, ...], str]:
        """Get all the IO values.

        Parameters:
        ------------
            processor: FreeWiliProcessorType
                Processor to set IO on.

        Returns:
        ---------
            Result[tuple[int], str]:
                Ok(tuple[int]) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.get_io()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def toggle_high_speed_io(
        self: Self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Toggle the high-speed Bidirectional IO.

        Parameters:
        ------------
            enable: bool
                Whether to enable or disable high-speed IO.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.toggle_high_speed_io(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_io(
        self: Self,
        io: int,
        menu_cmd: IOMenuCommand,
        pwm_freq: None | int = None,
        pwm_duty: None | int = None,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the state of an IO pin to high or low.

        Parameters:
        ------------
            io : int
                The number of the IO pin to set.
            menu_cmd : IOMenuCommand
                Whether to set the pin to high, low, toggle, or pwm.
            pwm_freq: None | int
                PWM frequency in Hertz
            pwm_duty: None | int
                PWM Duty cycle (0-100)
            processor: FreeWiliProcessorType
                Processor to set IO on.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_io(io, menu_cmd, pwm_freq, pwm_duty)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_board_leds(
        self: Self,
        io: int,
        red: int,
        green: int,
        blue: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Set the GUI RGB LEDs.

        Parameters:
        ------------
            io : int
                The number of the IO pin to set.
            red : int
                Red Color 0-255
            green : int
                Green Color 0-255
            blue : int
                Blue Color 0-255
            processor: FreeWiliProcessorType
                Processor to set LEDs on.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_board_leds(io, red, green, blue)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def read_write_spi_data(
        self, data: bytes, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Read and Write SPI data.

        Parameters:
        -----------
            data : bytes
                The data to write.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
                The str is the response from the device, typically "OK".
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.read_write_spi_data(data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def read_i2c(
        self, address: int, register: int, data_size: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[bytes, str]:
        """Write I2C data.

        Parameters:
        ------------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data_size : int
                The number of bytes to read.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.read_i2c(address, register, data_size)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def write_i2c(
        self, address: int, register: int, data: bytes, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Write I2C data.

        Parameters:
        -----------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data : bytes
                The data to write.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
                The str is the response from the device, typically "OK".
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.write_i2c(address, register, data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def poll_i2c(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main) -> Result[tuple[int, ...], str]:
        """Poll I2C data.

        Parameters:
        ------------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[tuple[int, ...], str]:
                Ok(tuple[int, ...]) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.poll_i2c()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def show_gui_image(
        self, fwi_path: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Show a fwi image on the display.

        Arguments:
        ----------
            fwi_path: str
                path to the fwi image
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.show_gui_image(fwi_path)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def show_text_display(
        self, text: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Show text on the display.

        Arguments:
        ----------
            text: str
                text to display on screen.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.show_text_display(text)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def read_all_buttons(
        self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[dict[ButtonColor, bool], str]:
        """Read all the buttons.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[dict[ButtonColor, bool], str]:
                Ok(dict[ButtonColor, bool]) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.read_all_buttons()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def reset_display(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display) -> Result[str, str]:
        """Reset the display back to the main menu.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.reset_display()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_accel_events(
        self,
        enable: bool,
        interval_ms: int | None = None,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Enable or disable acceleration events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable acceleration events.
            interval_ms: int | None
                The interval in milliseconds for accelerometer events. If None, the default value will be used.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_accel_events(enable, interval_ms)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_gpio_events(
        self,
        enable: bool,
        interval_ms: int | None = None,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable or disable GPIO events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable GPIO events.
            interval_ms: int | None
                The interval in milliseconds for GPIO events. If None, the default value will be used.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_gpio_events(enable, interval_ms)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_button_events(
        self,
        enable: bool,
        interval_ms: int | None = None,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Enable or disable acceleration events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable acceleration events.
            interval_ms: int | None
                The interval in milliseconds for accelerometer events. If None, the default value will be used.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_button_events(enable, interval_ms)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_ir_events(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Enable or disable infrared events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable infrared events.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_ir_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_battery_events(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Enable or disable battery events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable battery events.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_battery_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_radio_events(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable or disable radio events on currently selected radio.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable radio events.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_radio_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_uart_events(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable or disable UART events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable UART events.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_uart_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_audio_events(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Enable or disable audio events.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable audio events.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_audio_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def process_events(self) -> None:
        """Process any events that have been received.

        This is typically called in a loop to process events as they come in.
        """
        if self.main_serial:
            self.main_serial.process_events()
        if self.display_serial:
            self.display_serial.process_events()

    def select_radio(
        self, radio_index: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Select the radio to use for events.

        Arguments:
        ----------
            radio_index: int
                Index of the radio to select. 1 or 2 typically.

            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.select_radio(radio_index)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_radio_event_rssi_threshold(
        self, rssi: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Set the RSSI threshold for radio events.

        Arguments:
        ----------
            rssi: int
                RSSI threshold value to set.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_radio_event_rssi_threshold(rssi)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_radio_event_sample_window(
        self, sample_window_ms: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Set the sample window (ms) for the specified radio.

        Arguments:
        ----------
            sample_window_ms: int
                Sample window value to set.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_radio_event_sample_window(sample_window_ms)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def transmit_radio_subfile(
        self, sub_fname: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Transmit a subfile to the specified radio.

        Arguments:
        ----------
            sub_fname: str
                Name of the subfile to transmit. This should be the filename with the extension.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.transmit_radio_subfile(sub_fname)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def write_radio(
        self, data: bytes, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Write radio data.

        Arguments:
        ----------
            data: bytes
                Data to transmit.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.write_radio(data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def write_uart(
        self, data: bytes | str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Write uart data.

        Arguments:
        ----------
            data: bytes
                Data to transmit.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.write_uart(data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def send_ir(
        self, data: bytes, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Send IR data.

        Notes: v54 firmware uses NEC format and is converted to an 32-bit integer.

        Parameters:
        ----------
            data : bytes
                The data to send. The first 4 bytes are used as the command.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[bytes, str]:
                Ok(bytes) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.send_ir(data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def play_audio_file(
        self, file_name: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Play an audio file on the FreeWili.

        Arguments:
        ----------
            file_name: str
                Name of the file in the FreeWili. 8.3 filename limit exists as of V12
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.play_audio_file(file_name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def play_audio_asset(
        self, asset_value: str | int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Play an audio asset on the FreeWili.

        Arguments:
        ----------
            asset_value: str | int
                The asset value to play.
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.play_audio_asset(asset_value)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def play_audio_number_as_speech(
        self, value: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Play an audio number as speech on the FreeWili.

        Arguments:
        ----------
            value: int
                The audio number to play.
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.play_audio_number_as_speech(value)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def play_audio_tone(
        self,
        frequency_hz: int,
        duration_sec: float,
        amplitude: float,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Play an audio tone on the FreeWili.

        Arguments:
        ----------
            frequency_hz: int
                The frequency of the tone in Hertz.
            duration_sec: float
                The duration of the tone in seconds.
            amplitude: float
                The amplitude of the tone (0.0 to 1.0).
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.play_audio_tone(frequency_hz, duration_sec, amplitude)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def record_audio(
        self, file_name: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[str, str]:
        """Record audio on the FreeWili.

        Arguments:
        ----------
            file_name: str
                Name of the file in the FreeWili. (ie. "/sounds/test.wav")
            processor: FreeWiliProcessorType
                Processor to upload the file to.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.record_audio(file_name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def change_directory(self, directory: str, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Change the current directory for file operations.

        Arguments:
        ----------
            directory: str
                The directory to change to.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.change_directory(directory)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def create_directory(self, directory: str, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Create a new directory on the FreeWili.

        Arguments:
        ----------
            directory: str
                The directory to create.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.create_directory(directory)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def remove_directory_or_file(self, dir_or_filename: str, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Remove a directory or file on the FreeWili.

        Arguments:
        ----------
            dir_or_filename: str
                The directory or file to remove.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.remove_directory_or_file(dir_or_filename)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def create_blank_file(self, name: str, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Create a blank file on the FreeWili.

        Arguments:
        ----------
            name: str
                The name of the file to create.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.create_blank_file(name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def move_directory_or_file(
        self, original_name: str, new_name: str, processor: FreeWiliProcessorType
    ) -> Result[str, str]:
        """Move a directory or file on the FreeWili.

        Arguments:
        ----------
            original_name: str
                The original name of the directory or file to move.
            new_name: str
                The new name of the directory or file.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.move_directory_or_file(original_name, new_name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def format_filesystem(self, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Format the filesystem on the FreeWili.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.format_filesystem()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def list_current_directory(self, processor: FreeWiliProcessorType) -> Result[FileSystemContents, str]:
        """List the contents of the current directory on the FreeWili.

        Note: This API is currently considered experimental and may change in the future.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[FileSystemContents, str]:
                Ok(FileSystemContents) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.list_current_directory()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def reset_to_uf2_bootloader(self, processor: FreeWiliProcessorType) -> Result[None, str]:
        """Reset the FreeWili to the uf2 bootloader.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[None, str]:
                Returns Ok(None) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.reset_to_uf2_bootloader()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def get_rtc(
        self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[tuple[datetime.datetime, int], str]:
        """Get the RTC (Real-Time Clock) from the FreeWili.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[tuple[datetime.datetime, int], str]:
                Ok(tuple[datetime.datetime, int]) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.get_rtc()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_rtc(
        self,
        dt: datetime.datetime,
        trim: int | None = None,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the RTC (Real-Time Clock) on the FreeWili.

        Arguments:
        ----------
            dt: datetime
                The datetime to set the RTC to.
            trim: int | None
                The trim value to set. (-127 - 127). If None, no trim is set.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_rtc(dt, trim)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_settings_to_default(self, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Set the settings to default on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_settings_to_default()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_settings_as_startup(self, processor: FreeWiliProcessorType) -> Result[str, str]:
        """Set the settings as startup on the FreeWili.

        Notes: Settings are unstable as of v54 firmware. Subject to change in future firmware versions.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_settings_as_startup()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def set_system_sounds(
        self,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Display,
    ) -> Result[str, str]:
        """Set the system sounds on the FreeWili.

        Arguments:
        ----------
            enable: bool
                Whether to enable or disable system sounds.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_system_sounds(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    # WilEye Camera Commands
    def wileye_take_picture(
        self,
        destination: int,
        filename: str,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Take a picture using the WilEye camera.

        Arguments:
        ----------
            destination: int
                Destination processor (0 = Main, 1 = Display)
            filename: str
                Name of the file to save the picture as
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_take_picture(destination, filename)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_start_recording_video(
        self,
        destination: int,
        filename: str,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Start recording video using the WilEye camera.

        Arguments:
        ----------
            destination: int
                Destination processor
                    0 = WILEye's SDCard
                    1 = FREE-WILi's Main Filesystem
                    2 = FREE-WILi's Display Filesystem
            filename: str
                Name of the file to save the video as
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_start_recording_video(destination, filename)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_stop_recording_video(
        self,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Stop recording video using the WilEye camera.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_stop_recording_video()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_contrast(
        self,
        contrast: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the contrast level for the WilEye camera.

        Arguments:
        ----------
            contrast: int
                Contrast level (percentage, 0-100)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_contrast(contrast)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_saturation(
        self,
        saturation: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the saturation level for the WilEye camera.

        Arguments:
        ----------
            saturation: int
                Saturation level (percentage, 0-100)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_saturation(saturation)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_brightness(
        self,
        brightness: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the brightness level for the WilEye camera.

        Arguments:
        ----------
            brightness: int
                Brightness level (percentage, 0-100)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_brightness(brightness)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_hue(
        self,
        hue: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the hue level for the WilEye camera.

        Arguments:
        ----------
            hue: int
                Hue level (percentage, 0-100)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_hue(hue)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_flash_enabled(
        self,
        enabled: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable or disable the flash for the WilEye camera.

        Arguments:
        ----------
            enabled: bool
                True to enable flash, False to disable
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_flash_enabled(enabled)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_zoom_level(
        self,
        zoom_level: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the zoom level for the WilEye camera.

        Arguments:
        ----------
            zoom_level: int
                Zoom levels [1-4] (1 = no zoom, 4 = max zoom)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_zoom_level(zoom_level)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def wileye_set_resolution(
        self,
        resolution_index: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set the resolution for the WilEye camera.

        Arguments:
        ----------
            resolution_index: int
                Resolution index:
                    0 = 640x480
                    1 = 1280x720
                    2 = 1920x1080
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        -------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.wileye_set_resolution(resolution_index)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def enable_nfc_read_events(
        self, enable: bool, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Enable or disable NFC read events.

        Parameters:
        ------------
            enable : bool
                Enable NFC reads if True, disable if False.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        ---------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.enable_nfc_read_events(enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_transmit(
        self,
        channel: int,
        can_id: int,
        data: bytes,
        is_extended: bool,
        is_fd: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Transmit a CAN or CAN FD frame.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            can_id: int
                CAN ID (11-bit for standard, 29-bit for extended)
            data: bytes | tuple[int, ...]
                Data payload (0-64 bytes for CAN FD, 0-8 bytes for standard CAN)
            is_extended: bool
                True if using extended CAN ID (29-bit), False for standard (11-bit)
            is_fd: bool
                True if using CAN FD, False for standard CAN
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_transmit(channel, can_id, data, is_extended, is_fd)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_enable_transmit_periodic(
        self,
        index: int,
        enabled: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable/Disable periodic transmission of a CAN or CAN FD frame.

        Arguments:
        ----------
            index: int
                Index of the periodic frame to enable
            enabled: bool
                True to enable periodic transmission, False to disable
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_enable_transmit_periodic(index, enabled)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_set_transmit_periodic(
        self,
        channel: int,
        index: int,
        period_us: int,
        arb_id: int,
        is_fd: bool,
        is_extended: bool,
        data: bytes,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set a periodic CAN or CAN FD frame.

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
            data: bytes
                Data payload (0-64 bytes for CAN FD, 0-8 bytes for standard CAN)
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_set_transmit_periodic(channel, index, period_us, arb_id, is_fd, is_extended, data)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_enable_streaming(
        self,
        channel: int,
        enabled: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable/Disable CAN or CAN FD frame streaming.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            enabled: bool
                True to enable streaming, False to disable
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_enable_streaming(channel, enabled)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

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
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Set a CAN or CAN FD filter.

        See can_enable_rx_filter to enable/disable the filter.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                Index of the filter (0-31)
            is_extended: bool
                True if using extended CAN ID (29-bit), False for standard (11-bit)
            mask_id: int
                CAN ID mask (11-bit for standard, 29-bit for extended)
            id: int | None
                ID to filter on
            mask_b0: int
                Mask byte 0
            b0: int
                Byte 0
            mask_b1: int
                Mask byte 1
            b1: int
                Byte 1
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_set_rx_filter(channel, index, is_extended, mask_id, id, mask_b0, b0, mask_b1, b1)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_enable_rx_filter(
        self,
        channel: int,
        index: int,
        enable: bool,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
    ) -> Result[str, str]:
        """Enable or disable a CAN RX filter.

        Arguments:
        ----------
            channel: int
                CAN channel (0 or 1)
            index: int
                Index of the filter (0-31)
            enable: bool
                True to enable the filter, False to disable
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_enable_rx_filter(channel, index, enable)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_read_registers(
        self,
        channel: int,
        address: int,
        wordcount: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
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
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_read_registers(channel, address, wordcount)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def can_write_registers(
        self,
        channel: int,
        address: int,
        bytesize: int,
        word: int,
        processor: FreeWiliProcessorType = FreeWiliProcessorType.Main,
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
            processor: FreeWiliProcessorType
                Processor to send the command to (default: Main)

        Returns:
        --------
            Result[str, str]:
                Ok(str) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.can_write_registers(channel, address, bytesize, word)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def get_app_info(
        self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[FreeWiliAppInfo, str]:
        """Detect the processor type and version of the FreeWili.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[FreeWiliProcessorType, str]:
                Returns Ok(FreeWiliProcessorType) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.get_app_info()
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")


@dataclass(frozen=True)
class FileMap:
    """Map file extension to processor type and location."""

    # file extension type (ie. .fwi)
    extension: str
    # processor the file should live on
    processor: FreeWiliProcessorType
    # directory the file type
    directory: str
    # description of the file type
    description: str

    @classmethod
    def from_ext(cls, ext: str) -> Self:
        """Creates a FileMap from a file extension.

        Parameters:
        ------------
            ext: str
                File extension (ie. ".wasm"). Not case sensitive.

        Returns:
        ---------
            FileMap

        Raises:
        -------
            ValueError:
                If the extension isn't known.
        """
        ext = ext.lstrip(".").lower()
        mappings = {
            "wasm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
            "wsm": (FreeWiliProcessorType.Main, "/scripts", "WASM binary"),
            "zio": (FreeWiliProcessorType.Main, "/scripts", "ZoomIO script file"),
            "bin": (FreeWiliProcessorType.Main, "/fpga", "FPGA bin file"),
            "sub": (FreeWiliProcessorType.Main, "/radio", "Radio file"),
            "fwi": (FreeWiliProcessorType.Display, "/images", "Image file"),
            "wav": (FreeWiliProcessorType.Display, "/sounds", "Audio file"),
            "py": (FreeWiliProcessorType.Main, "/scripts", "rthon script"),
        }
        if ext not in mappings:
            raise ValueError(f"Extension '{ext}' is not a known FreeWili file type")
        return cls(ext, *mappings[ext])

    @classmethod
    def from_fname(cls, file_name: str) -> Self:
        """Creates a FileMap from a file path.

        Parameters:
        ------------
            file_name: str
                File name (ie. "myfile.wasm"). Not case sensitive. Can contain paths.

        Returns:
        ---------
            FileMap

        Raises:
        -------
            ValueError:
                If the extension isn't known.
        """
        fpath = pathlib.Path(file_name)
        return cls.from_ext(fpath.suffix)

    def to_path(self, file_name: str) -> str:
        """Creates a file path from the file_name to upload to the FreeWili.

        Parameters:
        ------------
            file_name: str
                File name (ie. "myfile.wasm"). Not case sensitive. Can contain paths.

        Returns:
        ---------
            str
                Full file path intended to be uploaded to a FreeWili

        Raises:
        -------
            ValueError:
                If the extension isn't known.
        """
        fpath = pathlib.Path(file_name)
        fpath_str = str(pathlib.Path(self.directory) / fpath.name)
        if platform.system().lower() == "windows":
            fpath_str = fpath_str.replace("\\", "/")
        return fpath_str
