# noqa
from .fw import FreeWili  # noqa
from .serialport import TRACE, configure_logging, enable_trace_logging  # noqa

# Configure logging automatically when freewili package is imported
configure_logging()
