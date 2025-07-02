"""Common data types and constants."""

import enum
import sys

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
