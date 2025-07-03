"""Set Board RGB on a Free-Wili."""

import time

from freewili import FreeWili

# find a FreeWili device and open it
device = FreeWili.find_first().expect("Failed to find a FreeWili")
device.open().expect("Failed to open")

# Turn the LEDs on
for led_num in range(7):
    print(device.set_board_leds(led_num, 10, 10, led_num * 2).expect("Failed to set LED"))
# Wait so we can see them
time.sleep(3)
# Turn the LEDS off
for led_num in reversed(range(7)):
    print(device.set_board_leds(led_num, 0, 0, 0).expect("Failed to set LED"))

device.close()
