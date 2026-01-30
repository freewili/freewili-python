"""Test code for fw_ver.py script functionality using real hardware."""

import pytest

from freewili import FreeWili
from freewili.fw_serial import FreeWiliProcessorType
from freewili.types import FreeWiliAppInfo


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_find_first() -> None:
    """Test finding first FreeWili device."""
    fw = FreeWili.find_first().expect("Failed to find FreeWili")
    assert fw is not None


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_get_app_info_main_processor() -> None:
    """Test getting app info for Main processor on real hardware."""
    with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
        result = fw.get_app_info(FreeWiliProcessorType.Main)
        assert result.is_ok(), f"Failed to get Main processor info: {result.unwrap_err() if result.is_err() else ''}"

        app_info: FreeWiliAppInfo = result.unwrap()
        assert app_info.processor_type == FreeWiliProcessorType.Main
        assert app_info.version > 0, "Version should be greater than 0"

        print(f"Main Firmware version: {app_info}")


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_get_app_info_display_processor() -> None:
    """Test getting app info for Display processor on real hardware."""
    with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
        result = fw.get_app_info(FreeWiliProcessorType.Display)
        assert result.is_ok(), f"Failed to get Display processor info: {result.unwrap_err() if result.is_err() else ''}"

        app_info = result.unwrap()
        assert app_info.processor_type == FreeWiliProcessorType.Display
        assert app_info.version > 0, "Version should be greater than 0"

        print(f"Display Firmware version: {app_info}")


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_get_both_processor_versions() -> None:
    """Test getting app info for both Main and Display processors."""
    with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
        main_result = fw.get_app_info(FreeWiliProcessorType.Main)
        display_result = fw.get_app_info(FreeWiliProcessorType.Display)

        assert main_result.is_ok(), (
            f"Failed to get Main processor info: {main_result.unwrap_err() if main_result.is_err() else ''}"
        )
        assert display_result.is_ok(), (
            f"Failed to get Display processor info: {display_result.unwrap_err() if display_result.is_err() else ''}"
        )

        main_info = main_result.unwrap()
        display_info = display_result.unwrap()

        print(f"Main Firmware version: {main_info}")
        print(f"Display Firmware version: {display_info}")

        # Verify both have valid versions
        assert main_info.version > 0
        assert display_info.version > 0


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_context_manager() -> None:
    """Test FreeWili context manager usage with real hardware."""
    fw = FreeWili.find_first().expect("Failed to find FreeWili")

    with fw:
        # Should be able to communicate while in context
        result = fw.get_app_info(FreeWiliProcessorType.Main)
        assert result.is_ok()

    # Context manager should handle cleanup


@pytest.mark.skipif("len(FreeWili.find_all()) == 0")
def test_hw_processor_type_values() -> None:
    """Test that processor type enum values work with real hardware."""
    with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
        # Test each processor type
        for proc_type in [FreeWiliProcessorType.Main, FreeWiliProcessorType.Display]:
            result = fw.get_app_info(proc_type)
            # Should get either valid info or an error, but not crash
            assert result.is_ok() or result.is_err()


def test_processor_type_enum_attributes() -> None:
    """Test FreeWiliProcessorType enum has expected values (no hardware needed)."""
    assert hasattr(FreeWiliProcessorType, "Main")
    assert hasattr(FreeWiliProcessorType, "Display")
    assert hasattr(FreeWiliProcessorType, "Unknown")


if __name__ == "__main__":
    pytest.main([__file__, "--verbose"])
