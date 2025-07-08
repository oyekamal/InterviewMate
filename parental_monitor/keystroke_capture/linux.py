# Linux-specific keystroke capture using pynput
# This typically requires X server access. For headless/Wayland, other methods like evdev might be needed.

from pynput import keyboard
import threading
import time
import re

# For getting active window title and process name on Linux
import subprocess # For xprop/xdotool
import psutil # For process name from PID

# from .. import logger as app_logger # Proper import from main app
# from ..config import load_config # Proper import

class LinuxKeyCapture:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback # Callback: log_callback({"app": app_name, "word": word})
        self.listener_thread = None
        self.running = False
        self.buffer = ""
        self.last_activity_time = time.time()

        self.filters = self.config.get('keyword_filters', {})
        self.include_processes = [p.lower() for p in self.filters.get('include_processes', [])]
        self.exclude_words = [w.lower() for w in self.filters.get('exclude_words', [])]
        self.word_regex = re.compile(r'\w+')

        self.buffer_timeout_seconds = 5 # Flush buffer if no new char for this long

    def get_active_window_info_x11(self):
        """Gets active window's process name and title using xdotool and psutil."""
        try:
            # Get active window ID
            active_window_id_cmd = ["xdotool", "getactivewindow"]
            active_window_id_proc = subprocess.run(active_window_id_cmd, capture_output=True, text=True, check=True)
            window_id = active_window_id_proc.stdout.strip()

            if not window_id:
                return "unknown_process", "No active window"

            # Get PID from window ID
            pid_cmd = ["xdotool", "getwindowpid", window_id]
            pid_proc = subprocess.run(pid_cmd, capture_output=True, text=True, check=True)
            pid_str = pid_proc.stdout.strip()

            app_name = "unknown_process"
            if pid_str.isdigit():
                pid = int(pid_str)
                try:
                    process = psutil.Process(pid)
                    app_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # app_logger.log_error(f"Could not get process info for PID {pid}", self.config, is_critical=False)
                    pass # Keep app_name as unknown

            # Get window title (WM_NAME)
            # xprop -id <WIN_ID> WM_NAME
            title_cmd = ["xprop", "-id", window_id, "WM_NAME"]
            title_proc = subprocess.run(title_cmd, capture_output=True, text=True) # Don't check=True, can fail if no name
            title = "Unknown Title"
            if title_proc.returncode == 0 and title_proc.stdout:
                match = re.search(r'WM_NAME\(\w+\) = "(.*)"', title_proc.stdout)
                if match:
                    title = match.group(1)

            return app_name, title

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # app_logger.log_error(f"Error getting active window info (xdotool/xprop): {e}. Is xdotool installed?", self.config, is_critical=False)
            # print(f"Error getting active window info (xdotool/xprop): {e}. Is xdotool installed?")
            # This error might be frequent if xdotool is not present. Log once or handle.
            # For now, print to console during dev.
            if "FileNotFoundError" in str(e) or (hasattr(e, 'stderr') and "not found" in e.stderr):
                print("Warning: xdotool or xprop not found. Please install them for active window detection.")
            return "unknown_process", "Error (xdotool)" # Fallback
        except Exception as e:
            # app_logger.log_error(f"Unexpected error in get_active_window_info_x11: {e}", self.config, is_critical=False)
            # print(f"Unexpected error in get_active_window_info_x11: {e}")
            return "unknown_process", "Error (x11_other)"


    def process_buffer(self, force_flush=False):
        content_to_process = self.buffer
        processed_upto_idx = -1

        parts = re.split(r'(\s+)', content_to_process)
        current_word = ""

        for part in parts:
            if not part: continue

            if part.isspace():
                if current_word:
                    self.submit_word(current_word)
                    current_word = ""
                processed_upto_idx += len(part)
            else:
                current_word += part

        if current_word:
            if force_flush:
                self.submit_word(current_word)
                self.buffer = ""
            else:
                self.buffer = current_word
        else:
            self.buffer = ""


    def submit_word(self, word_candidate):
        word_candidate = word_candidate.strip().lower()
        if not word_candidate or len(word_candidate) < 2:
            return

        if any(excluded in word_candidate for excluded in self.exclude_words):
            # print(f"Word '{word_candidate}' excluded.")
            return

        app_name, window_title = self.get_active_window_info_x11()
        app_name_lower = app_name.lower() # Process name on Linux usually doesn't have .exe

        if self.include_processes and not any(proc_name in app_name_lower for proc_name in self.include_processes):
            # print(f"App '{app_name_lower}' not in include_processes list. Word '{word_candidate}' from title '{window_title}' not logged.")
            return

        log_data = {"app": app_name, "word": word_candidate, "title": window_title}
        self.log_callback(log_data)
        # print(f"Logged: App: {app_name}, Title: {window_title}, Word: {word_candidate}")

    def on_press(self, key):
        self.last_activity_time = time.time()
        try:
            if hasattr(key, 'char') and key.char is not None:
                self.buffer += key.char
            elif key == keyboard.Key.space:
                self.buffer += " "
                self.process_buffer()
            elif key == keyboard.Key.enter:
                self.process_buffer(force_flush=True)
            elif key == keyboard.Key.tab:
                self.process_buffer(force_flush=True)
        except AttributeError:
            # Special keys ignored
            pass
        except Exception as e:
            # app_logger.log_error(f"Error in on_press (Linux): {e}", self.config)
            print(f"Error in on_press (Linux): {e}")


    def _listener_main(self):
        # pynput listener on Linux (X11)
        # It needs access to the X display.
        # If running as a systemd service, this might require `Environment=DISPLAY=:0`
        # and ensuring the service user can access X.
        # This can be problematic for security or if no X session is active (e.g. server).
        # Wayland is not directly supported by pynput's keyboard module in the same way;
        # evdev access might be a more robust (but complex) alternative for general input capture.

        # Check for DISPLAY environment variable
        import os
        if not os.environ.get('DISPLAY'):
            # app_logger.log_error("DISPLAY environment variable not set. pynput X11 listener may fail.", self.config)
            print("Warning: DISPLAY environment variable not set. pynput X11 listener may fail.")
            # For a service, this would need to be set, e.g. DISPLAY=:0 or DISPLAY=:1

        try:
            with keyboard.Listener(on_press=self.on_press, x11_event_loop=None) as k_listener: # Use default event loop
                self.pynput_listener_obj = k_listener
                print("Linux Key Listener started in thread (X11).")
                k_listener.join() # Blocks until listener.stop() is called
        except Exception as e: # Catch broad exceptions from pynput listener start
            # This could be display connection errors, etc.
            # app_logger.log_error(f"Failed to start pynput listener on Linux: {e}", self.config, is_critical=True)
            print(f"CRITICAL: Failed to start pynput listener on Linux: {e}")
            self.running = False # Ensure start() knows it failed.
        finally:
            print("Linux Key Listener thread finished.")

    def _buffer_timeout_checker(self):
        while self.running:
            time.sleep(self.buffer_timeout_seconds / 2)
            if self.buffer and (time.time() - self.last_activity_time > self.buffer_timeout_seconds):
                # print(f"Buffer timeout for (Linux): '{self.buffer}', flushing.")
                self.process_buffer(force_flush=True)

    def start(self):
        if self.running:
            print("Linux key capture already running.")
            return

        self.running = True
        self.buffer = ""
        self.last_activity_time = time.time()

        self.listener_thread = threading.Thread(target=self._listener_main, daemon=True)
        self.listener_thread.start()

        # Give a moment for the listener thread to indicate failure if it can't start
        time.sleep(0.5)
        if not self.running: # If _listener_main failed and set self.running to False
            print("Linux key capture failed to start (listener thread might have exited).")
            # app_logger.log_error("Linux key capture failed to start (listener thread did not stay active).", self.config, is_critical=True)
            # No need to start timeout_thread if listener failed
            return

        self.timeout_thread = threading.Thread(target=self._buffer_timeout_checker, daemon=True)
        self.timeout_thread.start()

        print("LinuxKeyCapture started with pynput (X11).")

    def stop(self):
        if not self.running:
            # print("Linux key capture not running.")
            return

        self.running = False

        if hasattr(self, 'pynput_listener_obj') and self.pynput_listener_obj:
            try:
                # print("Attempting to stop pynput listener (Linux)...")
                self.pynput_listener_obj.stop()
            except Exception as e:
                # app_logger.log_error(f"Error stopping pynput listener (Linux): {e}", self.config, is_critical=False)
                print(f"Error stopping pynput listener (Linux): {e}")

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)
            if self.listener_thread.is_alive():
                print("Linux listener thread did not stop gracefully.")
                # app_logger.log_error("Linux keystroke listener thread did not stop gracefully.", self.config, is_critical=False)

        if self.timeout_thread and self.timeout_thread.is_alive():
            self.timeout_thread.join(timeout=1)

        if self.buffer:
            # print(f"Flushing remaining buffer on stop (Linux): '{self.buffer}'")
            self.process_buffer(force_flush=True)

        print("LinuxKeyCapture stopped.")


if __name__ == '__main__':
    print("Linux Keystroke Capture Module (pynput for X11)")

    mock_config_data = {
        'keyword_filters': {
            'include_processes': ["gedit", "gnome-terminal", "firefox", "chrome", "chromium"],
            'exclude_words': ["password", "secret"]
        },
        'log_directory': 'TestData/Logs_LinuxKeyCapture',
        'config_file_path': 'dummy_config.yaml'
    }

    # import os
    # if not os.path.exists(mock_config_data['log_directory']):
    #    os.makedirs(mock_config_data['log_directory'], exist_ok=True)

    def test_log_keyword_linux(keyword_info):
        print(f"CALLBACK - App: {keyword_info['app']}, Word: '{keyword_info['word']}', WinTitle: '{keyword_info['title']}'")

    print("Initializing Linux key capture...")
    print("Ensure pynput is installed (`pip install pynput psutil`)")
    print("Ensure xdotool and xprop are installed (`sudo apt install xdotool xprop`) for active window detection.")
    print("This test requires an active X11 session.")
    print("Try typing in Gedit, a terminal, or Firefox after starting.")

    capturer = None
    try:
        capturer = LinuxKeyCapture(mock_config_data, test_log_keyword_linux)
        capturer.start()
        if not capturer.running: # Check if start failed
            print("Failed to start capturer. Exiting test.")
        else:
            print("Capture started. Type for 30 seconds or press Ctrl+C in this console to stop.")
            # pynput listener runs in a daemon thread, so main thread needs to stay alive.
            time.sleep(300) # Run for 5 minutes
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping capture...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if capturer:
            print("Stopping capture...")
            capturer.stop()
            print("Capture stopped.")
        print("Linux test finished.")
