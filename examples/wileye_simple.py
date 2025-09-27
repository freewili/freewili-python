"""
Simple WilEye Camera Example

A basic example showing how to use the WilEye camera commands
with the FreeWili Python library using automatic device discovery.
"""

import sys
import pathlib
import time
import result

# Ensure we use the local freewili module
current_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from freewili import FreeWili


def main():
    print("FreeWili WilEye Camera - Simple Example")
    print("="*40)
    
    print("Searching for FreeWili devices...")
    
    # Find FreeWili device automatically
    try:
        fw_device = FreeWili.find_first().expect("No FreeWili devices found")
        print(f"Found FreeWili device: {fw_device}")
    except result.UnwrapError as ex:
        print(f"Error: {ex}")
        print("\nMake sure your FreeWili device is:")
        print("1. Connected via USB")
        print("2. Powered on")
        print("3. Recognized by your system")
        return
    
    # Use the found device's serial interface
    fw = fw_device.main_serial  # Use main processor serial interface
    
    try:
        # Open connection
        result = fw.open()
        if result.is_err():
            print(f"Failed to connect: {result.unwrap_err()}")
            return
        
        print("Connected successfully!")
        
        # Example 1: Take a picture
        print("\n1. Taking a picture...")
        result = fw.wileye_take_picture(0, "example_photo.jpg")
        if result.is_ok():
            print("Picture taken successfully!")
        else:
            print(f"Failed to take picture: {result.unwrap_err()}")
        
        # Example 2: Set camera brightness
        print("\n2. Setting camera brightness to 75...")
        result = fw.wileye_set_brightness(75)
        if result.is_ok():
            print("Brightness set successfully!")
        else:
            print(f"Failed to set brightness: {result.unwrap_err()}")
        
        # Example 3: Set camera contrast
        print("\n3. Setting camera contrast to 60...")
        result = fw.wileye_set_contrast(60)
        if result.is_ok():
            print("Contrast set successfully!")
        else:
            print(f"Failed to set contrast: {result.unwrap_err()}")
        
        # Example 4: Enable flash
        print("\n4. Enabling camera flash...")
        result = fw.wileye_set_flash_enabled(True)
        if result.is_ok():
            print("Flash enabled successfully!")
        else:
            print(f"Failed to enable flash: {result.unwrap_err()}")
        
        # Example 5: Set resolution
        print("\n5. Setting camera resolution to high (index 2)...")
        result = fw.wileye_set_resolution(2)
        if result.is_ok():
            print("Resolution set successfully!")
        else:
            print(f"Failed to set resolution: {result.unwrap_err()}")
        
        # Example 6: Set zoom level
        print("\n6. Setting zoom level to 2x...")
        result = fw.wileye_set_zoom_level(2)
        if result.is_ok():
            print("Zoom level set successfully!")
        else:
            print(f"Failed to set zoom level: {result.unwrap_err()}")
        
        # Example 7: Take another picture with new settings
        print("\n7. Taking another picture with new settings...")
        result = fw.wileye_take_picture(0, "example_photo_2.jpg")
        if result.is_ok():
            print("Second picture taken successfully!")
        else:
            print(f"Failed to take second picture: {result.unwrap_err()}")
        
        # Example 8: Start video recording
        print("\n8. Starting video recording...")
        result = fw.wileye_start_recording_video(0, "example_video.mp4")
        if result.is_ok():
            print("Video recording started! Recording for 3 seconds...")
            time.sleep(3)  # Record for 3 seconds
            
            # Example 9: Stop video recording
            print("\n9. Stopping video recording...")
            result = fw.wileye_stop_recording_video()
            if result.is_ok():
                print("Video recording stopped successfully!")
            else:
                print(f"Failed to stop video recording: {result.unwrap_err()}")
        else:
            print(f"Failed to start video recording: {result.unwrap_err()}")
        
        # Example 10: Disable flash
        print("\n10. Disabling camera flash...")
        result = fw.wileye_set_flash_enabled(False)
        if result.is_ok():
            print("Flash disabled successfully!")
        else:
            print(f"Failed to disable flash: {result.unwrap_err()}")
        
        print("\nAll WilEye camera examples completed!")
        print("Check your FreeWili device storage for the captured files.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close connection
        fw.close()
        print("Disconnected from FreeWili device")


if __name__ == "__main__":
    main()