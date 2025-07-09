"""For Interfacing to Free-Wili Devices."""

import pathlib
import platform
import sys
from dataclasses import dataclass
from typing import Callable, List

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import pyfwfinder as fwf
from result import Err, Ok, Result

from freewili.framing import ResponseFrame
from freewili.serial_util import FreeWiliSerial
from freewili.types import ButtonColor, FreeWiliProcessorType, IOMenuCommand

# USB Locations:
# first address = FTDI
FTDI_HUB_LOC_INDEX = 2
# second address = Display
DISPLAY_HUB_LOC_INDEX = 1
# third address = Main
MAIN_HUB_LOC_INDEX = 0

# This maps the actual GPIO exposed on the connector, all others not
# listed here are internal to the processor.
GPIO_MAP = {
    8: "GPIO8/UART1_Tx_OUT",
    9: "GPIO9/UART1_Rx_IN",
    10: "GPIO10/UART1_CTS_IN",
    11: "GPIO11/UART1_RTS_OUT",
    12: "GPIO12/SPI1_Rx_IN",
    13: "GPIO13/SPI1_CS_OUT",
    14: "GPIO14/SPI1_SCLK_OUT",
    15: "GPIO15/SPI1_Tx_OUT",
    16: "GPIO16/I2C0 SDA",
    17: "GPIO17/I2C0 SCL",
    25: "GPIO25/GPIO25_OUT",
    26: "GPIO26/GPIO26_IN",
    27: "GPIO27/GPIO_27_OUT",
}


class FreeWili:
    """Free-Wili device used to access FTDI and serial functionality."""

    def __init__(self, device: fwf.FreeWiliDevice):
        self.device = device
        self._stay_open = False

        self._main_serial: None | FreeWiliSerial = None
        self._display_serial: None | FreeWiliSerial = None

    def __str__(self) -> str:
        return f"Free-Wili {self.device.serial}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.device.serial}>"

    @property
    def usb_devices(self) -> List[fwf.USBDevice]:
        """Grab all the USB devices attached to the FreeWili."""
        return self.device.usb_devices

    def get_usb_device(self, processor_type: FreeWiliProcessorType) -> None | fwf.USBDevice:
        """Get the USBDevice by ProcessorType.

        Parameters:
        ----------
            processor_type: FreeWiliProcessorType
                Type of processor to get.

        Returns:
        -------
            None | fwf.USBDevice:
                fwf.USBDevice if successful, None otherwise.

        Raises:
        -------
            None
        """
        match processor_type:
            case FreeWiliProcessorType.Main:
                devs = self.device.get_usb_devices(fwf.USBDeviceType.SerialMain)
                if devs:
                    return devs[0]
            case FreeWiliProcessorType.Display:
                devs = self.device.get_usb_devices(fwf.USBDeviceType.SerialDisplay)
                if devs:
                    return devs[0]
            case FreeWiliProcessorType.FTDI:
                devs = self.device.get_usb_devices(fwf.USBDeviceType.FTDI)
                if devs:
                    return devs[0]
            case FreeWiliProcessorType.ESP32:
                devs = self.device.get_usb_devices(fwf.USBDeviceType.ESP32)
                if devs:
                    return devs[0]
        # Get the processor by location
        # TODO: MAC will be broke here
        if processor_type in (FreeWiliProcessorType.Main, FreeWiliProcessorType.Display):
            for usb_device in self.usb_devices:
                if (
                    processor_type == FreeWiliProcessorType.Main
                    # and usb_device.kind == fwf.USBDeviceType.MassStorage
                    and usb_device.location == 1
                ):
                    return usb_device
                if (
                    processor_type == FreeWiliProcessorType.Display
                    # and usb_device.kind == fwf.USBDeviceType.MassStorage
                    and usb_device.location == 2
                ):
                    return usb_device
        # Legacy support for older VID/PID of Main/Display firmware.
        if len(self.usb_devices) < 3:
            return None
        match processor_type:
            case FreeWiliProcessorType.Main:
                device = self.usb_devices[0]
                return device
            case FreeWiliProcessorType.Display:
                device = self.usb_devices[1]
                return self.usb_devices[1]
        return None

    @property
    def ftdi(self) -> None | fwf.USBDevice:
        """Get FTDI processor."""
        return self.get_usb_device(FreeWiliProcessorType.FTDI)

    @property
    def main(self) -> None | fwf.USBDevice:
        """Get Main processor."""
        return self.get_usb_device(FreeWiliProcessorType.Main)

    @property
    def display(self) -> None | fwf.USBDevice:
        """Get Display processor."""
        return self.get_usb_device(FreeWiliProcessorType.Display)

    @property
    def esp32(self) -> None | fwf.USBDevice:
        """Get Display processor."""
        return self.get_usb_device(FreeWiliProcessorType.ESP32)

    @property
    def main_serial(self) -> None | FreeWiliSerial:
        """Get Main FreeWiliSerial.

        Arguments:
        ----------
            None

        Returns:
        --------
            None | FreeWiliSerial:
                FreeWiliSerial on success, None otherwise.
        """
        if not self._main_serial and self.main and self.main.port:
            self._main_serial = FreeWiliSerial(self.main.port, self._stay_open, "Main: " + str(self))
        if self._main_serial:
            self._main_serial.stay_open = self._stay_open
        return self._main_serial

    @property
    def display_serial(self) -> None | FreeWiliSerial:
        """Get Display FreeWiliSerial.

        Arguments:
        ----------
            None

        Returns:
        --------
            None | FreeWiliSerial:
                FreeWiliSerial on success, None otherwise.
        """
        if not self._display_serial and self.display and self.display.port:
            self._display_serial = FreeWiliSerial(self.display.port, self._stay_open, "Display: " + str(self))
        if self._display_serial:
            self._display_serial.stay_open = self._stay_open
        return self._display_serial

    def get_serial_from(self, processor_type: FreeWiliProcessorType) -> Result[FreeWiliSerial, str]:
        """Get FreeWiliSerial from processor type.

        Arguments:
        ----------
            processor_type: FreeWiliProcessorType
                Processor type to get serial port for.

        Returns:
        --------
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
                else:
                    return Err("Display serial isn't valid")
            case _:
                return Err(f"{processor_type} isn't a valid FreeWiliSerial type")

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
        """Open the serial port. Use in conjunction with stay_open.

        Arguments:
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
        if self.main_serial:
            result = self.main_serial.open(block, timeout_sec)
            if result.is_err():
                return Err(result.err())
        if self.display_serial:
            result = self.display_serial.open(block, timeout_sec)
            if result.is_err():
                return Err(result.err())
        return Ok(None)

    def close(self, restore_menu: bool = True) -> None:
        """Close the serial port. Use in conjunction with stay_open.

        Arguments:
        ----------
            restore_menu: bool
                Restore the menu functionality before close

        Returns:
        -------
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
        ----------
            None

        Returns:
        -------
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
        ----------
            None

        Returns:
        -------
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
        -------
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
        -------
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

    def run_script(
        self, file_name: str, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[str, str]:
        """Run a script on the FreeWili.

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
                return serial.run_script(file_name)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def get_io(self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main) -> Result[tuple[int, ...], str]:
        """Get all the IO values.

        Parameters:
        ----------
            processor: FreeWiliProcessorType
                Processor to set IO on.

        Returns:
        -------
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
        ----------
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
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
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
    ) -> Result[ResponseFrame, str]:
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
            processor: FreeWiliProcessorType
                Processor to set LEDs on.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.set_board_leds(io, red, green, blue)
            case Err(msg):
                return Err(msg)
            case _:
                raise RuntimeError("Missing case statement")

    def read_i2c(
        self, address: int, register: int, data_size: int, processor: FreeWiliProcessorType = FreeWiliProcessorType.Main
    ) -> Result[bytes, str]:
        """Write I2C data.

        Parameters:
        ----------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data_size : int
                The number of bytes to read.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
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
        ----------
            address : int
                The address to write to.
            register : int
                The register to write to.
            data : bytes
                The data to write.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
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
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
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
    ) -> Result[ResponseFrame, str]:
        """Show a fwi image on the display.

        Arguments:
        ----------
            fwi_path: str
                path to the fwi image
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
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
    ) -> Result[ResponseFrame, str]:
        """Show text on the display.

        Arguments:
        ----------
            text: str
                text to display on screen.
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
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
        -------
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

    def reset_display(
        self, processor: FreeWiliProcessorType = FreeWiliProcessorType.Display
    ) -> Result[ResponseFrame, str]:
        """Reset the display back to the main menu.

        Arguments:
        ----------
            processor: FreeWiliProcessorType
                Processor to use.

        Returns:
        -------
            Result[ResponseFrame, str]:
                Ok(ResponseFrame) if the command was sent successfully, Err(str) if not.
        """
        match self.get_serial_from(processor):
            case Ok(serial):
                return serial.reset_display()
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
        -------
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
        ----------
            ext: str
                File extension (ie. ".wasm"). Not case sensitive.

        Returns:
        --------
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
            "bit": (FreeWiliProcessorType.Main, "/fpga", "FPGA bit file"),
            "sub": (FreeWiliProcessorType.Display, "/radio", "Radio file"),
            "fwi": (FreeWiliProcessorType.Display, "/images", "Image file"),
            "wav": (FreeWiliProcessorType.Display, "/sounds", "Audio file"),
        }
        if ext not in mappings:
            raise ValueError(f"Extension '{ext}' is not a known FreeWili file type")
        return cls(ext, *mappings[ext])

    @classmethod
    def from_fname(cls, file_name: str) -> Self:
        """Creates a FileMap from a file path.

        Parameters:
        ----------
            file_name: str
                File name (ie. "myfile.wasm"). Not case sensitive. Can contain paths.

        Returns:
        --------
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
        ----------
            file_name: str
                File name (ie. "myfile.wasm"). Not case sensitive. Can contain paths.

        Returns:
        --------
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


if __name__ == "__main__":
    devices = FreeWili.find_all()
    print(f"Found {len(devices)} Free-Wili(s):")
    for i, dev in enumerate(devices):
        print(f"{i}. {dev}")
        ftdi = dev.ftdi
        main = dev.main
        display = dev.display
        print("\tFTDI:   ", ftdi)  # type: ignore
        print("\tMain:   ", main)  # type: ignore
        print("\tDisplay:", display)  # type: ignore
