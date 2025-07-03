"""Read buttons on a Free-Wili."""

from freewili import FreeWili

# find a FreeWili device and open it
device = FreeWili.find_first().expect("Failed to find a FreeWili")
device.open().expect("Failed to open")

# Read the buttons and print on change
print("Reading buttons...")
last_button_read = device.read_all_buttons().expect("Failed to read buttons")

keyboard_interrupt_requested = False
while not keyboard_interrupt_requested:
    try:
        # Read the buttons
        buttons = device.read_all_buttons().expect("Failed to read buttons")
        for button_color, button_state in buttons.items():
            # Check if the button state has changed
            last_button_state = last_button_read[button_color]
            if last_button_state == button_state:
                continue
            # Print the button change
            msg = "Pressed \N{WHITE HEAVY CHECK MARK}"
            if button_state == 0:
                msg = "Released \N{CROSS MARK}"
            print(f"{button_color.name} {msg}")
        # Save the button state for the next loop
        last_button_read = buttons
    except KeyboardInterrupt:
        keyboard_interrupt_requested = True

device.close()
