![](https://github.com/freewili/freewili-python/raw/master/logo.png)
# FreeWili

FreeWili is a Python library for controlling and communicating with FreeWili boards.

## Installation

You can install fwi-flash using pip:
```
pip install freewili
```

## Usage

```
fwi-flash --help   
usage: fwi-flash [-h] [-l] [-i INDEX] [-d DOWNLOAD_FILE DOWNLOAD_FILE] [--version]

options:
  -h, --help            show this help message and exit
  -l, --list            List all FreeWili connected to the computer.
  -i INDEX, --index INDEX
                        Select a specific FreeWili by index. The first FreeWili is 1.
  -d DOWNLOAD_FILE DOWNLOAD_FILE, --download_file DOWNLOAD_FILE DOWNLOAD_FILE
                        Download a file to the FreeWili. Argument should be in the form of: <source_file> <target_name>
  --version             show program's version number and exit
```

## Development

```
poetry self add "poetry-dynamic-versioning[plugin]"
poetry install
poetry run fwi-flash
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
