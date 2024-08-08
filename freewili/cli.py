"""Command line interface for the FreeWili library.

This module provides a command line interface to find and control FreeWili boards.
"""

import argparse
import importlib.metadata
import pathlib
import sys

from result import Err, Ok, Result

from freewili import image, serial


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
        "-s",
        "--send_file",
        nargs=1,
        help="send a file to the FreeWili. Argument should be in the form of: <source_file>",
    )
    parser.add_argument(
        "-fn",
        "--file_name",
        nargs=1,
        help="Set the name of the file in the FreeWili. Argument should be in the form of: <file_name>",
    )
    parser.add_argument(
        "-u",
        "--get_file",
        nargs=2,
        help="Get a file from the FreeWili. Argument should be in the form of: <source_file> <target_name>",
    )
    parser.add_argument(
        "-w",
        "--run_script",
        nargs="?",
        const=False,
        help="Run a script on the FreeWili. If no argument is provided, -fn will be used.",
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
    if args.send_file:
        match get_device(device_index):
            case Ok(device):
                if args.file_name:
                    file_name = args.file_name[0]
                else:
                    file_name = "/scripts/" + pathlib.Path(args.send_file[0]).name
                print(device.send_file(args.send_file[0], file_name).unwrap())
            case Err(msg):
                exit_with_error(msg)
    if args.get_file:
        match get_device(device_index):
            case Ok(device):
                data = device.get_file(args.get_file[0]).unwrap()
                with open(args.get_file[1], "w+b") as f:
                    f.write(data)
            case Err(msg):
                exit_with_error(msg)
    if args.run_script is not None:
        match get_device(device_index):
            case Ok(device):
                if args.run_script:
                    script_name = args.run_script
                elif args.file_name:
                    script_name = args.file_name[0]
                elif args.send_file:
                    script_name = pathlib.Path(args.send_file[0]).name
                else:
                    raise ValueError("No script or file name provided")
                print(device.run_script(script_name).unwrap())
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


def convert() -> None:
    """A command line interface to convert a jpg or png image to a fwi file.

    Parameters:
    ----------
        None

    Returns:
    -------
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to a JPG or PNG image to be converted",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output filename for the fwi file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=importlib.metadata.version("freewili")),
    )
    args = parser.parse_args()
    match image.convert(args.input, args.output):
        case Ok(msg):
            print(msg)
        case Err(msg):
            exit_with_error(msg)
