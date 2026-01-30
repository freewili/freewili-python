Development
===========

Initial setup
-------------

.. code-block:: bash
    :caption:  Update your fork with release tags
    
        cd my/fork/of/freewili-python
        git remote add upstream https://github.com/freewili/freewili-python
        git fetch upstream --tags

.. code-block:: bash
    :caption:  Initialize virtual environment
    
        pip install uv
        uv venv
        source .venv/bin/activate       # Linux
        # .\.venv\Scripts\activate.ps1  # Windows (power shell)
        uv sync
        pre-commit install

Running unit tests
------------------

.. code-block:: bash
    :caption:  Running unit tests
    
        uv run pytest


Building documentation
----------------------

.. code-block:: bash
    :caption:  Running documentation

        sphinx-autobuild doc/source/ doc/build


VSCode setup
------------
- Install recommended extensions
- Point vscode to the virtual environmenet managed by uv (.venv)
    - > Python: Select Interpreter
- Choose which cli to debug:
    - > Debug: Select and Start Debugging
- F5 starts debugging

Dependencies
------------
Installing Python 3.10+

If you don't already have Python 3.10+ installed, you can download it from the official Python website: <https://www.python.org/downloads/>. Follow the installation instructions for your operating system.

Installing VSCode
-----------------
To install VSCode, follow the instructions at <https://code.visualstudio.com/docs/setup/setup-overview>.


Installing recommended extensions in VSCode
-------------------------------------------
See https://code.visualstudio.com/docs/editor/extension-marketplace#_recommended-extensions