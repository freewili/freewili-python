Examples
========

All code examples can be found in the examples directory of the repository.

Find all devices
-----------------

Find and display all Free-Wili devices.

.. literalinclude:: ../../examples/find_freewilis.py
   :language: python
   :linenos:

Upload files
------------

Upload files to the first Free-Wili device.

.. literalinclude:: ../../examples/upload_wasm_with_fwi.py
   :language: python
   :linenos:

Device Settings
---------------

Configure FreeWili device settings including system sounds, default configurations, and real-time clock.

.. literalinclude:: ../../examples/settings.py
   :language: python
   :linenos:

FPGA Configuration
------------------

Load FPGA configuration files on the FreeWili device.

.. literalinclude:: ../../examples/fpga.py
   :language: python
   :linenos:

Toggle IO
------------

Toggles IO on the first Free-Wili device.

.. literalinclude:: ../../examples/io_toggle.py
   :language: python
   :linenos:

Read Buttons
------------

Read buttons on the first Free-Wili device.

.. literalinclude:: ../../examples/read_buttons.py
   :language: python
   :linenos:

Set Board LEDs
--------------

Set Board LEDs on the first Free-Wili device.

.. literalinclude:: ../../examples/set_board_leds.py
   :language: python
   :linenos:

SparkFun 9DoF IMU Breakout - ISM330DHCX, MMC5983MA (Qwiic)
----------------------------------------------------------

SparkFun 9DoF IMU Breakout example over I2C.

.. literalinclude:: ../../examples/i2c_sparkfun_9dof_imu_breakout.py
   :language: python
   :linenos:

Event Handling (Console)
-------------------------

Console-based example for handling real-time events from FreeWili devices including accelerometer, button, IR, and battery events.

.. literalinclude:: ../../examples/events.py
   :language: python
   :linenos:

Event Handling (GUI)
---------------------

PySide6 GUI application for monitoring real-time FreeWili events with visual displays and controls.

.. literalinclude:: ../../examples/events_gui.py
   :language: python
   :linenos:

Audio Recording
---------------

Record audio from FreeWili and save it to a WAV file.

.. literalinclude:: ../../examples/record_audio.py
   :language: python
   :linenos:

Audio Playback - Tone
----------------------

Play audio tones on the FreeWili device.

.. literalinclude:: ../../examples/play_audio_tone.py
   :language: python
   :linenos:

Audio Playback - Number
------------------------

Play audio number announcements on the FreeWili device.

.. literalinclude:: ../../examples/play_audio_number.py
   :language: python
   :linenos:

Audio Playback - Assets
------------------------

Play audio assets/files on the FreeWili device.

.. literalinclude:: ../../examples/play_audio_assets.py
   :language: python
   :linenos:

IR Communication - Send
------------------------

Send infrared signals using the FreeWili device.

.. literalinclude:: ../../examples/send_ir.py
   :language: python
   :linenos:

IR Communication - Read
------------------------

Read and decode infrared signals using the FreeWili device.

.. literalinclude:: ../../examples/read_ir.py
   :language: python
   :linenos:

UART Communication
------------------

UART serial communication example for the FreeWili device.

.. literalinclude:: ../../examples/uart.py
   :language: python
   :linenos:

SPI Communication
-----------------

SPI read/write communication example for the FreeWili device.

.. literalinclude:: ../../examples/spi_read_write.py
   :language: python
   :linenos:

Filesystem Explorer
-------------------

Recursively explore and list the filesystem contents on both Display and Main processors of the FreeWili device.

.. literalinclude:: ../../examples/filesystem.py
   :language: python
   :linenos:

Download Files
--------------

Download files from the FreeWili device to the local filesystem with progress tracking.

.. literalinclude:: ../../examples/get_file.py
   :language: python
   :linenos:

CAN Communication
-----------------

Handle CAN and CAN FD communication events from FreeWili devices including transmit and receive on both CAN channels.

.. literalinclude:: ../../examples/can.py
   :language: python
   :linenos:

WilEye Camera
-------------

Simple example demonstrating WilEye camera commands and automatic device discovery.

.. literalinclude:: ../../examples/wileye_simple.py
   :language: python
   :linenos:
