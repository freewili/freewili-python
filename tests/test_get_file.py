"""Test file download functionality on a FreeWili device."""

import os
import pathlib
import tempfile
from typing import List

import pytest

from freewili import FreeWili
from freewili.fw import FreeWiliProcessorType as FwProcessor
from freewili.types import FileType


class TestGetFile:
    """Test class for file download functionality."""

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_get_file_success(self) -> None:
        """Test successful file download from FreeWili."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # First, let's find an existing file on the device to download
            test_processors = [FwProcessor.Display, FwProcessor.Main]
            test_directories = {
                FwProcessor.Display: ["/images", "/sounds"],
                FwProcessor.Main: ["/scripts", "/radio", "/fpga"],
            }

            downloaded_file = None
            source_file = None
            processor_used = None

            try:
                # Try to find an existing file to download
                for processor in test_processors:
                    for directory in test_directories[processor]:
                        fw.change_directory(directory, processor)
                        result = fw.list_current_directory(processor)
                        if result.is_ok():
                            fs_contents = result.unwrap()
                            # Find first file (not directory)
                            for item in fs_contents.contents:
                                if item.file_type == FileType.File and item.name not in ["..", "."]:
                                    source_file = f"{directory}/{item.name}"
                                    processor_used = processor
                                    break
                            if source_file:
                                break
                    if source_file:
                        break

                # If no existing file found, create a test file
                if not source_file:
                    # Create and upload a test file
                    test_content = b"Test content for get_file functionality"
                    with tempfile.NamedTemporaryFile(suffix=".fwi", delete=False) as temp_file:
                        temp_file.write(test_content)
                        temp_file.flush()

                        # Upload to device
                        upload_result = fw.send_file(
                            source_file=temp_file.name,
                            target_name="/images/test_get_file.fwi",
                            processor=FwProcessor.Display,
                        )
                        assert upload_result.is_ok(), f"Failed to upload test file: {upload_result.unwrap_err()}"

                        source_file = "/images/test_get_file.fwi"
                        processor_used = FwProcessor.Display

                        # Clean up temp upload file
                        os.unlink(temp_file.name)

                # Now test downloading
                if source_file and processor_used:
                    callback_messages: List[str] = []

                    def progress_callback(message: str) -> None:
                        callback_messages.append(message)
                        print(f"Download progress: {message}")

                    # Create destination file
                    with tempfile.NamedTemporaryFile(delete=False) as temp_dest:
                        downloaded_file = temp_dest.name

                    # Download the file
                    result = fw.get_file(
                        source_file=source_file,
                        destination_path=downloaded_file,
                        processor=processor_used,
                        event_cb=progress_callback,
                    )

                    # Verify download was successful
                    assert result.is_ok(), f"Failed to download file: {result.unwrap_err()}"

                    # Verify callback was called
                    assert len(callback_messages) > 0, "Progress callback should have been called"

                    # Verify downloaded file exists and has content
                    assert os.path.exists(downloaded_file), "Downloaded file should exist"

                    file_size = pathlib.Path(downloaded_file).stat().st_size
                    assert file_size > 0, "Downloaded file should not be empty"

                    print(f"✅ Successfully downloaded {source_file} ({file_size} bytes)")

                else:
                    pytest.skip("No files available on device for download test")

            finally:
                # Clean up downloaded file
                if downloaded_file and os.path.exists(downloaded_file):
                    os.unlink(downloaded_file)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_get_file_multiple(self) -> None:
        """Test downloading the same file multiple times."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            fw.send_file(
                "tests/assets/invalid.fwi",
                "/images/invalid.fwi",
                FwProcessor.Display,
            ).expect("Failed to upload invalid.fwi to Display")
            for i in range(50):
                try:
                    fw.get_file(
                        "/images/invalid.fwi",
                        f"invalid_{i}.fwi",
                        FwProcessor.Display,
                    ).expect(f"Failed to get invalid.fwi file {i}")
                finally:
                    file_path = f"invalid_{i}.fwi"
                    if os.path.exists(file_path):
                        os.remove(file_path)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_get_file_with_callback(self) -> None:
        """Test file download with progress callback."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            # Create a test file to ensure we have something to download
            test_content = b"A" * 1024  # 1KB of data to ensure progress callbacks
            test_filename = "callback_test.fwi"

            # Upload test file first
            with tempfile.NamedTemporaryFile(suffix=".fwi", delete=False) as temp_file:
                temp_file.write(test_content)
                temp_file.flush()
                temp_filename = temp_file.name

            # Close file before upload to avoid permission issues
            upload_result = fw.send_file(
                source_file=temp_filename, target_name=f"/images/{test_filename}", processor=FwProcessor.Display
            )
            assert upload_result.is_ok(), f"Failed to upload test file: {upload_result.unwrap_err()}"

            os.unlink(temp_filename)

            try:
                # Test download with callback
                callback_messages: List[str] = []

                def detailed_callback(message: str) -> None:
                    callback_messages.append(message)
                    print(f"Callback: {message}")

                with tempfile.NamedTemporaryFile(delete=False) as download_temp:
                    download_path = download_temp.name

                try:
                    result = fw.get_file(
                        source_file=f"/images/{test_filename}",
                        destination_path=download_path,
                        processor=FwProcessor.Display,
                        event_cb=detailed_callback,
                    )

                    assert result.is_ok(), f"Download failed: {result.unwrap_err()}"

                    # Verify callbacks were made
                    assert len(callback_messages) > 0, "No progress callbacks received"

                    # Check for expected callback message types
                    callback_text = " ".join(callback_messages).lower()
                    assert any(keyword in callback_text for keyword in ["sending", "command", "waiting", "saving"]), (
                        "Expected progress keywords not found in callbacks"
                    )

                    # Verify file was downloaded correctly
                    with open(download_path, "rb") as f:
                        downloaded_content = f.read()
                    assert downloaded_content == test_content, "Downloaded content doesn't match original"

                finally:
                    if os.path.exists(download_path):
                        os.unlink(download_path)

            finally:
                # Clean up test file from device
                try:
                    fw.remove_directory_or_file(f"/images/{test_filename}", FwProcessor.Display)
                except Exception:
                    pass  # Ignore cleanup errors

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_get_file_nonexistent(self) -> None:
        """Test downloading non-existent file returns error."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            with tempfile.NamedTemporaryFile(delete=False) as temp_dest:
                download_path = temp_dest.name

            try:
                # Try to download a file that doesn't exist
                result = fw.get_file(
                    source_file="/images/this_file_does_not_exist_12345.fwi",
                    destination_path=download_path,
                    processor=FwProcessor.Display,
                )

                # Should fail gracefully
                assert result.is_err(), "Downloading non-existent file should return an error"
                error_msg = result.unwrap_err()
                print(f"Expected error received: {error_msg}")

                # Verify the error message indicates the file doesn't exist
                assert any(
                    keyword in error_msg.lower() for keyword in ["not found", "does not exist", "error", "fail"]
                ), f"Error message should indicate file not found, got: {error_msg}"

            finally:
                # Clean up temp file if it was created
                if os.path.exists(download_path):
                    os.unlink(download_path)

    @pytest.mark.skipif("len(FreeWili.find_all()) == 0")
    def test_get_file_different_processors(self) -> None:
        """Test downloading from different processors."""
        fw = FreeWili.find_first().expect("Failed to find FreeWili")
        with fw:
            processors_to_test = [FwProcessor.Main, FwProcessor.Display]

            for processor in processors_to_test:
                print(f"\nTesting {processor.name} processor...")

                # Change to root directory
                fw.change_directory("/", processor)

                # List directory to find available directories
                result = fw.list_current_directory(processor)
                if result.is_ok():
                    fs_contents = result.unwrap()
                    print(f"  Current directory: {fs_contents.cwd}")

                    # Look for directories with potential files
                    directories_found = []
                    for item in fs_contents.contents:
                        if item.file_type.name == "Directory" and item.name not in ["..", "."]:
                            directories_found.append(item.name)

                    print(f"  Directories found: {directories_found}")

                    # This test mainly verifies we can communicate with different processors
                    # The actual file download is tested in other methods

                else:
                    print(f"  Failed to list directory on {processor.name}: {result.unwrap_err()}")


if __name__ == "__main__":
    pytest.main([__file__, "--verbose", "-s"])
