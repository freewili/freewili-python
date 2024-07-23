![](https://github.com/freewili/freewili-python/raw/master/logo.png)
# FreeWili

FreeWili is a Python library for controlling and communicating with FreeWili boards.

## Installation

You can install fwi-flash using pip:
```
pip install freewili
```
## Python script example

```python

import time
import freewili.serial

devices = freewili.serial.find_all()
device = devices[0]

led_state: bool = True
device.stay_open = True
for _ in range(100):
    device.set_io(25, led_state)
    led_state ^= True
    time.sleep(0.1)


## fw-serial Usage

```
usage: fwi-serial [-h] [-l] [-i INDEX] [-d DOWNLOAD_FILE DOWNLOAD_FILE] [-io SET_IO SET_IO] [--version]

options:
  -h, --help            show this help message and exit
  -l, --list            List all FreeWili connected to the computer.
  -i INDEX, --index INDEX
                        Select a specific FreeWili by index. The first FreeWili is 1.
  -d DOWNLOAD_FILE DOWNLOAD_FILE, --download_file DOWNLOAD_FILE DOWNLOAD_FILE
                        Download a file to the FreeWili. Argument should be in the form of: <source_file>
                        <target_name>
  -io SET_IO SET_IO, --set_io SET_IO SET_IO
                        Toggle IO pin to high. Argument should be in the form of: <io_pin> <high/low>
  --version             show program's version number and exit
```

## Development

```
poetry self add "poetry-dynamic-versioning[plugin]"
poetry install
poetry run fwi-serial --help

pre-commit install
```

### Dependencies
#### Installing Python 3.11+

If you don't already have Python 3.11+ installed, you can download it from the official Python website: <https://www.python.org/downloads/>. Follow the installation instructions for your operating system.

#### Installing Poetry

Poetry is a package manager for Python that makes it easy to install and manage the dependencies needed for FreeWili. To install Poetry, follow the instructions at <https://python-poetry.org/docs/#installation>.

#### Installing VSCode

To install VSCode, follow the instructions at <https://code.visualstudio.com/docs/setup/setup-overview>.


#### Installing recommended extensions in VSCode

See https://code.visualstudio.com/docs/editor/extension-marketplace#_recommended-extensions



## License
FreeWili is licensed under the [MIT License](https://opensource.org/licenses/MIT).
