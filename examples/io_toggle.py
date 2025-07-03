"""Toggle IO on a Free-Wili."""

from freewili import FreeWili
from freewili.types import IOMenuCommand

# find a FreeWili device and open it
device = FreeWili.find_first().expect("Failed to find a FreeWili")
device.open().expect("Failed to open")

# Set IO 25 high
print(device.set_io(25, IOMenuCommand.High).expect("Failed to set IO high"))
# Set IO 25 Low
print(device.set_io(25, IOMenuCommand.Low).expect("Failed to set IO low"))
# Toggle IO 25 Low
print(device.set_io(25, IOMenuCommand.Toggle).expect("Failed to toggle IO"))
# PWM IO 25
print(device.set_io(25, IOMenuCommand.Pwm, 10, 50).expect("Failed to toggle IO"))

device.close()
