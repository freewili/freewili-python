![](https://github.com/freewili/freewili-python/raw/master/logo.png)
# FreeWili

FreeWili is a Python library for controlling and communicating with FreeWili boards.

## Installation

You can install freewili using pip by running the following command:
```
pip install freewili
```
## Python script example

### Toggle LED 25:
```python

import time
import freewili

devices = freewili.find_all()
device = devices[0]

led_state: bool = True
device.stay_open = True
for _ in range(100):
    device.set_io(25, led_state)
    led_state ^= True
    time.sleep(0.1)
```

### Poll I2C:
```python

import freewili

devices = freewili.find_all()
device = devices[0]
print(device.poll_i2c())
```

```bash
Ok([1, 2])
```

## fwi-serial command line usage

```
usage: fwi-serial [-h] [-l] [-i INDEX] [-s SEND_FILE] [-fn FILE_NAME] [-u GET_FILE GET_FILE] [-w [RUN_SCRIPT]] [-io SET_IO SET_IO] [--version]

options:
  -h, --help            show this help message and exit
  -l, --list            List all FreeWili connected to the computer.
  -i INDEX, --index INDEX
                        Select a specific FreeWili by index. The first FreeWili is 1.
  -s SEND_FILE, --send_file SEND_FILE
                        send a file to the FreeWili. Argument should be in the form of: <source_file>
  -fn FILE_NAME, --file_name FILE_NAME
                        Set the name of the file in the FreeWili. Argument should be in the form of: <file_name>
  -u GET_FILE GET_FILE, --get_file GET_FILE GET_FILE
                        Get a file from the FreeWili. Argument should be in the form of: <source_file> <target_name>
  -w [RUN_SCRIPT], --run_script [RUN_SCRIPT]
                        Run a script on the FreeWili. If no argument is provided, -fn will be used.
  -io SET_IO SET_IO, --set_io SET_IO SET_IO
                        Toggle IO pin to high. Argument should be in the form of: <io_pin> <high/low>
  --version             show program's version number and exit
```

### Send file from host to freewili:

```bash
$ fwi-serial -d /path/to/bin.wasm /scripts/bin.wasm
```

### Run script on the freewili:

```bash
$ fwi-serial -w bin.wasm
```

### Set IO on the freewili:

```bash
$ fwi-serial -io 25 high
```

## Development

```
pip install poetry
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
