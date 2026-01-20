"""Example script to demonstrate playing audio numbers with Free-WiLi."""

import time

from freewili import FreeWili

fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to FreeWili {fw}")
    while True:
        try:
            user_input = int(input("Enter number: "))
            fw.play_audio_number_as_speech(user_input).expect("Failed to play audio number as speech")
            time.sleep(len(str(user_input)) * 0.8)  # Give some time for the audio to play, playing is async
        except (ValueError, KeyboardInterrupt):
            print("Goodbye!")
            break
    print("Done.")
