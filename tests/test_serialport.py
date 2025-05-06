"""Test SerialPort Module."""

import time
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from freewili.serialport import SerialPort  # Adjust this import as needed


class TestSerialPort(unittest.TestCase):
    """Test Serial Port Class."""

    @patch("freewili.serialport.Serial")  # Patch Serial from pyserial
    def test_send_queue_get_called(self, mock_serial_class: Any) -> None:
        """Test send queue."""
        # Create a mock Serial instance
        mock_serial_instance = MagicMock()
        mock_serial_instance.in_waiting = 0
        mock_serial_class.return_value = mock_serial_instance
        mock_serial_instance.write.return_value = len(b"test\n")

        # Create the SerialReader instance and start the thread
        serial_port = SerialPort(port="COM1")

        # Send data to the thread
        test_data = "test"
        serial_port.send(test_data)

        # Give the thread time to pick up from the queue
        time.sleep(1)

        # Close the thread gracefully
        serial_port.close()

        # Check that write() was called with the correct data
        expected_data = b"test\n"
        mock_serial_instance.write.assert_called_with(expected_data)

        # Optionally check send_queue is empty now
        self.assertTrue(serial_port.send_queue.empty())


if __name__ == "__main__":
    unittest.main()
