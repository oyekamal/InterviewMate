# Linux-specific screenshot capture
# Options:
# 1. `pyscreenshot` library (wrapper around backends like scrot, gnome-screenshot)
# 2. `scrot` command-line tool directly (requires scrot to be installed)
# 3. `gnome-screenshot` command-line tool (if GNOME environment)
# 4. Xlib directly (more complex)

# Using pyscreenshot for broader compatibility if available.
# Fallback to scrot if pyscreenshot is problematic or not installed.

import subprocess
import io
import os # For checking if scrot is available via PATH

# Attempt to use pyscreenshot first
try:
    import pyscreenshot as ImageGrab
    PYSCREENSHOT_AVAILABLE = True
    print("Using pyscreenshot for Linux screenshots.")
except ImportError:
    ImageGrab = None
    PYSCREENSHOT_AVAILABLE = False
    print("pyscreenshot not found. Will attempt to use 'scrot' or 'gnome-screenshot' CLI.")

# from .. import logger as app_logger # For logging errors
# from ..config import load_config # If needed

class LinuxScreenshotCapture:
    def __init__(self, config):
        self.config = config
        self.backend_preference = ['gnome-screenshot', 'scrot'] # Preferred CLI tools if pyscreenshot fails or isn't used
        self.active_backend = None

        if PYSCREENSHOT_AVAILABLE:
            self.active_backend = "pyscreenshot"
        else: # Check for CLI backends
            for backend_cmd in self.backend_preference:
                if self._is_tool_available(backend_cmd):
                    self.active_backend = backend_cmd
                    print(f"Using '{self.active_backend}' CLI for Linux screenshots.")
                    break
            if not self.active_backend:
                msg = "No suitable screenshot tool (pyscreenshot, scrot, gnome-screenshot) found on Linux."
                # app_logger.log_error(msg, self.config, is_critical=True)
                print(f"CRITICAL: {msg}")
                raise RuntimeError(msg) # Critical, cannot function

        # Ensure DISPLAY is set, essential for X11 based tools
        if not os.environ.get('DISPLAY'):
            # app_logger.log_error("DISPLAY environment variable not set. Screenshot capture may fail.", self.config, is_critical=False)
            print("Warning: DISPLAY environment variable not set. Screenshot capture may fail on Linux.")


    def _is_tool_available(self, name):
        """Check whether `name` is on PATH and marked as executable."""
        from shutil import which
        return which(name) is not None

    def _capture_with_pyscreenshot(self):
        try:
            # This captures the virtual screen, handling multi-monitor setups if backend supports it.
            screenshot = ImageGrab.grab() # Returns a PIL Image object
            if screenshot:
                img_byte_arr = io.BytesIO()
                screenshot.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
            else:
                # app_logger.log_error("Linux screenshot (pyscreenshot) failed: grab() returned None.", self.config)
                print("Linux screenshot (pyscreenshot) failed: grab() returned None.")
                return None
        except Exception as e:
            # app_logger.log_error(f"Error during Linux screenshot (pyscreenshot): {e}", self.config)
            print(f"Error during Linux screenshot (pyscreenshot): {e}")
            # If pyscreenshot fails, we could try falling back to CLI if not already using it.
            # However, the constructor already selected a backend. If pyscreenshot was chosen and fails,
            # it might indicate a deeper issue (e.g., display server problem).
            return None

    def _capture_with_cli(self, tool_name):
        try:
            tmp_file = "/tmp/parental_monitor_screenshot.png" # Temporary file for the screenshot

            if tool_name == 'scrot':
                # scrot options:
                # -o: overwrite if exists
                # -q 0-100: quality (75 is default, higher is better but larger)
                # -z: silent operation (no beep)
                # '%Y-%m-%d-%H%M%S_$wx$h_scrot.png' # Example filename format for scrot itself
                # For simplicity, just save to tmp_file
                command = ["scrot", "-o", tmp_file, "-q", "90", "-z"]
            elif tool_name == 'gnome-screenshot':
                # gnome-screenshot options:
                # -f <filename>: save to file
                command = ["gnome-screenshot", "-f", tmp_file]
            else:
                # app_logger.log_error(f"Unsupported CLI tool for screenshot: {tool_name}", self.config)
                print(f"Unsupported CLI tool for screenshot: {tool_name}")
                return None

            # Ensure DISPLAY is available for the subprocess
            env = os.environ.copy()
            if not env.get('DISPLAY'):
                # app_logger.log_warning("DISPLAY not set, trying :0 for CLI screenshot tool", self.config)
                print("DISPLAY not set in environment, trying to use DISPLAY=:0 for CLI screenshot tool")
                env['DISPLAY'] = ':0' # Common default, but might not always be correct

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            stdout, stderr = process.communicate(timeout=10) # 10 second timeout

            if process.returncode == 0:
                if os.path.exists(tmp_file):
                    with open(tmp_file, 'rb') as f:
                        img_bytes = f.read()
                    os.remove(tmp_file) # Clean up temporary file
                    if not img_bytes: # File was empty
                         # app_logger.log_error(f"Linux screenshot ({tool_name}) produced an empty file.", self.config)
                         print(f"Linux screenshot ({tool_name}) produced an empty file.")
                         return None
                    return img_bytes
                else:
                    # app_logger.log_error(f"Linux screenshot ({tool_name}) command succeeded but temp file '{tmp_file}' not found.", self.config)
                    print(f"Linux screenshot ({tool_name}) command succeeded but temp file '{tmp_file}' not found. stdout: {stdout.decode()}, stderr: {stderr.decode()}")
                    return None
            else:
                # app_logger.log_error(f"Linux screenshot ({tool_name}) failed. Return code: {process.returncode}. Stderr: {stderr.decode()}", self.config)
                print(f"Linux screenshot ({tool_name}) failed. Return code: {process.returncode}. Stderr: {stderr.decode()}, Stdout: {stdout.decode()}")
                return None
        except subprocess.TimeoutExpired:
            # app_logger.log_error(f"Linux screenshot ({tool_name}) timed out.", self.config)
            print(f"Linux screenshot ({tool_name}) timed out.")
            if process: process.kill() # Ensure process is killed
            return None
        except FileNotFoundError: # Should be caught by _is_tool_available, but as safeguard
            # app_logger.log_error(f"Linux screenshot tool '{tool_name}' not found during capture attempt.", self.config, is_critical=True)
            print(f"CRITICAL: Linux screenshot tool '{tool_name}' not found during capture attempt.")
            raise RuntimeError(f"Screenshot tool '{tool_name}' missing.")
        except Exception as e:
            # app_logger.log_error(f"Error during Linux screenshot ({tool_name}): {e}", self.config)
            print(f"Error during Linux screenshot ({tool_name}): {e}")
            return None


    def capture(self):
        """
        Captures the full screen using the selected backend.
        Returns PNG image bytes, or None if capture fails.
        """
        if not self.active_backend:
            # This case should ideally be caught in __init__
            # app_logger.log_error("No active screenshot backend configured for Linux.", self.config, is_critical=True)
            print("CRITICAL: No active screenshot backend configured for Linux.")
            return None

        # print(f"Attempting screenshot with Linux backend: {self.active_backend}")
        if self.active_backend == "pyscreenshot":
            return self._capture_with_pyscreenshot()
        elif self.active_backend in self.backend_preference: # scrot or gnome-screenshot
            return self._capture_with_cli(self.active_backend)
        else:
            # Should not happen if __init__ is correct
            # app_logger.log_error(f"Unknown active backend '{self.active_backend}' for Linux screenshot.", self.config)
            print(f"Unknown active backend '{self.active_backend}' for Linux screenshot.")
            return None

if __name__ == '__main__':
    print("Linux Screenshot Capture Module")

    mock_config_data = {
        'log_directory': 'TestData/Logs_LinuxScreenshot',
        'config_file_path': 'dummy_config.yaml' # For error logger pathing
    }

    # import os
    # if not os.path.exists(mock_config_data['log_directory']):
    #    os.makedirs(mock_config_data['log_directory'], exist_ok=True)

    print("Initializing screenshot capturer for Linux...")
    try:
        capturer = LinuxScreenshotCapture(mock_config_data)
        print(f"Using backend: {capturer.active_backend}")

        print("Attempting to capture a screenshot...")
        png_bytes = capturer.capture()

        if png_bytes:
            print(f"Screenshot captured successfully. Size: {len(png_bytes)} bytes.")
            output_path = "test_linux_screenshot.png"
            try:
                with open(output_path, "wb") as f:
                    f.write(png_bytes)
                print(f"Screenshot saved to {output_path} for verification.")
                # On Linux, you might use 'xdg-open test_linux_screenshot.png' to view it.
                # subprocess.run(["xdg-open", output_path])
            except Exception as e:
                print(f"Error saving test screenshot: {e}")
        else:
            print("Failed to capture screenshot.")

    except RuntimeError as e: # From constructor if no backend found
        print(f"Initialization failed: {e}")
    except Exception as e: # Other unexpected errors
        print(f"An unexpected error occurred: {e}")
        # import traceback
        # traceback.print_exc()

    print("Test finished.")
