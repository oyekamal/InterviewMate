# Windows-specific keystroke capture using pynput
# Fallback could be pyHook if pynput has issues with admin rights or background operation.

from pynput import keyboard
import threading
import time
import re # For word parsing

# For getting active window title and process name
import psutil
import pygetwindow # May need to install: pip install pygetwindow

# TODO: Import proper logger and config from the application
# from .. import logger as app_logger
# from ..config import load_config # This might be too direct, pass config object

class WindowsKeyCapture:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback # Callback to log keywords: log_callback({"app": app_name, "word": word})
        self.listener_thread = None
        self.running = False
        self.buffer = ""
        self.last_activity_time = time.time()

        # Extract filter settings from config
        self.filters = self.config.get('keyword_filters', {})
        self.include_processes = [p.lower() for p in self.filters.get('include_processes', [])]
        self.exclude_words = [w.lower() for w in self.filters.get('exclude_words', [])]
        self.word_regex = re.compile(r'\w+') # Regex to find words

        # Buffer timeout for flushing incomplete words (e.g., if user stops typing mid-word)
        self.buffer_timeout_seconds = 5 # Flush buffer if no new char for this long

    def get_active_window_info(self):
        try:
            active_window = pygetwindow.getActiveWindow()
            if active_window:
                title = active_window.title
                # Get process associated with the window handle (HWND)
                # This part can be tricky and might require win32gui directly for more robust PID finding
                # For now, psutil.process_iter() and check window title / visible windows.
                # A simpler but less accurate way for MVP:
                # Assume the foreground window's process is the target.
                # This might not always be true for all apps (e.g. some games, complex UIs)

                # A more direct way to get PID from HWND (requires pywin32)
                # import win32process
                # import win32gui
                # hwnd = win32gui.GetForegroundWindow()
                # _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # process = psutil.Process(pid)
                # return process.name(), title

                # Simpler approach for now, iterate processes, check names against include_processes
                # This is not ideal as it doesn't directly link to the active window's process.
                # A better approach for pynput might be to get the process from the window hook event if available
                # For now, we'll rely on the process name list and assume typing occurs in one of them.
                # This means we might log even if the active window is not one of the include_processes,
                # but the typing is still captured. The filtering by process name will happen before logging.

                # Let's try to get the process of the active window more reliably.
                # This requires pywin32.
                try:
                    import win32gui
                    import win32process
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid > 0: # Ensure valid PID
                             p = psutil.Process(pid)
                             return p.name(), title
                except ImportError:
                    # Fallback if pywin32 is not installed - this is less accurate
                    # For MVP, this could be acceptable, or pywin32 becomes a hard dependency
                    # This part would need to be communicated clearly.
                    # For now, return a placeholder if pywin32 is not available.
                    # app_logger.log_error("pywin32 not installed, cannot accurately get active process name.", self.config, is_critical=False)
                    print("Warning: pywin32 not installed. Active process name detection might be inaccurate.")
                    return "unknown_process", title # Fallback
                except psutil.NoSuchProcess:
                     return "unknown_process", title # Process might have died quickly
                except Exception as e:
                    # app_logger.log_error(f"Error getting active window info with pywin32: {e}", self.config, is_critical=False)
                    print(f"Error getting active window info with pywin32: {e}")
                    return "unknown_process", title # Fallback

            return "unknown_process", "No active window" # Fallback
        except Exception as e:
            # app_logger.log_error(f"Error getting active window info: {e}", self.config, is_critical=False)
            print(f"Error getting active window info: {e}")
            return "unknown_process", "Error" # Fallback

    def process_buffer(self, force_flush=False):
        # Process the buffer to extract words
        # A word is typically terminated by space, enter, punctuation, or timeout

        # Simple space/enter based splitting for now
        # More sophisticated word boundary detection might be needed.

        # If force_flush is true, process whatever is in buffer.
        # Otherwise, look for delimiters like space or newline.

        content_to_process = self.buffer
        processed_upto_idx = -1

        # Try to split by common delimiters first
        parts = re.split(r'(\s+)', content_to_process) # Split by space/tab/newline, keeping delimiters

        current_word = ""
        for part in parts:
            if not part: continue # Skip empty parts from multiple delimiters

            if part.isspace(): # If it's a space or other whitespace
                if current_word:
                    self.submit_word(current_word)
                    current_word = ""
                # What to do with the space itself? Ignored for now.
                processed_upto_idx += len(part)
            else: # It's part of a word
                current_word += part

        # If there's a remaining current_word, it means no delimiter was found at the end
        if current_word:
            if force_flush and current_word: # If forced, submit whatever is left
                self.submit_word(current_word)
                processed_upto_idx += len(current_word)
                self.buffer = "" # Cleared
            else: # Not forced, keep it in buffer for next time
                self.buffer = current_word
        else: # All parts processed or buffer was empty
            self.buffer = ""


    def submit_word(self, word_candidate):
        word_candidate = word_candidate.strip().lower()
        if not word_candidate or len(word_candidate) < 2 : # Ignore very short "words" or empty
            return

        # Check against exclude_words
        if any(excluded in word_candidate for excluded in self.exclude_words):
            # print(f"Word '{word_candidate}' excluded.")
            return

        app_name, window_title = self.get_active_window_info()
        app_name_lower = app_name.lower().replace(".exe", "")

        # Check against include_processes
        if self.include_processes and not any(proc_name in app_name_lower for proc_name in self.include_processes):
            # print(f"App '{app_name_lower}' not in include_processes list. Word '{word_candidate}' from title '{window_title}' not logged.")
            return

        # Log the keyword
        # The log_callback expects a dictionary: {"app": app_name, "word": word}
        # The logger module will format it as: "[timestamp] app_name: 'word'"
        log_data = {"app": app_name, "word": word_candidate, "title": window_title}
        self.log_callback(log_data)
        # print(f"Logged: App: {app_name}, Title: {window_title}, Word: {word_candidate}")


    def on_press(self, key):
        self.last_activity_time = time.time()
        try:
            # Handle alphanumeric and common characters
            if hasattr(key, 'char') and key.char is not None:
                self.buffer += key.char
            # Handle space, enter, tab as word delimiters
            elif key == keyboard.Key.space:
                self.buffer += " " # Add space to trigger word processing
                self.process_buffer()
            elif key == keyboard.Key.enter:
                self.process_buffer(force_flush=True) # Process current buffer then effectively add newline (or handle separately)
                # self.buffer += "\n" # Or handle enter as a flush signal
            elif key == keyboard.Key.tab:
                self.process_buffer(force_flush=True) # Treat tab as a word separator
                # self.buffer += "\t" # Or specific handling
            # Could add more special keys like backspace if complex editing is to be tracked
            # elif key == keyboard.Key.backspace:
            #    self.buffer = self.buffer[:-1]

        except AttributeError:
            # Special keys (e.g., shift, ctrl, etc.) are ignored for now
            # print(f"Special key {key} pressed - ignored for word buffer")
            pass # We are interested in typed words, not control keys.
        except Exception as e:
            # app_logger.log_error(f"Error in on_press: {e}", self.config)
            print(f"Error in on_press: {e}")


    def _listener_main(self):
        # This function will run in a separate thread
        # For pynput, the listener itself is blocking
        with keyboard.Listener(on_press=self.on_press) as k_listener:
            self.pynput_listener_obj = k_listener # Store for potential external stop
            print("Windows Key Listener started in thread.")
            # The listener blocks here until k_listener.stop() is called or an error occurs
            # We need a way for self.running to stop this.
            # The 'with' statement handles joining the listener thread on exit.
            # To make it stoppable by self.running:
            # k_listener.start()
            # while self.running:
            #    time.sleep(0.1) # Keep alive, allow self.running to break
            # k_listener.stop()
            # k_listener.join() # Ensure it's fully stopped.

            # Simpler: The 'with' statement is fine if stop() is called from another thread.
            # The listener will run until stop() is called on it.
            k_listener.join() # This makes this thread wait until listener is stopped.
        print("Windows Key Listener thread finished.")


    def _buffer_timeout_checker(self):
        """Periodically checks if the buffer should be flushed due to inactivity."""
        while self.running:
            time.sleep(self.buffer_timeout_seconds / 2) # Check periodically
            if self.buffer and (time.time() - self.last_activity_time > self.buffer_timeout_seconds):
                # print(f"Buffer timeout for: '{self.buffer}', flushing.")
                self.process_buffer(force_flush=True)


    def start(self):
        if self.running:
            print("Key capture already running.")
            return

        self.running = True
        self.buffer = ""
        self.last_activity_time = time.time()

        # Start the pynput listener in a separate thread
        self.listener_thread = threading.Thread(target=self._listener_main, daemon=True)
        self.listener_thread.start()

        # Start buffer timeout checker thread
        self.timeout_thread = threading.Thread(target=self._buffer_timeout_checker, daemon=True)
        self.timeout_thread.start()

        print("WindowsKeyCapture started with pynput.")

    def stop(self):
        if not self.running:
            # print("Key capture not running.")
            return

        self.running = False

        # Stop the pynput listener
        # The listener needs to be stopped from the outside.
        # keyboard.Listener.stop() can be called globally if there's only one.
        # Or, if we have the instance:
        if hasattr(self, 'pynput_listener_obj') and self.pynput_listener_obj:
            try:
                # print("Attempting to stop pynput listener...")
                self.pynput_listener_obj.stop()
            except Exception as e: # Broad exception as pynput might have internal state issues on stop
                # app_logger.log_error(f"Error stopping pynput listener: {e}", self.config, is_critical=False)
                print(f"Error stopping pynput listener: {e}")

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2) # Wait for thread to finish
            if self.listener_thread.is_alive():
                print("Listener thread did not stop gracefully.")
                # app_logger.log_error("Keystroke listener thread did not stop gracefully.", self.config, is_critical=False)


        if self.timeout_thread and self.timeout_thread.is_alive():
            self.timeout_thread.join(timeout=1)

        # Process any remaining buffer content
        if self.buffer:
            # print(f"Flushing remaining buffer on stop: '{self.buffer}'")
            self.process_buffer(force_flush=True)

        print("WindowsKeyCapture stopped.")


if __name__ == '__main__':
    print("Windows Keystroke Capture Module (pynput)")

    # Mock config and logger for testing
    mock_config_data = {
        'keyword_filters': {
            'include_processes': ["notepad", "chrome", "firefox", "explorer"], # explorer for file dialogs etc.
            'exclude_words': ["password", "secret"]
        },
        'log_directory': 'TestData/Logs_WinKeyCapture', # Dummy for errors if any
        'config_file_path': 'dummy_config.yaml' # For error logger pathing
    }

    # Ensure log directory exists for potential error logs from this test
    # import os
    # if not os.path.exists(mock_config_data['log_directory']):
    #    os.makedirs(mock_config_data['log_directory'], exist_ok=True)


    def test_log_keyword(keyword_info):
        # Expected format: {"app": app_name, "word": word, "title": window_title}
        print(f"CALLBACK - App: {keyword_info['app']}, Word: '{keyword_info['word']}', WinTitle: '{keyword_info['title']}'")

    print("Initializing key capture... (Requires admin rights if hooking globally without UAC bypass)")
    print("Ensure pygetwindow and pynput are installed (`pip install pygetwindow pynput psutil pywin32`)")
    print("Try typing in Notepad or Chrome after starting.")

    capturer = None
    try:
        capturer = WindowsKeyCapture(mock_config_data, test_log_keyword)
        capturer.start()
        print("Capture started. Type for 30 seconds or press Ctrl+C in this console to stop.")
        time.sleep(300) # Run for 300 seconds (5 minutes) or until Ctrl+C
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping capture...")
    except Exception as e:
        print(f"An error occurred: {e}")
        # import traceback
        # traceback.print_exc()
    finally:
        if capturer:
            print("Stopping capture...")
            capturer.stop()
            print("Capture stopped.")
        print("Test finished.")
