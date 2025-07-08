# Screenshot capture package
# This __init__.py can provide a unified interface for platform-specific screenshot implementations.

import sys
import time
import threading
from .. import config as app_config # To get config for intervals, etc.
from .. import logger as app_logger # To save screenshots

_scheduler_thread = None
_stop_event = None # threading.Event() to signal scheduler to stop

# Placeholder for platform-specific capture function/class
_screenshot_capturer_instance = None

def _get_capturer_instance(config):
    """Initializes and returns the platform-specific screenshot capturer."""
    global _screenshot_capturer_instance
    if _screenshot_capturer_instance is None:
        if sys.platform == "win32":
            from . import windows as win_screenshot
            _screenshot_capturer_instance = win_screenshot.WindowsScreenshotCapture(config)
            print("Windows screenshot capturer initialized.")
        elif sys.platform.startswith("linux"):
            from . import linux as lin_screenshot
            _screenshot_capturer_instance = lin_screenshot.LinuxScreenshotCapture(config)
            print("Linux screenshot capturer initialized.")
        else:
            app_logger.log_error(f"Screenshot capture not supported on this platform: {sys.platform}", config)
            raise NotImplementedError(f"Screenshot capture not supported on platform {sys.platform}")
    return _screenshot_capturer_instance

def take_screenshot_and_log(config):
    """Takes a screenshot using the platform-specific method and logs it."""
    try:
        capturer = _get_capturer_instance(config)
        image_bytes = capturer.capture() # Returns PNG bytes
        if image_bytes:
            # The logger.save_screenshot function will handle encryption and saving to the correct location.
            saved_path = app_logger.save_screenshot(image_bytes, config)
            if saved_path:
                print(f"Screenshot taken and logged to {saved_path}")
            else:
                print("Failed to save screenshot after capturing.")
                # app_logger.log_error("take_screenshot_and_log: Failed to save screenshot (save_screenshot returned None)", config, is_critical=False)
        else:
            print("Failed to capture screenshot (capture method returned None).")
            # app_logger.log_error("take_screenshot_and_log: Failed to capture screenshot (capture method returned None)", config, is_critical=False)

    except NotImplementedError:
        # This was already logged by _get_capturer_instance if platform is unsupported
        pass
    except Exception as e:
        print(f"Error during screenshot capture and logging: {e}")
        app_logger.log_error(f"take_screenshot_and_log: Unhandled exception: {e}", config)


def _screenshot_scheduler_loop(config, stop_event):
    """Periodically calls take_screenshot_and_log."""
    interval_minutes = config.get('screenshot_interval_minutes', 5)
    interval_seconds = interval_minutes * 60

    if interval_seconds <= 0:
        print(f"Screenshot interval ({interval_minutes} min) is zero or negative. Scheduler will not run.")
        # app_logger.log_error(f"Screenshot interval ({interval_minutes} min) is invalid. Scheduler not started.", config, is_critical=True)
        return

    print(f"Screenshot scheduler started. Interval: {interval_minutes} minutes.")
    while not stop_event.is_set():
        try:
            # Initial call can be immediate, or wait for first interval.
            # Let's make it immediate for the first one, then wait.
            # This behavior might need adjustment based on requirements.
            # For now, let's wait for the first interval to align with "every N minutes".

            # Wait for the interval, but check stop_event frequently
            # This makes the scheduler more responsive to stop signals.
            wait_chunk = 5 # seconds to wait per check
            for _ in range(interval_seconds // wait_chunk):
                if stop_event.is_set(): break
                time.sleep(wait_chunk)

            # Handle remaining fractional time
            if not stop_event.is_set() and (interval_seconds % wait_chunk > 0) :
                 time.sleep(interval_seconds % wait_chunk)

            if stop_event.is_set():
                break # Exit loop if stop signal received during wait

            print("Scheduler: Time to take a screenshot.")
            take_screenshot_and_log(config)

        except Exception as e:
            print(f"Error in screenshot scheduler loop: {e}")
            app_logger.log_error(f"Screenshot scheduler loop error: {e}", config)
            # If critical errors occur, maybe stop the scheduler or increase wait time.
            # For now, continue trying.
            time.sleep(60) # Wait a minute before retrying if an error occurred in the loop itself.

    print("Screenshot scheduler stopped.")


def start_screenshot_scheduler(app_config_obj):
    """Starts the screenshot scheduler in a new thread."""
    global _scheduler_thread, _stop_event

    if _scheduler_thread and _scheduler_thread.is_alive():
        print("Screenshot scheduler already running.")
        return

    # Ensure logger is initialized before scheduler starts trying to use it
    # This should be done by the main application orchestrator
    # app_logger.initialize_logger(app_config_obj) # Assuming this is done elsewhere

    _stop_event = threading.Event()

    # Initialize capturer once (or ensure it can be initialized by the scheduler loop)
    try:
        _get_capturer_instance(app_config_obj) # Initialize early to catch platform issues
    except NotImplementedError:
        print("Cannot start screenshot scheduler: platform not supported for capture.")
        return # Don't start thread if not supported
    except Exception as e:
        print(f"Could not initialize screenshot capturer: {e}. Scheduler not started.")
        app_logger.log_error(f"Failed to initialize screenshot capturer: {e}. Scheduler not started.", app_config_obj)
        return


    _scheduler_thread = threading.Thread(target=_screenshot_scheduler_loop, args=(app_config_obj, _stop_event), daemon=True)
    _scheduler_thread.start()

def stop_screenshot_scheduler():
    """Stops the screenshot scheduler."""
    global _scheduler_thread, _stop_event
    if _stop_event:
        _stop_event.set() # Signal the loop to stop

    if _scheduler_thread and _scheduler_thread.is_alive():
        print("Stopping screenshot scheduler...")
        _scheduler_thread.join(timeout=10) # Wait for the thread to finish
        if _scheduler_thread.is_alive():
            print("Screenshot scheduler thread did not stop gracefully.")
            # Consider logging this if it happens in production
            # app_logger.log_error("Screenshot scheduler thread did not stop gracefully.", some_config_ref)
    _scheduler_thread = None
    _stop_event = None
    print("Screenshot scheduler signaled to stop (if it was running).")


if __name__ == '__main__':
    # This is a simplified example.
    # The main app would load config properly and initialize logger.
    import os
    from parental_monitor import config as cfg # For default config and paths
    from parental_monitor import logger as main_logger # For logger init

    print("Screenshot Capture Scheduler Module Example")

    # Create a dummy config for testing
    # Note: logger.py's __main__ creates TestData, so we might conflict or use it
    # For this test, let's use a specific path.
    test_base_dir = "TestData_ScreenshotScheduler"
    if not os.path.exists(test_base_dir):
        os.makedirs(test_base_dir, exist_ok=True)

    test_config_file = os.path.join(test_base_dir, "test_config_screenshots.yaml")
    test_log_dir = os.path.join(test_base_dir, "Logs")
    test_key_file = os.path.join(test_base_dir, "test_encryption.key")

    mock_config = {
        'screenshot_interval_minutes': 0.2, # Every 12 seconds for testing
        'log_directory': test_log_dir,
        'encryption_key_file': test_key_file,
        'config_file_path': os.path.abspath(test_config_file) # For logger relative pathing
    }

    # Save this mock_config to the test_config_file so config.py can load it if needed by sub-modules
    # Or, ensure all modules receive the config object directly.
    # For this test, we'll pass mock_config directly.

    print(f"Initializing main logger for the test (key: {test_key_file}, logs: {test_log_dir})")
    # This will create the key file if it doesn't exist.
    main_logger.initialize_logger(mock_config)


    print(f"Attempting to start screenshot scheduler on {sys.platform}...")
    try:
        start_screenshot_scheduler(mock_config)

        if not (_scheduler_thread and _scheduler_thread.is_alive()):
            print("Scheduler did not start (e.g. platform not supported or interval invalid). Test cannot proceed.")
        else:
            print("Scheduler started. Will take screenshots periodically.")
            print("Running for 30 seconds. Check for screenshots in:", os.path.abspath(test_log_dir))
            print("Press Ctrl+C to stop early.")
            time.sleep(30) # Run for 30 seconds

    except NotImplementedError as e:
        print(e)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"An error occurred in test main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Stopping screenshot scheduler...")
        stop_screenshot_scheduler()
        print("Screenshot module example finished.")

        # Clean up test files (optional)
        # import shutil
        # if os.path.exists(test_base_dir):
        #     print(f"To clean up, remove directory: {os.path.abspath(test_base_dir)}")
            # shutil.rmtree(test_base_dir)
