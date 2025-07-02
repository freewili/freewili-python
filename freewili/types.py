"""Common data types and constants."""

import enum


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
