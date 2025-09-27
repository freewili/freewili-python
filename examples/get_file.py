"""Example script to download a file from FreeWili device to local filesystem."""

import sys
import pathlib
import time

# Ensure we use the local freewili module (with our fixes) instead of any installed version
current_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from freewili import FreeWili
from freewili.fw import FreeWiliProcessorType as FwProcessor


def progress_callback(message: str) -> None:
    """Callback function to display progress during file download."""
    timestamp = time.strftime("[%H:%M:%S]")
    print(f"{timestamp} {message}")


def get_file_from_device(fw: FreeWili, source_file: str, destination_path: str, processor: FwProcessor) -> None:
    """Download a file from the FreeWili device.
    
    Arguments:
    ----------
        fw: FreeWili
            The connected FreeWili device instance.
        source_file: str
            Path to the file on the FreeWili device (e.g., "/sounds/test.wav").
        destination_path: str
            Local path where the file should be saved.
        processor: FwProcessor
            Which processor to get the file from (Main or Display).
    """
    print(f"Downloading {source_file} from {processor.name} processor...")
    
    # Ensure destination directory exists
    dest_path = pathlib.Path(destination_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get the file from the device
    result = fw.get_file(
        source_file=source_file,
        destination_path=dest_path,
        processor=processor,
        event_cb=progress_callback
    )
    
    if result.is_ok():
        print(f"✅ Success: {result.unwrap()}")
        print(f"   File saved to: {dest_path.absolute()}")
        print(f"   File size: {dest_path.stat().st_size} bytes")
    else:
        print(f"Error: {result.unwrap_err()}")


def list_available_files(fw: FreeWili, processor: FwProcessor, directory: str = "/") -> None:
    """List files available on the device for download.
    
    Arguments:
    ----------
        fw: FreeWili
            The connected FreeWili device instance.
        processor: FwProcessor
            Which processor to list files from.
        directory: str
            Directory to list (default: root directory).
    """
    print(f"\nListing files in {directory} on {processor.name} processor:")
    
    # Change to the specified directory
    change_result = fw.change_directory(directory, processor)
    if change_result.is_err():
        print(f"Failed to change to directory {directory}: {change_result.unwrap_err()}")
        return
    
    # List current directory contents
    result = fw.list_current_directory(processor)
    if result.is_err():
        print(f"Failed to list directory contents: {result.unwrap_err()}")
        return
    
    fs_contents = result.unwrap()
    print(f"📁 Current directory: {fs_contents.cwd}")
    
    # Display files that can be downloaded
    files_found = False
    for item in fs_contents.contents:
        if item.name not in ["..", "."] and item.file_type.name == "File":
            files_found = True
            print(f"  📄 {item.name} ({item.size} bytes)")
    
    if not files_found:
        print("  No files found in this directory.")


def main() -> None:
    """Main function demonstrating file download from FreeWili."""
    print("FreeWili File Download Example")
    print("=" * 40)
    print("📁 All files will be saved to: ./upload/ directory")
    
    # Find and connect to FreeWili device
    fw_result = FreeWili.find_first()
    if fw_result.is_err():
        print(f"Failed to find FreeWili device: {fw_result.unwrap_err()}")
        return
    
    try:
        with fw_result.unwrap() as fw:
            print(f"🔌 Connected to: {fw}")
            
            # Example 1: List available files on Display processor
            list_available_files(fw, FwProcessor.Display, "/")        # Root directory
            list_available_files(fw, FwProcessor.Display, "/sounds")
            list_available_files(fw, FwProcessor.Display, "/images")
            
            # Example 2: List available files on Main processor
            list_available_files(fw, FwProcessor.Main, "/")           # Root directory
            list_available_files(fw, FwProcessor.Main, "/scripts")
            list_available_files(fw, FwProcessor.Main, "/radio")
            list_available_files(fw, FwProcessor.Main, "/fpga")
            
            print(f"\n{'='*50}")
            print("File Download Examples:")
            print(f"{'='*50}")
            
            # Example 3: Download working files from your device
            working_downloads = [
                ("/settings.txt", "./upload/main_settings.txt", FwProcessor.Main, "Main processor configuration"),
                ("/settings.txt", "./upload/display_settings.txt", FwProcessor.Display, "Display processor configuration"),
                ("/testfw.bin", "./upload/testfw.bin", FwProcessor.Main, "Small test firmware binary"),
                ("/wili.jpeg", "./upload/wili.jpeg", FwProcessor.Main, "JPEG image")
            ]
            
            for source_file, dest_path, processor, description in working_downloads:
                print(f"\n🔄 Downloading {description}...")
                try:
                    get_file_from_device(
                        fw=fw,
                        source_file=source_file,
                        destination_path=dest_path,
                        processor=processor
                    )
                except Exception as e:
                    print(f" Download failed: {e}")
            
            print(f"\n{'='*50}")
            print("Additional Examples (modify with actual file names):")
            print(f"{'='*50}")
            
    except Exception as e:
        print(f"Failed to open FreeWili device: {e}")
        return
        
    print(f"\nSummary:")
    print(f" All downloaded files are saved in the ./upload/ directory")


if __name__ == "__main__":
    main()