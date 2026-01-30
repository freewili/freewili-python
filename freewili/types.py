"""Common data types and constants."""

import enum
import sys
from dataclasses import dataclass

from freewili.framing import ResponseFrame

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

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


class FreeWiliProcessorType(enum.Enum):
    """Processor type of the Free-Wili."""

    Main = enum.auto()
    Display = enum.auto()
    FTDI = enum.auto()
    Unknown = enum.auto()

    def __str__(self) -> str:
        return self.name


@dataclass
class FreeWiliAppInfo:
    """Information of the FreeWili application."""

    processor_type: FreeWiliProcessorType
    version: float

    def __str__(self) -> str:
        desc = f"{self.processor_type.name}"
        if self.processor_type in (FreeWiliProcessorType.Main, FreeWiliProcessorType.Display):
            desc += f" v{self.version}"
        return desc


class ButtonColor(enum.Enum):
    """Free-Wili Physical Button Color."""

    Unknown = enum.auto()
    White = enum.auto()
    Yellow = enum.auto()
    Green = enum.auto()
    Blue = enum.auto()
    Red = enum.auto()


class EventData(object):
    """Base class for Free-Wili event data types."""

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an instance of the subclass.

        Arguments:
        ----------
        data : str
            The string to convert.

        Returns:
        --------
        Self
            An instance of the subclass.

        Raises:
        -------
        NotImplementedError
            If the method is not implemented in the subclass.
        """
        raise NotImplementedError(f"{cls.__name__}.from_string() must be implemented in subclasses.")


@dataclass(frozen=True)
class Radio1Data(EventData):
    """Radio1 event data from Free-Wili Display."""

    # [*radio1 0DF6B2ADEAE711E2 4170 29 08 db 00 8e 90 ae e0 56 72 ... 1]
    data: bytes
    raw: str

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to a Radio1Data object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from a Radio1 event.

        Returns:
        --------
            Radio1Data:
                The converted Radio1Data object.
        """
        try:
            d: bytes = bytes([int(x, 16) for x in data.rstrip(" ").split(" ")])
            return cls(data=d, raw=data)
        except ValueError:
            # " RSSI below threshold, flushing RX buffer"
            return cls(data=b"", raw=data)


@dataclass(frozen=True)
class Radio2Data(Radio1Data):
    """Radio2 event data from Free-Wili Display."""

    # Inherits from Radio1Data, no additional fields or methods needed
    pass


@dataclass(frozen=True)
class UART1Data(Radio1Data):
    """UART1 event data from Free-Wili Display."""

    # Inherits from Radio1Data, no additional fields or methods needed
    pass


@dataclass(frozen=True)
class GPIOData(EventData):
    """GPIO event data from Free-Wili Display."""

    # [*gpioIn 0DF6B2ADB5DFB0B6 6 35873723 1]
    # raw GPIO pin states by index, 0 = low, 1 = high
    raw: list[int]
    # GPIO pin states with names, 0 = low, 1 = high
    pin: dict[str, int]

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to a GPIOData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from a GPIO event.

        Returns:
        --------
            GPIOData:
                The converted GPIOData object.
        """
        all_io_values = int(data, 16)
        values = []
        for i in range(32):
            io_value = (all_io_values >> i) & 0x1
            values.append(io_value)
        pin_states = {}
        for io_num, io_name in GPIO_MAP.items():
            pin_states[io_name] = values[io_num]
        return cls(raw=values, pin=pin_states)


@dataclass(frozen=True)
class AccelData(EventData):
    """Accelerometer event data from Free-Wili Display."""

    # [*accel 0DFEFB5DB4E34E9B 20 2g 64 -768 16448 29 84 4 1]
    # Force
    g: float
    # X acceleration
    x: float
    # Y acceleration
    y: float
    # Z acceleration
    z: float
    # Temperature in Celsius
    temp_c: float
    # Temp in Fahrenheit
    temp_f: float

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an AccelData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from an accel event.

        Returns:
        --------
            AccelData:
                The converted AccelData object.
        """
        """2g 832 1600 16448 31 89 0"""
        parts = data.split(" ")
        return cls(
            g=float(parts[0].strip("g")),
            x=float(parts[1]),
            y=float(parts[2]),
            z=float(parts[3]),
            temp_c=float(parts[4]),
            temp_f=float(parts[5]),
        )


@dataclass(frozen=True)
class ButtonData(EventData):
    """Button event data from Free-Wili Display."""

    # [*button 0E027CA91437D2F5 7450 0 0 0 0 0 1]
    gray: bool
    yellow: bool
    green: bool
    blue: bool
    red: bool

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an ButtonData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from a button event.

        Returns:
        --------
            ButtonData:
                The converted ButtonData object.
        """
        """2g 832 1600 16448 31 89 0"""
        parts = data.split(" ")
        return cls(
            gray=bool(int(parts[0])),
            yellow=bool(int(parts[1])),
            green=bool(int(parts[2])),
            blue=bool(int(parts[3])),
            red=bool(int(parts[4])),
        )


@dataclass(frozen=True)
class IRData(EventData):
    """IR event data from Free-Wili Display."""

    # [*irrx 0E02C19053D884DF 108 10008004 1]
    value: bytes

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an IRData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from an IR event.

        Returns:
        --------
            IRData:
                The converted IRData object.
        """
        try:
            return cls(value=bytes.fromhex(data.zfill(len(data) + len(data) % 2)))
        except ValueError:
            print(f"ERROR: Invalid IR data format: {data}", file=sys.stderr)
            # Return an empty IRData object if conversion fails
            # This is a fallback to ensure the program continues running
            # without crashing due to invalid data.
            return cls(value=b"")


@dataclass(frozen=True)
class AudioData(EventData):
    """Audio event data from Free-Wili Display."""

    # [*audio 0E00CC80AEF767E4 6165 -956 -1192 -1296 -1276 -1268 -1260 -1136 -940 1]
    data: list[int]

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an IRData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from an audio event.

        Returns:
        --------
            AudioData:
                The converted AudioData object.
        """
        data_int = [int(x) for x in data.split(" ")]
        return cls(data=data_int)


@dataclass(frozen=True)
class RawData(EventData):
    """Raw event data from Free-Wili Display."""

    value: str

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to a RawData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from an Unknown event.

        Returns:
        --------
            RawData:
                The converted RawData object.
        """
        return cls(value=data)


@dataclass(frozen=True)
class BatteryData(EventData):
    """Battery event data from Free-Wili Display."""

    vbus: float
    vsys: float
    vbatt: float
    ichg: int
    """Indicates if the battery is currently charging."""
    charging: bool
    """True if the battery is charging, False otherwise."""
    charge_complete: bool

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an BatteryData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from a battery event.

        Returns:
        --------
            BatteryData:
                The converted BatteryData object.
        """
        # [*battery 0E02C19093FFBC29 1353 489 416 410 0 1 1  1]
        parts = data.split(" ")
        vbus = float(parts[0])
        vsys = float(parts[1])
        vbatt = float(parts[2])
        ichg = int(parts[3])
        if vbus < 1000 and vsys < 1000 and vbatt < 1000:
            # v54 firmware looks like its math is off, so if everything is less than 1000, multiply by 10
            vbus *= 10.0
            vsys *= 10.0
            vbatt *= 10.0
        return cls(
            vbus=vbus,
            vsys=vsys,
            vbatt=vbatt,
            ichg=ichg,
            charging=bool(int(parts[4])),
            charge_complete=bool(int(parts[5])),
        )


@dataclass(frozen=True)
class NFCData(EventData):
    """NFC event data from Free-Wili Main."""

    # [*nfc 0D286B98B7093788 4 Card: T2T UID=043CE602234B80 ATQA=4400 SAK=00 1]
    # [*nfc 0D286B98B41B2400 3 Card removed 1]

    """Indicates if the nfc event was a card disconnecting."""
    disconnected: bool | None
    uid: bytes | None
    atqa: bytes | None
    sak: bytes | None
    """The card type as a string. A more sophisticated implementation would
        have classes for each supported card."""
    card_type: str | None

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to an NFCData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from an NFC event.

        Returns:
        --------
            NFCData:
                The converted NFCData object.
        """
        try:
            parts = data.split(" ")
            disconnected = parts[0] == "Card" and parts[1] == "removed"
            if disconnected:
                return cls(
                    disconnected=True,
                    uid=None,
                    atqa=None,
                    sak=None,
                    card_type=None,
                )
            card_type = parts[1]
            uid = bytes.fromhex(parts[2].split("=")[1])
            atqa = bytes.fromhex(parts[3].split("=")[1])
            sak = bytes.fromhex(parts[4].split("=")[1])
            return cls(
                disconnected=False,
                uid=uid,
                atqa=atqa,
                sak=sak,
                card_type=card_type,
            )
        except ValueError:
            print(f"ERROR: Invalid NFC data format: {data}", file=sys.stderr)
            # Return an empty NFCData object if conversion fails
            # This is a fallback to ensure the program continues running
            # without crashing due to invalid data.
            return cls(
                disconnected=None,
                uid=None,
                atqa=None,
                sak=None,
                card_type=None,
            )


@dataclass(frozen=True)
class CANData(EventData):
    """CAN event data from Free-Wili Neptune."""

    # w
    # Channel ArbID (hex) isCANFD isXtd Bytes (hex)

    # 0 9 1 1 01 02 03
    # [e\f\w 0D4B2535E0F2EED0 28 Ok 1]
    # [*can1 0D4B2535E108BCD8 29 9x 01 02 03 1]
    # [*canTx0 0D4B2535E1354348 30 9x 01 02 03 1]

    # w
    # Channel ArbID (hex) isCANFD isXtd Bytes (hex)

    # 0 9 1 0 01 02 03
    # [e\f\w 0D4B253EF45EF028 31 Ok 1]
    # [*can1 0D4B253EF47304C8 32 9 01 02 03 1]
    # [*canTx0 0D4B253EF4BCEEA8 33 9 01 02 03 1]

    # w
    # Channel ArbID (hex) isCANFD isXtd Bytes (hex)

    # 0 9 0 0 01 02 03
    # [e\f\w 0D4B254578129FE0 34 Ok 1]
    # [*can1 0D4B254578266E30 35 9 01 02 03 1]
    # [*canTx0 0D4B254578321A78 36 9 01 02 03 1]
    # CAN Arbitration ID
    arb_id: int
    # Indicates if using extended CAN ID (29-bit) or standard (11-bit)
    is_extended: bool
    # Data payload
    data: bytes

    @classmethod
    def from_string(cls, data: str) -> Self:
        """Convert a string to a CANData object.

        Arguments:
        ----------
            data: str
                The string to convert, typically from a CAN event.

        Returns:
        --------
            CANData:
                The converted CANData object.
        """
        # [*can1 0D4B254578266E30 35 9 01 02 03 1]
        # [*canTx0 0D4B254578321A78 36 9 01 02 03 1]
        # [*can1 0D4B25E7F3A694C0 44 9  1]
        # [*canTx0 0D4B25E7F3B1B850 45 9  1]
        parts = data.split(" ")
        arb_id = int(parts[0].strip("x"), 16)
        is_extended = parts[0].lower().endswith("x")
        try:
            data_bytes = bytes([int(x, 16) for x in parts[1:]])
        except ValueError:
            data_bytes = bytes()
        return cls(
            arb_id=arb_id,
            is_extended=is_extended,
            data=data_bytes,
        )


# Type alias for all possible event data types
# This allows us to use EventDataType in type hints and function signatures
EventDataType = (
    EventData
    | RawData
    | Radio1Data
    | Radio2Data
    | UART1Data
    | GPIOData
    | AccelData
    | ButtonData
    | IRData
    | BatteryData
    | NFCData
    | CANData
)


class EventType(enum.Enum):
    """Free-Wili Event Type."""

    Unknown = enum.auto()
    GPIO = enum.auto()
    File = enum.auto()
    Accel = enum.auto()
    Button = enum.auto()
    Battery = enum.auto()
    IR = enum.auto()
    Radio1 = enum.auto()
    Radio2 = enum.auto()
    UART1 = enum.auto()
    Audio = enum.auto()
    NFC = enum.auto()
    CANTX0 = enum.auto()
    CANRX0 = enum.auto()
    CANTX1 = enum.auto()
    CANRX1 = enum.auto()

    def __str__(self) -> str:
        return self.name

    def get_data_type(self) -> EventData:  # type: ignore[return-value]
        """Get the EventDataType class from this EventType.

        Arguments:
        ----------
            None

        Returns:
        --------
            EventDataType:
                The corresponding EventDataType class.

        Raises:
            ValueError:
                When the string does not match any known event type.
        """
        match self:
            case self.Unknown:
                return RawData  # type: ignore[return-value]
            case self.GPIO:
                return GPIOData  # type: ignore[return-value]
            case self.File:
                return RawData  # type: ignore[return-value]
            case self.Accel:
                return AccelData  # type: ignore[return-value]
            case self.Button:
                return ButtonData  # type: ignore[return-value]
            case self.IR:
                return IRData  # type: ignore[return-value]
            case self.Battery:
                return BatteryData  # type: ignore[return-value]
            case self.Radio1:
                return Radio1Data  # type: ignore[return-value]
            case self.Radio2:
                return Radio2Data  # type: ignore[return-value]
            case self.UART1:
                return UART1Data  # type: ignore[return-value]
            case self.Audio:
                return AudioData  # type: ignore[return-value]
            case self.NFC:
                return NFCData  # type: ignore[return-value]
            case self.CANTX0:
                return CANData  # type: ignore[return-value]
            case self.CANRX0:
                return CANData  # type: ignore[return-value]
            case self.CANTX1:
                return CANData  # type: ignore[return-value]
            case self.CANRX1:
                return CANData  # type: ignore[return-value]
            case _:
                return RawData  # type: ignore[return-value]

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Convert a string value to an EventType.

        Arguments:
        ----------
            value: str
                string value to convert to an enum. Case Insensitive. This is typically
                the rf_type_data field in a FreeWili Event ResponseFrame.

        Returns:
        --------
            EventType:
                FreeWili event type.

        Raises:
            ValueError:
                When invalid enum isn't matched against provided string value.
        """
        match value.lower():
            case "gpioin":
                return cls(cls.GPIO)
            case "file":
                return cls(cls.File)
            case "accel":
                return cls(cls.Accel)
            case "button":
                return cls(cls.Button)
            case "irrx":
                return cls(cls.IR)
            case "battery":
                return cls(cls.Battery)
            case "radio1":
                return cls(cls.Radio1)
            case "radio2":
                return cls(cls.Radio2)
            case "uart1":
                return cls(cls.UART1)
            case "audio":
                return cls(cls.Audio)
            case "nfc":
                return cls(cls.NFC)
            case "cantx0":
                return cls(cls.CANTX0)
            case "can0":
                return cls(cls.CANRX0)
            case "cantx1":
                return cls(cls.CANTX1)
            case "can1":
                return cls(cls.CANRX1)
            case _:
                return cls(cls.Unknown)

    @classmethod
    def from_frame(cls, frame: ResponseFrame) -> Self:
        """Convert a ResponseFrame to an EventType.

        Arguments:
        ----------
            frame: ResponseFrame
                The ResponseFrame to convert.

        Returns:
        --------
            EventType:
                The corresponding EventType.

        Raises:
            ValueError:
                When the frame does not contain a valid event type.
        """
        rf_type_data = frame.rf_type_data
        return cls.from_string(rf_type_data)


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


class FileType(enum.Enum):
    """Free-Wili File Type."""

    Unknown = enum.auto()
    Directory = enum.auto()
    File = enum.auto()

    def __str__(self) -> str:
        return self.name

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Convert a string value to a FileType.

        Arguments:
        ----------
            value: str
                string value to convert to an enum. Case Insensitive.

        Returns:
        --------
            FileType:
                FreeWili file type.

        """
        match value.lower():
            case "dir":
                return cls(cls.Directory)
            case "file":
                return cls(cls.File)
            case _:
                return cls(cls.Unknown)


@dataclass(frozen=True)
class FileSystemItem:
    """File system item representation for Free-Wili."""

    """Name of the file system item."""
    name: str
    """Type of the file system item, either File or Directory."""
    file_type: FileType
    """Size of the file in bytes, 0 for directories."""
    size: int = 0

    def __str__(self) -> str:
        return f"FileSystemItem(name={self.name}, file_type={self.file_type}, size={self.size})"


@dataclass(frozen=True)
class FileSystemContents:
    """File system representation for Free-Wili."""

    # File system current working directory
    cwd: str
    # List of files in the file system
    contents: list[FileSystemItem]

    def __str__(self) -> str:
        return f"FileSystem(cwd={self.cwd}, contents={self.contents})"
