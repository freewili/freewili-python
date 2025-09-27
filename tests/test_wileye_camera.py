"""Unit tests for WilEye camera commands in FreeWili."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pathlib
from result import Ok, Err

from freewili.fw_serial import FreeWiliSerial


class TestWilEyeCamera(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.mock_serial_port = Mock()
        self.fw_serial = FreeWiliSerial("COM1")
        self.fw_serial.serial_port = self.mock_serial_port
        self.fw_serial._is_connected = True

    def test_wileye_take_picture_success(self):
        """Test successful picture capture."""
        # Mock successful response
        with patch.object(self.fw_serial, '_empty_all') as mock_empty, \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Picture saved")):
            
            result = self.fw_serial.wileye_take_picture(0, "test.jpg")
            
            # Verify _empty_all was called
            mock_empty.assert_called_once()
            
            # Verify command was sent correctly
            self.mock_serial_port.send.assert_called_with("e\\c\\t 0 test.jpg")
            
            # Verify result
            self.assertTrue(result.is_ok())
            self.assertEqual(result.unwrap(), "Picture saved")

    def test_wileye_take_picture_failure(self):
        """Test picture capture failure."""
        # Mock error response
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Err("Camera error")):
            
            result = self.fw_serial.wileye_take_picture(1, "photo.jpg")
            
            # Verify command was sent
            self.mock_serial_port.send.assert_called_with("e\\c\\t 1 photo.jpg")
            
            # Verify error result
            self.assertTrue(result.is_err())
            self.assertEqual(result.unwrap_err(), "Camera error")

    def test_wileye_start_recording_success(self):
        """Test successful video recording start."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Recording started")):
            
            result = self.fw_serial.wileye_start_recording_video(0, "video.mp4")
            
            # Verify command
            self.mock_serial_port.send.assert_called_with("e\\c\\v 0 video.mp4")
            
            # Verify success
            self.assertTrue(result.is_ok())
            self.assertEqual(result.unwrap(), "Recording started")

    def test_wileye_stop_recording_success(self):
        """Test successful video recording stop."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Recording stopped")):
            
            result = self.fw_serial.wileye_stop_recording_video()
            
            # Verify command
            self.mock_serial_port.send.assert_called_with("e\\c\\s")
            
            # Verify success
            self.assertTrue(result.is_ok())
            self.assertEqual(result.unwrap(), "Recording stopped")

    def test_wileye_set_contrast_valid_range(self):
        """Test setting contrast with valid values."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Contrast set")):
            
            # Test minimum value
            result = self.fw_serial.wileye_set_contrast(0)
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\c 0\n")
            
            # Test middle value
            result = self.fw_serial.wileye_set_contrast(50)
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\c 50\n")
            
            # Test maximum value
            result = self.fw_serial.wileye_set_contrast(100)
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\c 100\n")

    def test_wileye_set_saturation_valid_range(self):
        """Test setting saturation with valid values."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Saturation set")):
            
            result = self.fw_serial.wileye_set_saturation(75)
            
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\i 75\n")

    def test_wileye_set_brightness_valid_range(self):
        """Test setting brightness with valid values."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Brightness set")):
            
            result = self.fw_serial.wileye_set_brightness(60)
            
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\b 60\n")

    def test_wileye_set_hue_valid_range(self):
        """Test setting hue with valid values."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Hue set")):
            
            # Test various hue values
            test_values = [0, 90, 180, 270, 360]
            for hue_val in test_values:
                result = self.fw_serial.wileye_set_hue(hue_val)
                self.assertTrue(result.is_ok())
                self.mock_serial_port.send.assert_called_with(f"e\\c\\u {hue_val}\n")

    def test_wileye_set_flash_enabled_true(self):
        """Test enabling flash."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Flash enabled")):
            
            result = self.fw_serial.wileye_set_flash_enabled(True)
            
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\l 1\n")

    def test_wileye_set_flash_enabled_false(self):
        """Test disabling flash."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Flash disabled")):
            
            result = self.fw_serial.wileye_set_flash_enabled(False)
            
            self.assertTrue(result.is_ok())
            self.mock_serial_port.send.assert_called_with("e\\c\\l 0\n")

    def test_wileye_set_zoom_level_various_values(self):
        """Test setting zoom level with various values."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Zoom level set")):
            
            # Test different zoom levels
            zoom_levels = [1, 2, 4, 8, 16]
            for zoom in zoom_levels:
                result = self.fw_serial.wileye_set_zoom_level(zoom)
                self.assertTrue(result.is_ok())
                self.mock_serial_port.send.assert_called_with(f"e\\c\\m {zoom}")

    def test_wileye_set_resolution_various_indices(self):
        """Test setting resolution with various indices."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("Resolution set")):
            
            # Test different resolution indices
            resolutions = [0, 1, 2, 3, 4]  # Common resolution indices
            for res_idx in resolutions:
                result = self.fw_serial.wileye_set_resolution(res_idx)
                self.assertTrue(result.is_ok())
                self.mock_serial_port.send.assert_called_with(f"e\\c\\y {res_idx}\n")

    def test_wileye_commands_clear_queues(self):
        """Test that WilEye commands clear all queues before execution."""
        with patch.object(self.fw_serial, '_empty_all') as mock_empty, \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("OK")):
            
            # Test that _empty_all is called for each command
            self.fw_serial.wileye_take_picture(0, "test.jpg")
            mock_empty.assert_called()
            
            self.fw_serial.wileye_set_contrast(50)
            self.assertEqual(mock_empty.call_count, 2)
            
            self.fw_serial.wileye_set_flash_enabled(True)
            self.assertEqual(mock_empty.call_count, 3)

    def test_wileye_response_frame_timeout(self):
        """Test handling of response frame timeouts."""
        # Mock timeout error
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Err("Timeout")):
            
            result = self.fw_serial.wileye_take_picture(0, "test.jpg")
            
            # Should return error result
            self.assertTrue(result.is_err())
            self.assertIn("Timeout", result.unwrap_err())

    def test_wileye_parameter_types(self):
        """Test that WilEye commands handle parameter types correctly."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("OK")):
            
            # Test integer parameters
            result = self.fw_serial.wileye_set_contrast(42)
            self.assertTrue(result.is_ok())
            
            # Test boolean parameters
            result = self.fw_serial.wileye_set_flash_enabled(True)
            self.assertTrue(result.is_ok())
            
            result = self.fw_serial.wileye_set_flash_enabled(False)
            self.assertTrue(result.is_ok())
            
            # Test string parameters
            result = self.fw_serial.wileye_take_picture(1, "my_photo.jpg")
            self.assertTrue(result.is_ok())

    def test_wileye_command_format_consistency(self):
        """Test that all WilEye commands follow consistent format."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("OK")):
            
            # All commands should start with "e\\c"
            commands_and_calls = [
                (lambda: self.fw_serial.wileye_take_picture(0, "test.jpg"), "e\\c\\t 0 test.jpg"),
                (lambda: self.fw_serial.wileye_start_recording_video(1, "vid.mp4"), "e\\c\\v 1 vid.mp4"),
                (lambda: self.fw_serial.wileye_stop_recording_video(), "e\\c\\s"),
                (lambda: self.fw_serial.wileye_set_contrast(50), "e\\c\\c 50\n"),
                (lambda: self.fw_serial.wileye_set_saturation(75), "e\\c\\i 75\n"),
                (lambda: self.fw_serial.wileye_set_brightness(60), "e\\c\\b 60\n"),
                (lambda: self.fw_serial.wileye_set_hue(90), "e\\c\\u 90\n"),
                (lambda: self.fw_serial.wileye_set_flash_enabled(True), "e\\c\\l 1\n"),
                (lambda: self.fw_serial.wileye_set_zoom_level(2), "e\\c\\m 2"),
                (lambda: self.fw_serial.wileye_set_resolution(1), "e\\c\\y 1\n"),
            ]
            
            for command_func, expected_cmd in commands_and_calls:
                command_func()
                self.mock_serial_port.send.assert_called_with(expected_cmd)


class TestWilEyeIntegration(unittest.TestCase):
    """Integration tests for WilEye camera commands."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.mock_serial_port = Mock()
        self.fw_serial = FreeWiliSerial("COM1")
        self.fw_serial.serial_port = self.mock_serial_port
        self.fw_serial._is_connected = True

    def test_camera_workflow_take_picture(self):
        """Test complete camera workflow for taking pictures."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("OK")):
            
            # Typical workflow: Set parameters, then take picture
            self.fw_serial.wileye_set_resolution(2)  # Set high resolution
            self.fw_serial.wileye_set_brightness(75)  # Adjust brightness
            self.fw_serial.wileye_set_flash_enabled(True)  # Enable flash
            result = self.fw_serial.wileye_take_picture(0, "outdoor_photo.jpg")
            
            # Verify all commands succeeded
            self.assertTrue(result.is_ok())
            
            # Verify command sequence
            expected_calls = [
                "e\\c\\y 2\n",  # Set resolution
                "e\\c\\b 75\n",  # Set brightness
                "e\\c\\l 1\n",  # Enable flash
                "e\\c\\t 0 outdoor_photo.jpg"  # Take picture
            ]
            
            actual_calls = [call[0][0] for call in self.mock_serial_port.send.call_args_list if isinstance(call[0][0], str)]
            self.assertEqual(actual_calls, expected_calls)

    def test_camera_workflow_record_video(self):
        """Test complete camera workflow for recording video."""
        with patch.object(self.fw_serial, '_empty_all'), \
             patch.object(self.fw_serial, '_handle_final_response_frame', return_value=Ok("OK")):
            
            # Typical workflow: Set parameters, start recording, stop recording
            self.fw_serial.wileye_set_resolution(1)  # Medium resolution for video
            self.fw_serial.wileye_set_zoom_level(1)  # No zoom
            start_result = self.fw_serial.wileye_start_recording_video(0, "meeting_video.mp4")
            stop_result = self.fw_serial.wileye_stop_recording_video()
            
            # Verify all commands succeeded
            self.assertTrue(start_result.is_ok())
            self.assertTrue(stop_result.is_ok())
            
            # Verify command sequence
            expected_calls = [
                "e\\c\\y 1\n",  # Set resolution
                "e\\c\\m 1",  # Set zoom level
                "e\\c\\v 0 meeting_video.mp4",  # Start recording
                "e\\c\\s"  # Stop recording
            ]
            
            actual_calls = [call[0][0] for call in self.mock_serial_port.send.call_args_list if isinstance(call[0][0], str)]
            self.assertEqual(actual_calls, expected_calls)


if __name__ == '__main__':
    unittest.main()