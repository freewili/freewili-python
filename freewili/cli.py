"""Command line interface for the FreeWili library.

This module provides a command line interface to find and control FreeWili boards.
"""

import argparse
import importlib.metadata
import sys

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
        default=True,
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
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=importlib.metadata.version("freewili")),
    )
    args = parser.parse_args()
    if args.list:
        devices = serial.find_all()
        print(f"Found {len(devices)} FreeWili(s)")
        for i, free_wili in enumerate(devices, start=1):
            print(f"\t{i}. {free_wili}")
    if args.download_file:
        if not args.index:
            raise ValueError("You must specify the index of the FreeWili.")
        devices = serial.find_all()
        if args.index > len(devices):
            exit_with_error(f"Index {args.index} is out of range. There are only {len(devices)} devices.")
        devices[args.index - 1].download_file(*args.download_file)
