"""This script explores the FreeWili filesystem, listing directories and files recursively."""

from freewili import FreeWili
from freewili.fw import FreeWiliProcessorType as FwProcessor
from freewili.types import FileType


def explore_directory(
    fw: FreeWili,
    processor: FwProcessor,
    path: str = "/",
    indent: int = 0,
    max_depth: int = 3,
    visited: None | set[str] = None,
) -> None:
    """Recursively explore directories on the FreeWili filesystem."""
    if visited is None:
        visited = set()

    # Normalize the path to avoid double slashes
    path = "/" if path in ["/", "//"] else path

    # Prevent infinite recursion
    if indent > max_depth:
        print("  " * indent + f"⚠️  Max depth reached for {path}")
        return

    # Prevent visiting the same path twice
    if path in visited:
        print("  " * indent + f"🔄 Already visited {path}")
        return

    visited.add(path)

    # Change to the directory
    if path != "/":
        change_result = fw.change_directory(path, processor)
        if change_result.is_err():
            print("  " * indent + f"❌ Failed to change to {path}: {change_result.unwrap_err()}")
            return

    # List current directory contents
    result = fw.list_current_directory(processor)
    if result.is_err():
        print("  " * indent + f"❌ Failed to list directory {path}: {result.unwrap_err()}")
        return

    fs_contents = result.unwrap()

    # Calculate actual item count (excluding parent/current directory references)
    actual_items = [item for item in fs_contents.contents if item.name not in ["..", "."]]

    # Print current directory info
    prefix = "  " * indent
    # Normalize the path display to avoid double slashes
    if fs_contents.cwd == "/":
        display_path = "/"
    else:
        display_path = f"{fs_contents.cwd}/"
    print(f"{prefix}📁 {display_path} ({len(actual_items)} items)")

    # Print files only (we'll show directories when we explore them)
    for item in fs_contents.contents:
        if item.name == ".." or item.name == ".":
            continue  # Skip parent/current directory references

        if item.file_type == FileType.File:
            print(f"{prefix}  📄 {item.name} ({item.size} bytes)")

    # Recursively explore subdirectories (excluding parent directory references)
    for item in fs_contents.contents:
        if item.file_type == FileType.Directory and item.name not in ["..", "."]:
            # Build the new path, handling root directory properly
            current_dir = fs_contents.cwd if fs_contents.cwd not in ["/", "//"] else ""
            if current_dir:
                new_path = f"{current_dir}/{item.name}"
            else:
                new_path = f"/{item.name}"

            explore_directory(fw, processor, new_path, indent + 1, max_depth, visited)

            # Change back to the original directory after exploring subdirectory
            # Normalize the path to avoid double slashes
            return_path = fs_contents.cwd if fs_contents.cwd not in ["//"] else "/"
            fw.change_directory(return_path, processor)


fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to {fw}")
    print("\n=== Exploring Display Processor Filesystem ===")
    fw.change_directory("/", FwProcessor.Display).expect("Failed to change to root directory on Display processor")
    explore_directory(fw, FwProcessor.Display)

    print("\n=== Exploring Main Processor Filesystem ===")
    fw.change_directory("/", FwProcessor.Main).expect("Failed to change to root directory on Main processor")
    explore_directory(fw, FwProcessor.Main)
