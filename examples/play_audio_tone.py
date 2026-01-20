"""Example script to demonstrate playing audio tones with Free-WiLi."""

import time

from freewili import FreeWili

fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to FreeWili {fw}")
    print("type 'list' to see audio assets or 'exit' to quit.")
    while True:
        try:
            user_input = input("Enter to play audio tone [hz duration_sec amplitude]: ")
            frequency_hz, duration_sec, amplitude = map(float, user_input.split())
            frequency_hz = int(frequency_hz)  # Convert to int for frequency
            # v54 firmware: Response frame always returns failure
            fw.play_audio_tone(frequency_hz, duration_sec, amplitude)  # .expect("Failed to play audio tone")
            time.sleep(duration_sec)  # Give some time for the audio to play, playing is async
        except (ValueError, KeyboardInterrupt):
            print("Goodbye!")
            break
    print("Done.")
