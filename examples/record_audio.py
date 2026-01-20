"""Example script to record audio from FreeWili and save it to a WAV file."""

import struct
import time
import wave

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import AudioData, EventType

audio_data = []


def event_handler(event_type: EventType, frame: ResponseFrame, data: AudioData) -> None:
    """Handle events from FreeWili."""
    if event_type != EventType.Audio:
        return
    # print(f"Audio Event: {data.data}")
    audio_data.append(data.data)


fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw, wave.open("test.wav", "wb") as wav_file:
    print(f"Connected to {fw}")
    wav_file.setnchannels(1)  # Mono
    wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
    wav_file.setframerate(8000)  # 4kHz sample rate

    fw.set_event_callback(event_handler)
    fw.enable_audio_events(True).expect("Failed to enable audio events")
    start_time = time.time()
    print("Listening for audio events... Press Ctrl+C to stop recording...")
    while True:
        try:
            fw.process_events()
            # Clear the first 2 seconds of audio data to avoid initial noise
            if time.time() - start_time < 2.0:
                audio_data.clear()
            if audio_data:
                # Write the audio data to the WAV file
                for data in audio_data:
                    print(f"\tWriting audio data: {data!r}" + " " * 30, end="\r")
                    # Convert data to bytes (little-endian 16-bit signed)
                    audio_bytes = b"".join(struct.pack("<h", sample) for sample in data)
                    wav_file.writeframes(audio_bytes)
                audio_data.clear()  # Clear the list after writing
        except KeyboardInterrupt:
            print("\nStopping audio recording...")
            break
    # Disable audio events before exiting
    print("Disabling audio events...")
    fw.enable_audio_events(False).expect("Failed to disable audio events")
    print(f"Audio saved to {wav_file._file.name}")  # type:ignore
print("Done.")
