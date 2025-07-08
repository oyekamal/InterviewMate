# Windows-specific screenshot capture using Pillow (PIL Fork) with GDI+/Desktop DWM

from PIL import ImageGrab, Image # Pillow library
import io # To handle bytes in memory

# from .. import logger as app_logger # For logging errors, if necessary
# from ..config import load_config # If specific config needed here beyond passed obj

class WindowsScreenshotCapture:
    def __init__(self, config):
        self.config = config
        # Any Windows-specific initialization can go here if needed
        # e.g., check for specific DLLs, although Pillow usually handles this.
        print("WindowsScreenshotCapture initialized with Pillow.")

    def capture(self):
        """
        Captures the full screen.
        Returns PNG image bytes, or None if capture fails.
        """
        try:
            # ImageGrab.grab() captures the primary screen by default.
            # For multi-monitor setups, specific bounding boxes can be provided.
            # bbox=(x, y, width, height)
            # To capture all screens, one might need to iterate through screen geometries.
            # For MVP, primary screen is sufficient.
            # Use allscreens=True if your Pillow version supports it and it's desired.
            # Some versions of Pillow might require `pip install pywin32` for full features on Windows.

            # Check Pillow version for allscreens attribute if we need it later.
            # from PIL import __version__ as pillow_version
            # if pillow_version >= "some_version_supporting_allscreens":
            #    screenshot = ImageGrab.grab(all_screens=True)
            # else:
            #    screenshot = ImageGrab.grab()

            screenshot = ImageGrab.grab() # Captures primary screen

            if screenshot:
                # Convert to PNG bytes in memory
                img_byte_arr = io.BytesIO()
                screenshot.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                # print(f"Screenshot captured ({screenshot.width}x{screenshot.height}), PNG size: {len(img_bytes)} bytes")
                return img_bytes
            else:
                # app_logger.log_error("Windows screenshot capture failed: ImageGrab.grab() returned None.", self.config)
                print("Windows screenshot capture failed: ImageGrab.grab() returned None.")
                return None
        except Exception as e:
            # app_logger.log_error(f"Error during Windows screenshot capture: {e}", self.config)
            print(f"Error during Windows screenshot capture: {e}")
            # import traceback
            # traceback.print_exc() # For detailed debugging during development
            return None

if __name__ == '__main__':
    print("Windows Screenshot Capture Module (Pillow)")

    # Mock config for testing (not strictly used by capture() itself but good practice)
    mock_config_data = {
        'log_directory': 'TestData/Logs_WinScreenshot', # Dummy for errors if any
        'config_file_path': 'dummy_config.yaml'
    }

    # import os
    # if not os.path.exists(mock_config_data['log_directory']):
    #    os.makedirs(mock_config_data['log_directory'], exist_ok=True)

    print("Initializing screenshot capturer...")
    capturer = WindowsScreenshotCapture(mock_config_data)

    print("Attempting to capture a screenshot...")
    png_bytes = capturer.capture()

    if png_bytes:
        print(f"Screenshot captured successfully. Size: {len(png_bytes)} bytes.")
        # Save it to a file for verification
        output_path = "test_windows_screenshot.png"
        try:
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            print(f"Screenshot saved to {output_path} for verification.")
            # import os
            # os.startfile(output_path) # Open the screenshot
        except Exception as e:
            print(f"Error saving test screenshot: {e}")
    else:
        print("Failed to capture screenshot.")

    print("Test finished.")
