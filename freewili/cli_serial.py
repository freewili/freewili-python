"""Command line serial interface for the FreeWili library.

This module provides a command line interface to find and control FreeWili boards.
"""

import argparse
import importlib.metadata
import pathlib

import pyfwfinder as fwf
from result import Err, Ok

from freewili import FreeWili
from freewili.cli import exit_with_error, get_device
from freewili.fw import GPIO_MAP
from freewili.serial_util import FreeWiliProcessorType, FreeWiliSerial, IOMenuCommand


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
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Verbose output",
    )
    parser.add_argument(
        "-i",
        "--index",
        type=int,
        default=1,
        help="Select a specific FreeWili by index. The first FreeWili is 1.",
    )
    parser.add_argument(
        "-di",
        "--display_index",
        type=int,
        default=None,
        help="Select a specific FreeWili display processor by index. The first FreeWili is 1.",
    )
    parser.add_argument(
        "-mi",
        "--main_index",
        type=int,
        default=None,
        help="Select a specific FreeWili main processor by index. The first FreeWili is 1.",
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
        "-g",
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
        "--io",
        nargs="*",
        help=(
            "Set IO. Argument should be in the form of: <io_pin> <high/low/toggle/pwm> [pwm_freq] [pwm_duty].\n"
            "No arguments gets all IO values."
        ),
    )
    parser.add_argument(
        "-led",
        "--led",
        nargs=4,
        help="Set Board LEDs. Argument should be in the form of: <LED #> <red 0-255> <green 0-255> <blue 0-255>",
    )
    parser.add_argument(
        "-gi",
        "--gui_image",
        nargs=1,
        help="Show GUI Image. Argument should be in the form of: <image path>",
    )
    parser.add_argument(
        "-gt",
        "--gui_text",
        nargs=1,
        help="Show GUI Text. Argument should be in the form of: <text>",
    )
    parser.add_argument(
        "-rb",
        "--read_buttons",
        action="store_true",
        default=False,
        help="Read buttons.",
    )
    parser.add_argument(
        "-rd",
        "--reset_display",
        action="store_true",
        default=False,
        help="Reset the display back to the main menu.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=importlib.metadata.version("freewili")),
    )
    args = parser.parse_args()
    device_index: int = args.index - 1
    processor_type = None
    if args.main_index is not None:
        processor_type = FreeWiliProcessorType.Main
    elif args.display_index is not None:
        processor_type = FreeWiliProcessorType.Display
    devices = FreeWili.find_all()
    if args.list:

        def print_usb(index: int, name: str, usb_device: fwf.USBDevice) -> None:
            port_or_paths = ""
            if usb_device.port:
                port_or_paths = usb_device.port
            elif usb_device.paths:
                port_or_paths = " ".join(usb_device.paths)
            if port_or_paths:
                print(f"\t{index}. {name}: {usb_device.name}: {port_or_paths}")
            else:
                print(f"\t{index}. {name}: {usb_device.kind.name}: {usb_device.name} {usb_device.serial}")

        def print_verbose(usb_device: fwf.USBDevice, serial: FreeWiliSerial | None = None) -> None:
            if not args.verbose:
                return
            print(f"\t\tName: {usb_device.name} Serial: {usb_device.serial}")
            print(f"\t\tVID: 0x{usb_device.vid:04X} PID: 0x{usb_device.pid:04X}")
            print(f"\t\tUSB Location: {usb_device.location}")
            print(f"\t\tKind: {usb_device.kind.name}")
            if usb_device.port:
                print(f"\t\tSerial Port: {usb_device.port}")
            if usb_device.paths:
                print(f"\t\tPaths: {' '.join(usb_device.paths)}")
            if serial:
                match serial.get_app_info():
                    case Ok(app_info):
                        print(f"\t\tApp Info: {app_info.processor_type} v{app_info.version}")
                    case Err(msg):
                        print(f"\t\tApp Info: {msg}")

        print(f"Found {len(devices)} FreeWili(s)")
        for i, free_wili in enumerate(devices, start=1):
            try:
                free_wili.stay_open = True
                print(f"{i}. {free_wili}")
                if free_wili.main:
                    print_usb(1, "Main", free_wili.main)
                    print_verbose(free_wili.main, free_wili.main_serial)
                if free_wili.display:
                    print_usb(2, "Display", free_wili.display)
                    print_verbose(free_wili.display, free_wili.display_serial)
                if free_wili.ftdi:
                    print_usb(3, "FPGA", free_wili.ftdi)
                    print_verbose(free_wili.ftdi)
                if free_wili.esp32:
                    print_usb(4, "ESP32", free_wili.esp32)
                    print_verbose(free_wili.esp32)
            finally:
                free_wili.close()
    if args.send_file:

        def send_file_callback(msg: str) -> None:
            if args.verbose:
                print(msg)

        match get_device(device_index, devices):
            case Ok(device):
                file_name = None
                if args.file_name:
                    file_name = args.file_name[0]
                match device.send_file(args.send_file[0], file_name, processor_type, send_file_callback):
                    case Ok(msg):
                        print(f"Success: {msg}")
                    case Err(msg):
                        exit_with_error(msg)
                    case _:
                        exit_with_error("Missing case statement")
            case Err(msg):
                exit_with_error(msg)
    if args.get_file:

        def get_file_callback(msg: str) -> None:
            if args.verbose:
                print(msg)

        match get_device(device_index, devices):
            case Ok(device):
                match device.get_file(args.get_file[0], args.get_file[1], processor_type, get_file_callback):
                    case Ok(msg):
                        print(f"Success: {msg}")
                    case Err(msg):
                        exit_with_error(msg)
                    case _:
                        exit_with_error("Missing case statement")
            case Err(msg):
                exit_with_error(msg)
    if args.run_script is not None:
        match get_device(device_index, devices):
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
    if args.io is not None:
        io_args_length = len(args.io)
        if io_args_length == 0:
            match get_device(device_index, devices):
                case Ok(device):
                    print("Getting IO pin values...")
                    match device.get_io():
                        case Ok(values):
                            for io_num, io_name in GPIO_MAP.items():
                                print(f"{io_name}: {values[io_num]}")
                        case Err(msg):
                            exit_with_error(msg)
                case Err(msg):
                    exit_with_error(msg)
        else:
            io_pin: int = int(args.io[0])
            menu_cmd: IOMenuCommand = IOMenuCommand.from_string(args.io[1].lower())
            pwm_freq_hz = None
            pwm_duty_cycle = None
            if menu_cmd is IOMenuCommand.Pwm:
                io_args_length = len(args.io)
                if io_args_length < 4:
                    exit_with_error(f"Expected 4 parameters to -io, got {io_args_length}")
                pwm_freq_hz = int(args.io[2])
                pwm_duty_cycle = int(args.io[3])
            match get_device(device_index, devices):
                case Ok(device):
                    print(f"Setting IO pin {io_pin} {menu_cmd.name} ", end="")
                    if io_args_length >= 4:
                        print(f"PWM Frequency: {pwm_freq_hz}Hz {pwm_duty_cycle}%", end="")
                    print()
                    match device.set_io(io_pin, menu_cmd, pwm_freq_hz, pwm_duty_cycle):
                        case Ok(msg):
                            print(f"Successfully configured pin {io_pin} {menu_cmd.name}: {msg}")
                        case Err(msg):
                            exit_with_error("Failed to configure IO pin: {msg}")
                case Err(msg):
                    exit_with_error(msg)
    if args.led:
        led_num = args.led[0]
        red = args.led[1]
        green = args.led[2]
        blue = args.led[3]
        match get_device(device_index, devices):
            case Ok(device):
                print(f"Setting LED {led_num} to RGB: {red}, {green}, {blue}...")
                match device.set_board_leds(led_num, red, green, blue):
                    case Ok(msg):
                        print(f"Successfully set LED {led_num}: {msg}")
                    case Err(msg):
                        exit_with_error(msg)
                    case _:
                        raise RuntimeError("Missing case statement")
            case Err(msg):
                exit_with_error(msg)
    if args.gui_image:
        value = args.gui_image[0]
        match get_device(device_index, devices):
            case Ok(device):
                print(f"Showing Image {value}...")
                match device.show_gui_image(value):
                    case Ok(msg):
                        print(f"Successfully showing {value}: {msg}")
                    case Err(msg):
                        exit_with_error(f"Failed to show Image {msg}")
            case Err(msg):
                exit_with_error(msg)
    if args.gui_text:
        value = args.gui_text[0]
        match get_device(device_index, devices):
            case Ok(device):
                print(f"Showing text {value}...")
                match device.show_text_display(value):
                    case Ok(msg):
                        print(f"Successfully showing {value}: {msg}")
                    case Err(msg):
                        exit_with_error(f"Failed to show text {msg}")
            case Err(msg):
                exit_with_error(msg)
    if args.read_buttons:
        match get_device(device_index, devices):
            case Ok(device):
                print("Getting button values...")
                match device.read_all_buttons():
                    case Ok(buttons):
                        for button_color, button_state in buttons.items():
                            msg = f"\N{WHITE HEAVY CHECK MARK} {button_color.name} Pressed"
                            if button_state == 0:
                                msg = f"\N{CROSS MARK} {button_color.name} Released"
                            print(msg)
                    case Err(msg):
                        exit_with_error(f"Failed to get button values {msg}")
            case Err(msg):
                exit_with_error(msg)
    if args.reset_display:
        match get_device(device_index, devices):
            case Ok(device):
                print("Resetting display...")
                match device.reset_display():
                    case Ok(msg):
                        print(f"Successfully reset display: {msg}")
                    case Err(msg):
                        exit_with_error(f"Failed to reset display {msg}")
                    case Err(msg):
                        exit_with_error(msg)
            case Err(msg):
                exit_with_error(msg)


if __name__ == "__main__":
    main()
