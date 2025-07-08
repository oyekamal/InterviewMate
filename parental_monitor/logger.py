# Handles data logging (keywords, screenshots) and file management.
import os
import datetime
from cryptography.fernet import Fernet
import shutil # For checking disk space
import sys # For sys.stderr in FATAL error case

# This will be part of utils.py later
ENCRYPTION_KEY = None

def load_or_generate_key(key_path):
    """Loads an encryption key from key_path or generates a new one."""
    global ENCRYPTION_KEY
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'wb') as f:
            f.write(key)
        print(f"Generated new encryption key at {key_path}")
    ENCRYPTION_KEY = key
    return Fernet(key)

# This should be initialized from config
cipher_suite = None

def initialize_logger(config):
    """Initializes the logger, sets up encryption."""
    global cipher_suite
    key_file = config.get('encryption_key_file', 'encryption.key')
    # Make key_file path relative to config file's directory or app install dir
    config_dir = os.path.dirname(config.get('config_file_path', '.')) # Assuming config_file_path is added to config
    if not os.path.isabs(key_file):
        key_file = os.path.join(config_dir, key_file)

    # Fallback if config_file_path is not available (e.g. during initial setup)
    if not os.path.exists(os.path.dirname(key_file)):
         # Try to place it near the log directory if possible
        log_base_dir = config.get('log_directory', 'ParentalMonitorData')
        if not os.path.isabs(log_base_dir): # if relative, make it absolute from CWD for now
            log_base_dir = os.path.abspath(log_base_dir)
        key_file_alt = os.path.join(os.path.dirname(log_base_dir) or log_base_dir, os.path.basename(key_file))

        # If config dir is not set, let's try to put key near the log_directory
        if not os.path.exists(os.path.dirname(key_file_alt)):
             os.makedirs(os.path.dirname(key_file_alt) or key_file_alt, exist_ok=True) # Handle case where key_file_alt is just a filename
        key_file = key_file_alt


    cipher_suite = load_or_generate_key(key_file)
    # Ensure log directory exists
    log_dir_base = config.get('log_directory', 'ParentalMonitorData')
    if not os.path.isabs(log_dir_base):
        log_dir_base = os.path.abspath(log_dir_base) # Make log_directory absolute

    # The actual daily log directory will be created by ensure_daily_log_dir
    # os.makedirs(log_dir_base, exist_ok=True) # Base directory for all logs

def get_daily_log_directory(base_log_dir):
    """Returns the path to the log directory for the current day."""
    today = datetime.date.today().strftime('%Y%m%d')
    return os.path.join(base_log_dir, today)

def ensure_daily_log_dir(config):
    """Ensures the daily log directory and its subdirectories (Screenshots) exist."""
    base_log_dir = config.get('log_directory', 'ParentalMonitorData')
    if not os.path.isabs(base_log_dir):
        # If config path is known, make it relative to config path's parent
        # Otherwise, relative to current working directory. This needs to be robust.
        config_file_location = config.get('config_file_path')
        if config_file_location:
            base_log_dir = os.path.join(os.path.dirname(config_file_location), base_log_dir)
        else: # Fallback to CWD. This is not ideal for a service.
             base_log_dir = os.path.abspath(base_log_dir)


    daily_dir = get_daily_log_directory(base_log_dir)
    screenshots_dir = os.path.join(daily_dir, 'Screenshots')

    try:
        os.makedirs(screenshots_dir, exist_ok=True)
        # Set permissions (basic example, might need more robust solution for cross-platform)
        # On POSIX, restrict to owner. Windows ACLs are more complex.
        if os.name == 'posix':
            os.chmod(base_log_dir, 0o700) # Restrict base log dir
            os.chmod(daily_dir, 0o700)
            os.chmod(screenshots_dir, 0o700)
    except Exception as e:
        log_error(f"Failed to create/set permissions for directory {screenshots_dir}: {e}", config)
        raise # Re-raise to indicate critical failure if directory cannot be created

    return daily_dir, screenshots_dir

def encrypt_data(data_bytes):
    """Encrypts data using the loaded key."""
    if not cipher_suite:
        raise ValueError("Logger not initialized or key not loaded.")
    return cipher_suite.encrypt(data_bytes)

def log_keyword(keyword_entry, config):
    """Logs a keyword entry to the encrypted keywords.log."""
    if not cipher_suite:
        print("Error: Encryption not initialized. Call initialize_logger first.")
        # Attempt to log this error to a plain text error log
        log_error("Attempted to log keyword before encryption was initialized.", config, is_critical=False)
        return

    daily_dir, _ = ensure_daily_log_dir(config)
    log_file_path = os.path.join(daily_dir, 'keywords.log.enc') # Encrypted log

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_log_entry = f"[{timestamp}] {keyword_entry}\n"

    encrypted_entry = encrypt_data(full_log_entry.encode('utf-8'))

    try:
        with open(log_file_path, 'ab') as f: # Append bytes
            f.write(encrypted_entry)
            f.write(b'\n') # Add a newline separator for distinct encrypted blocks if needed, or manage as a stream
        if os.name == 'posix':
            os.chmod(log_file_path, 0o600) # Read/write for owner only
    except Exception as e:
        log_error(f"Failed to write to keyword log {log_file_path}: {e}", config)


def save_screenshot(image_bytes, config):
    """Saves a screenshot as a PNG file, encrypted."""
    if not cipher_suite:
        print("Error: Encryption not initialized. Call initialize_logger first.")
        log_error("Attempted to save screenshot before encryption was initialized.", config, is_critical=False)
        return None

    _, screenshots_dir = ensure_daily_log_dir(config)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"{timestamp}.png.enc" # Encrypted screenshot
    file_path = os.path.join(screenshots_dir, file_name)

    encrypted_image_bytes = encrypt_data(image_bytes)

    try:
        with open(file_path, 'wb') as f:
            f.write(encrypted_image_bytes)
        if os.name == 'posix':
            os.chmod(file_path, 0o600)
        print(f"Screenshot saved to {file_path}")
        return file_path
    except Exception as e:
        log_error(f"Failed to save screenshot to {file_path}: {e}", config)
        return None

ERROR_LOG_FILE = "error.log"

def get_error_log_path(config):
    # Place error log in the base log directory or application install directory
    # It should NOT be in the daily directory and NOT encrypted.
    log_dir_base = config.get('log_directory', 'ParentalMonitorData')
    if not os.path.isabs(log_dir_base):
        # Try to make it relative to config file if path available
        config_file_location = config.get('config_file_path')
        if config_file_location:
            log_dir_base = os.path.join(os.path.dirname(os.path.dirname(config_file_location)), log_dir_base) # Parent of config dir
        else: # Fallback to CWD or one level above CWD's log_directory
            log_dir_base = os.path.abspath(os.path.join("..", log_dir_base))


    # Ensure the directory for error.log exists, separate from daily logs
    error_log_dir = os.path.dirname(log_dir_base) # Place it one level up from the main data folder
    if not error_log_dir : error_log_dir = "." # if log_dir_base was at root

    try:
        os.makedirs(error_log_dir, exist_ok=True)
    except Exception:
        # Fallback to current working directory if creation fails
        error_log_dir = "."

    return os.path.join(error_log_dir, ERROR_LOG_FILE)


def log_error(message, config, is_critical=True):
    """Logs an error message to error.log."""
    error_log_path = get_error_log_path(config) # Pass config to determine error log location
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {'CRITICAL: ' if is_critical else ''}{message}\n"

    try:
        with open(error_log_path, 'a') as f:
            f.write(log_entry)

        # Set permissions on the error log file, but only try once per path
        # to avoid repeated chmod calls on every error.
        # Using a dynamic attribute on the function itself to track this.
        # The attribute name includes the path to handle multiple possible error log locations (though unlikely for one app run).
        # Sanitize path for attribute name, replacing invalid characters.
        # Simplified: Assume one main error log path per app instance for this flag.
        # A more robust way might involve a class or a global dict for paths already chmod-ed.
        # For MVP, simple hasattr check on a fixed attribute name is likely sufficient if error_log_path is consistent.
        # Let's make the attribute name unique per path to be safer.
        # This is still a bit complex for a simple chmod. A simpler approach is to just call chmod every time.
        # The overhead is minimal. Let's simplify to always calling it on POSIX.
        if os.name == 'posix':
            try:
                os.chmod(error_log_path, 0o600) # Owner read/write
            except Exception:
                # Non-critical if this fails, the log might still be written.
                pass # nosemgrep: Non-critical chmod failure
    except Exception as e:
        # If we can't even write to the error log, print to stderr
        # We need to import sys for stderr for this specific exception case.
        # This was missing. Add 'import sys' at the top of logger.py.
        # For now, assume print to stdout is sufficient if sys.stderr is not available.
        # print(f"FATAL: Could not write to error log at {error_log_path}. Original error: {message}. Logging error: {e}", file=sys.stderr)
        print(f"FATAL: Could not write to error log at {error_log_path}. Original error: {message}. Logging error: {e}")

# --- Decryption utility (for CLI tool or parent access later) ---
def decrypt_data(encrypted_data_bytes, key_bytes):
    """Decrypts data using the provided key bytes."""
    fernet = Fernet(key_bytes)
    return fernet.decrypt(encrypted_data_bytes)

def decrypt_keyword_log(log_file_path_enc, key_file_path):
    """Decrypts and prints the content of an encrypted keyword log."""
    try:
        with open(key_file_path, 'rb') as f_key:
            key = f_key.read()

        fernet = Fernet(key)

        with open(log_file_path_enc, 'rb') as f_enc:
            # Read line by line if entries were separated by newlines before encryption
            # For now, assuming the whole file content is one block or multiple blocks separated by newlines
            # This depends on how log_keyword writes it.
            # If log_keyword writes newline AFTER encryption, then:
            for line in f_enc:
                line = line.strip()
                if not line: continue
                decrypted_entry = fernet.decrypt(line)
                print(decrypted_entry.decode('utf-8'), end='')
            # If newline was part of the encrypted content:
            # encrypted_content = f_enc.read()
            # decrypted_content = fernet.decrypt(encrypted_content)
            # print(decrypted_content.decode('utf-8'))

    except FileNotFoundError:
        print(f"Error: File not found ({log_file_path_enc} or {key_file_path})")
    except Exception as e:
        print(f"An error occurred during decryption: {e}")

def decrypt_screenshot(screenshot_path_enc, key_file_path, output_path_dec):
    """Decrypts an encrypted screenshot and saves it."""
    try:
        with open(key_file_path, 'rb') as f_key:
            key = f_key.read()

        fernet = Fernet(key)

        with open(screenshot_path_enc, 'rb') as f_enc:
            encrypted_data = f_enc.read()

        decrypted_data = fernet.decrypt(encrypted_data)

        with open(output_path_dec, 'wb') as f_dec:
            f_dec.write(decrypted_data)
        print(f"Screenshot decrypted and saved to {output_path_dec}")

    except FileNotFoundError:
        print(f"Error: File not found ({screenshot_path_enc} or {key_file_path})")
    except Exception as e:
        print(f"An error occurred during decryption: {e}")


if __name__ == '__main__':
    import sys
    # Example Usage (requires parental_monitor.config to be available)
    # This setup is a bit complex for a simple __main__ here,
    # as config loading itself might try to determine paths.
    # For testing, we'd typically mock or provide a fixed config.

    print("Logger module example.")
    # Create a dummy config for standalone testing
    dummy_config_path = "test_config.yaml"
    dummy_base_log_dir = "TestData"
    dummy_key_file = os.path.join(dummy_base_log_dir, "test.key")

    test_config = {
        'screenshot_interval_minutes': 1,
        'keyword_filters': {
            'include_processes': ["test_app"],
            'exclude_words': ["secret"]
        },
        'log_directory': dummy_base_log_dir,
        'encryption_key_file': dummy_key_file,
        'config_file_path': os.path.abspath(dummy_config_path) # Important for relative paths
    }

    # Clean up previous test runs if any
    if os.path.exists(dummy_base_log_dir):
        shutil.rmtree(dummy_base_log_dir)
    if os.path.exists(dummy_config_path):
        os.remove(dummy_config_path)
    if os.path.exists(get_error_log_path(test_config)): # remove main error log
        os.remove(get_error_log_path(test_config))


    os.makedirs(dummy_base_log_dir, exist_ok=True)

    # Save a dummy config file to the CWD for the test
    with open(dummy_config_path, 'w') as f:
        import yaml
        yaml.dump(test_config, f)

    print(f"Initializing logger with test config (key will be saved to: {dummy_key_file})")
    initialize_logger(test_config) # Key will be generated here if not exists

    print("Logging a keyword...")
    log_keyword("test_app.exe: 'this is a test keyword'", test_config)
    log_keyword("another_app.exe: 'sensitive data here filterme'", test_config)

    print("Simulating saving a screenshot...")
    # Create some dummy image bytes (e.g., a small text file for simplicity)
    dummy_image_bytes = b"This is not really a PNG, but it's test data."
    saved_screenshot_path = save_screenshot(dummy_image_bytes, test_config)
    if saved_screenshot_path:
        print(f"Dummy screenshot saved to: {saved_screenshot_path}")

    print("Logging an error...")
    log_error("This is a test error message.", test_config, is_critical=False)
    log_error("This is a critical test error.", test_config, is_critical=True)

    print(f"\nContents of {dummy_base_log_dir} (structure):")
    for root, dirs, files in os.walk(dummy_base_log_dir):
        for name in files:
            print(os.path.join(root, name))
        for name in dirs:
            print(os.path.join(root, name) + os.sep)

    error_log = get_error_log_path(test_config)
    if os.path.exists(error_log):
        print(f"\nContents of error log ({error_log}):")
        with open(error_log, 'r') as f:
            print(f.read())

    # Decryption example
    print("\n--- Decryption Test ---")
    today_str = datetime.date.today().strftime('%Y%m%d')
    enc_log_path = os.path.join(dummy_base_log_dir, today_str, 'keywords.log.enc')

    if os.path.exists(enc_log_path) and os.path.exists(dummy_key_file):
        print(f"\nDecrypting keyword log: {enc_log_path}")
        decrypt_keyword_log(enc_log_path, dummy_key_file)
    else:
        print(f"\nSkipping keyword log decryption, file not found: {enc_log_path} or key {dummy_key_file}")

    if saved_screenshot_path and os.path.exists(dummy_key_file):
        dec_screenshot_path = saved_screenshot_path.replace(".png.enc", "_dec.png")
        print(f"\nDecrypting screenshot: {saved_screenshot_path} to {dec_screenshot_path}")
        decrypt_screenshot(saved_screenshot_path, dummy_key_file, dec_screenshot_path)
        if os.path.exists(dec_screenshot_path):
             with open(dec_screenshot_path, 'rb') as f_dec:
                  print(f"Decrypted screenshot content: {f_dec.read().decode('utf-8', errors='ignore')}")
    else:
        print(f"\nSkipping screenshot decryption, file not found: {saved_screenshot_path} or key {dummy_key_file}")

    # print(f"\nTo clean up, remove: {dummy_config_path}, {dummy_base_log_dir}, and {error_log}")
