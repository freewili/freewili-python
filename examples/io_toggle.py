"""Toggle IO on a Free-Wili."""

from freewili import FreeWili
from freewili.types import IOMenuCommand

if __name__ == "__main__":
    try:
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            print(f"Connected to {fw}")
            # Set IO 25 high
            fw.set_io(25, IOMenuCommand.High).expect("Failed to set IO high")
            # Set IO 25 Low
            fw.set_io(25, IOMenuCommand.Low).expect("Failed to set IO low")
            # Toggle IO 25 Low
            fw.set_io(25, IOMenuCommand.Toggle).expect("Failed to toggle IO")
            # PWM IO 25
            fw.set_io(25, IOMenuCommand.Pwm, 10, 50).expect("Failed to toggle IO")
            # Toggle high-speed IO
            fw.toggle_high_speed_io(True).expect("Failed to toggle high-speed IO")
            fw.toggle_high_speed_io(False).expect("Failed to toggle high-speed IO off")
    except Exception as ex:
        print(f"Error: {ex}")

    print("Done.")
