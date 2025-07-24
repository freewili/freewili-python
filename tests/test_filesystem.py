"""Test Filesystem functionality on a FreeWili."""

import pytest

from freewili import FreeWili
from freewili.fw import FreeWiliProcessorType as FwProcessor


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_file_creation() -> None:
    """Test file creation on a FreeWili."""
    with FreeWili.find_first().expect("Failed to open") as fw:
        for processor in (FwProcessor.Main, FwProcessor.Display):
            fw.format_filesystem(processor).expect("Failed to format filesystem")
            fw.create_directory("test_dir", processor).expect("Failed to create directory")
            fw.change_directory("test_dir", processor).expect("Failed to change directory")
            fw.create_blank_file("test_file.txt", processor).expect("Failed to create file")
            fw.move_directory_or_file("test_file.txt", "test_file_moved.txt", processor).expect("Failed to move file")
            fw.remove_directory_or_file("test_file_moved.txt", processor).expect("Failed to remove file")
            fw.change_directory("/", processor).expect("Failed to change directory")
            fw.remove_directory_or_file("test_dir", processor).expect("Failed to remove file")


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--verbose",
        ]
    )
