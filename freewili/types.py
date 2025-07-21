"""Common data types and constants."""

import enum
import sys
from dataclasses import dataclass

from freewili.framing import ResponseFrame

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class FreeWiliProcessorType(enum.Enum):
    """Processor type of the Free-Wili."""

    Main = enum.auto()
    Display = enum.auto()
    FTDI = enum.auto()
    ESP32 = enum.auto()
    Unknown = enum.auto()

    def __str__(self) -> str:
        return self.name


class ButtonColor(enum.Enum):
    """Free-Wili Physical Button Color."""

    Unknown = enum.auto()
    White = enum.auto()
    Yellow = enum.auto()
    Green = enum.auto()
    Blue = enum.auto()
    Red = enum.auto()


class EventDataType(object):
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
class AccelData(EventDataType):
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
class ButtonData(EventDataType):
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
class IRData(EventDataType):
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
class RawData(EventDataType):
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
class BatteryData(EventDataType):
    """Battery event data from Free-Wili Display."""

    vbus: float
    vsys: float
    ichg: float
    charging: bool
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
        ichg = float(parts[2])
        if vbus < 1000 and vsys < 1000 and ichg < 1000:
            # v54 firmware looks like its math is off, so if everything is less than 1000, multiply by 10
            vbus *= 10.0
            vsys *= 10.0
            ichg *= 10.0
        return cls(
            vbus=vbus,
            vsys=vsys,
            ichg=ichg,
            charging=bool(int(parts[3])),
            charge_complete=bool(int(parts[4])),
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

    def __str__(self) -> str:
        return self.name

    def get_data_type(self) -> EventDataType:  # type: ignore[return-value]
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
            case "gpio":
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
