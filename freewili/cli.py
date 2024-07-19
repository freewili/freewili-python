"""Command line interface for the FreeWili library.

This module provides a command line interface to find and control FreeWili boards.
"""

import argparse
import importlib.metadata
import sys

from result import Err, Ok, Result

from freewili import serial


def exit_with_error(msg: str, exit_code: int = 1) -> None:
    """A function that prints an error message to the stderr and exits the program with a specified exit code.

    Parameters:
    ----------
        msg: str
            The error message to be printed.
        exit_code: int, optional
            The exit code to be used when exiting the program, defaults to 1.

    Returns:
    -------
        None
    """
    print(msg, file=sys.stderr)
    sys.exit(exit_code)


def get_device(index: int) -> Result[serial.FreeWiliSerial, str]:
    """Get a FreeWiliSerial by index.

    Parameters:
    ----------
        index: int
            The index to be checked.

    Returns:
    -------
        Result[serial.FreeWiliSerial, str]:
            The FreeWiliSerial if the index is valid, otherwise an error message.
    """
    devices = serial.find_all()
    if index >= len(devices):
        return Err(f"Index {index} is out of range. There are only {len(devices)} devices.")
    return Ok(devices[index])


def main() -> None:
    """A command line interface to list and control FreeWili boards.

    Parameters:
    ----------
        None

    Returns:
    -------
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        default=False,
        help="List all FreeWili connected to the computer.",
    )
    parser.add_argument(
        "-i",
        "--index",
        type=int,
        default=1,
        help="Select a specific FreeWili by index. The first FreeWili is 1.",
    )
    parser.add_argument(
        "-d",
        "--download_file",
        nargs=2,
        help="Download a file to the FreeWili. Argument should be in the form of: <source_file> <target_name>",
    )
    parser.add_argument(
        "-io",
        "--set_io",
        nargs=2,
        help="Toggle IO pin to high. Argument should be in the form of: <io_pin> <high/low>",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=importlib.metadata.version("freewili")),
    )
    args = parser.parse_args()
    device_index: int = args.index - 1
    if args.list:
        devices = serial.find_all()
        print(f"Found {len(devices)} FreeWili(s)")
        for i, free_wili in enumerate(devices, start=1):
            print(f"\t{i}. {free_wili}")
    if args.download_file:
        match get_device(device_index):
            case Ok(device):
                device.download_file(*args.download_file)
            case Err(msg):
                exit_with_error(msg)
    if args.set_io:
        io_pin: int = int(args.set_io[0])
        is_high: bool = args.set_io[1].upper() == "HIGH"
        match get_device(device_index):
            case Ok(device):
                print("Setting IO pin", io_pin, "to", "high" if is_high else "low")
                print(device.set_io(io_pin, is_high).unwrap_or("Failed to set IO pin"))
            case Err(msg):
                exit_with_error(msg)
