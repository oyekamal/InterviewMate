import unittest
import os
import shutil
import datetime
import time # For sleeping briefly to ensure different timestamps

# Adjust import path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parental_monitor import logger as app_logger
from parental_monitor import config as app_config # For default config structure
from parental_monitor import utils # For encryption parts

class TestLogger(unittest.TestCase):

    def setUp(self):
        self.test_suite_dir = "temp_test_logger_suite"
        os.makedirs(self.test_suite_dir, exist_ok=True)

        self.test_base_log_dir = os.path.join(self.test_suite_dir, "TestLogs")
        self.test_key_file_name = "test_logger_encryption.key"
        self.test_key_file_path = os.path.join(self.test_suite_dir, self.test_key_file_name) # Key outside log dir

        # Mock config for the logger.
        # The config_file_path is important for how logger resolves relative paths.
        self.mock_config_file_path = os.path.join(self.test_suite_dir, "mock_config.yaml")

        self.config = {
            'log_directory': self.test_base_log_dir, # This might be relative or absolute
            'encryption_key_file': self.test_key_file_path, # Path to key file
            'config_file_path': self.mock_config_file_path, # Used by logger to resolve relative paths
            # Add other default items if logger directly uses them, though mostly it uses above
             'keyword_filters': app_config.DEFAULT_CONFIG['keyword_filters'],
             'screenshot_interval_minutes': app_config.DEFAULT_CONFIG['screenshot_interval_minutes']
        }

        # Clean up before each test
        if os.path.exists(self.test_base_log_dir):
            shutil.rmtree(self.test_base_log_dir)
        if os.path.exists(self.test_key_file_path):
            os.remove(self.test_key_file_path)
        # Error log is placed relative to config or one level up from log_directory
        # Determine potential error log path and remove it
        self.error_log_path_test = app_logger.get_error_log_path(self.config)
        if os.path.exists(self.error_log_path_test):
            os.remove(self.error_log_path_test)

        # The logger's initialize_logger uses utils.initialize_encryption,
        # which uses a global _CIPHER_SUITE. Reset it for test isolation.
        utils._CIPHER_SUITE = None
        utils._ENCRYPTION_KEY_BYTES = None
        app_logger.cipher_suite = None # Also reset the one in logger module if it's distinct.

        # Initialize logger (this will also create the key file if it doesn't exist)
        # The logger's initialize_logger now calls utils.initialize_encryption
        app_logger.initialize_logger(self.config)
        self.assertTrue(os.path.exists(self.test_key_file_path), "Encryption key file was not created by initialize_logger.")

        # Ensure base log directory for daily logs is NOT created by initialize_logger itself,
        # but by ensure_daily_log_dir when first needed.
        # However, the parent of the base_log_dir (for error log) might be created.
        # Let's verify the state.
        # self.assertFalse(os.path.exists(self.test_base_log_dir), "Base log directory should not be created by init alone.")


    def tearDown(self):
        # Clean up all created files and directories
        if os.path.exists(self.test_suite_dir):
            shutil.rmtree(self.test_suite_dir)

        # Reset globals in utils and logger again for hygiene, though setUp should handle it for next test
        utils._CIPHER_SUITE = None
        utils._ENCRYPTION_KEY_BYTES = None
        app_logger.cipher_suite = None


    def _get_expected_daily_dir_paths(self):
        # Determine where the logger *should* be putting things based on current config
        base_log_dir_abs = self.config['log_directory']
        if not os.path.isabs(base_log_dir_abs):
            # logger.py's ensure_daily_log_dir logic:
            # If config_file_path is set, log_directory is relative to its parent.
            # Otherwise, it's relative to CWD.
            # In our test setup, config_file_path IS set.
            config_dir_parent = os.path.dirname(self.config['config_file_path'])
            base_log_dir_abs = os.path.join(config_dir_parent, self.config['log_directory'])
        base_log_dir_abs = os.path.abspath(base_log_dir_abs)

        today_str = datetime.date.today().strftime('%Y%m%d')
        expected_daily_dir = os.path.join(base_log_dir_abs, today_str)
        expected_screenshots_dir = os.path.join(expected_daily_dir, 'Screenshots')
        expected_keywords_log = os.path.join(expected_daily_dir, 'keywords.log.enc')
        return expected_daily_dir, expected_screenshots_dir, expected_keywords_log


    def test_01_daily_directory_creation(self):
        """Test that ensure_daily_log_dir creates the correct daily directory and Screenshots subdir."""
        expected_daily_dir, expected_screenshots_dir, _ = self._get_expected_daily_dir_paths()

        # Call the function that implicitly creates these
        # For example, logging a keyword or saving a screenshot.
        # Or call ensure_daily_log_dir directly for a focused test.
        actual_daily_dir, actual_screenshots_dir = app_logger.ensure_daily_log_dir(self.config)

        self.assertEqual(os.path.abspath(actual_daily_dir), os.path.abspath(expected_daily_dir))
        self.assertEqual(os.path.abspath(actual_screenshots_dir), os.path.abspath(expected_screenshots_dir))

        self.assertTrue(os.path.isdir(actual_daily_dir), "Daily log directory was not created.")
        self.assertTrue(os.path.isdir(actual_screenshots_dir), "Screenshots subdirectory was not created.")

        if os.name == 'posix': # Test permissions if on POSIX
            # Base log dir permissions are also set by ensure_daily_log_dir's logic.
            # Need to get the absolute path of the base log directory first.
            base_log_dir_path = os.path.dirname(actual_daily_dir)
            self.assertEqual(os.stat(base_log_dir_path).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(actual_daily_dir).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(actual_screenshots_dir).st_mode & 0o777, 0o700)


    def test_02_log_keyword_creates_encrypted_log(self):
        """Test logging a keyword, ensuring the log file is created and encrypted."""
        _, _, expected_keywords_log_path = self._get_expected_daily_dir_paths()

        test_app_name = "test_app.exe"
        test_keyword = "hello world from test"
        keyword_entry_raw = f"{test_app_name}: \"{test_keyword}\""

        app_logger.log_keyword(keyword_entry_raw, self.config)
        self.assertTrue(os.path.exists(expected_keywords_log_path), "keywords.log.enc was not created.")

        if os.name == 'posix':
            self.assertEqual(os.stat(expected_keywords_log_path).st_mode & 0o777, 0o600)

        # Verify content by decrypting
        with open(self.test_key_file_path, 'rb') as f_key:
            key_bytes = f_key.read()

        decrypted_lines = []
        with open(expected_keywords_log_path, 'rb') as f_enc:
            for line_bytes in f_enc: # logger writes a newline after each encrypted block
                line_bytes = line_bytes.strip()
                if not line_bytes: continue
                decrypted_entry_bytes = utils.decrypt(line_bytes) # Use utils directly with loaded key
                decrypted_lines.append(decrypted_entry_bytes.decode('utf-8'))

        self.assertEqual(len(decrypted_lines), 1, "Should be one log entry.")
        # Example format: "[2023-10-27 10:00:00] test_app.exe: "hello world""
        self.assertIn(keyword_entry_raw, decrypted_lines[0])
        self.assertTrue(decrypted_lines[0].startswith("["))
        self.assertTrue(decrypted_lines[0].endswith("]\n" if "\n" in decrypted_lines[0] else "]")) # logger adds \n before encrypting


    def test_03_save_screenshot_creates_encrypted_file(self):
        """Test saving a screenshot, ensuring file is created, named correctly, and encrypted."""
        _, expected_screenshots_dir, _ = self._get_expected_daily_dir_paths()

        dummy_image_bytes = b"This is a fake PNG content for testing."

        # Call before save_screenshot to ensure directories are there.
        # In real app, scheduler calls take_screenshot_and_log which calls ensure_daily_log_dir.
        app_logger.ensure_daily_log_dir(self.config)

        saved_path = app_logger.save_screenshot(dummy_image_bytes, self.config)
        self.assertIsNotNone(saved_path, "save_screenshot did not return a path.")
        self.assertTrue(os.path.exists(saved_path), "Screenshot file was not created.")
        self.assertTrue(saved_path.startswith(expected_screenshots_dir), "Screenshot not in expected directory.")
        self.assertTrue(saved_path.endswith(".png.enc"), "Screenshot file does not have .png.enc extension.")

        # Verify name format YYYYMMDD_HHMMSS.png.enc
        file_name = os.path.basename(saved_path)
        parts = file_name.split('_')
        self.assertTrue(len(parts) >= 2, f"Screenshot filename '{file_name}' not in expected format.")
        self.assertEqual(len(parts[0]), 8) # YYYYMMDD
        self.assertTrue(parts[0].isdigit())
        self.assertEqual(len(parts[1].split('.')[0]), 6) # HHMMSS
        self.assertTrue(parts[1].split('.')[0].isdigit())

        if os.name == 'posix':
            self.assertEqual(os.stat(saved_path).st_mode & 0o777, 0o600)

        # Verify content by decrypting
        with open(self.test_key_file_path, 'rb') as f_key:
            key_bytes = f_key.read()

        with open(saved_path, 'rb') as f_enc:
            encrypted_content = f_enc.read()

        decrypted_content_bytes = utils.decrypt(encrypted_content) # Use utils with loaded key
        self.assertEqual(decrypted_content_bytes, dummy_image_bytes)


    def test_04_log_error_creates_error_log(self):
        """Test that log_error creates and appends to error.log (unencrypted)."""
        error_message = "This is a test error message."
        app_logger.log_error(error_message, self.config, is_critical=False)

        self.assertTrue(os.path.exists(self.error_log_path_test), "error.log was not created.")

        with open(self.error_log_path_test, 'r') as f:
            content = f.read()

        self.assertIn(error_message, content)
        self.assertTrue(content.startswith("[")) # Timestamp

        # Test critical flag
        critical_error_message = "This is a CRITICAL test error."
        app_logger.log_error(critical_error_message, self.config, is_critical=True)
        with open(self.error_log_path_test, 'r') as f:
            content = f.read()
        self.assertIn(critical_error_message, content)
        self.assertIn("CRITICAL:", content)


    def test_05_multiple_keyword_logs_append(self):
        """Test that multiple keyword logs append to the same file correctly."""
        _, _, expected_keywords_log_path = self._get_expected_daily_dir_paths()

        entry1_raw = "app1: 'first entry'"
        entry2_raw = "app2: 'second entry'"

        app_logger.log_keyword(entry1_raw, self.config)
        time.sleep(0.01) # Ensure timestamp can differ if needed, though content is main check
        app_logger.log_keyword(entry2_raw, self.config)

        # Decrypt and check
        with open(self.test_key_file_path, 'rb') as f_key: key_bytes = f_key.read()
        decrypted_lines = []
        with open(expected_keywords_log_path, 'rb') as f_enc:
            for line_bytes in f_enc:
                line_bytes = line_bytes.strip()
                if not line_bytes: continue
                decrypted_lines.append(utils.decrypt(line_bytes).decode('utf-8'))

        self.assertEqual(len(decrypted_lines), 2)
        self.assertIn(entry1_raw, decrypted_lines[0])
        self.assertIn(entry2_raw, decrypted_lines[1])

    def test_06_decryption_utilities_in_logger(self):
        """Test the decryption helper functions in logger.py (decrypt_keyword_log, decrypt_screenshot)."""
        # 1. Log a keyword
        keyword_raw = "decrypt_test_app: 'testing decryption utility'"
        app_logger.log_keyword(keyword_raw, self.config)
        _, _, keywords_log_path_enc = self._get_expected_daily_dir_paths()

        # Redirect stdout to capture print output from decrypt_keyword_log
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output # Redirect stdout

        app_logger.decrypt_keyword_log(keywords_log_path_enc, self.test_key_file_path)
        sys.stdout = sys.__stdout__ # Reset stdout

        output_str = captured_output.getvalue()
        self.assertIn(keyword_raw, output_str)

        # 2. Save a "screenshot"
        image_bytes = b"dummy image for decryption test"
        app_logger.ensure_daily_log_dir(self.config) # Ensure screenshot dir exists
        screenshot_path_enc = app_logger.save_screenshot(image_bytes, self.config)
        self.assertIsNotNone(screenshot_path_enc)

        decrypted_screenshot_output_path = os.path.join(self.test_suite_dir, "decrypted_test_image.png")
        if os.path.exists(decrypted_screenshot_output_path): os.remove(decrypted_screenshot_output_path)

        app_logger.decrypt_screenshot(screenshot_path_enc, self.test_key_file_path, decrypted_screenshot_output_path)
        self.assertTrue(os.path.exists(decrypted_screenshot_output_path))

        with open(decrypted_screenshot_output_path, 'rb') as f_dec:
            content = f_dec.read()
        self.assertEqual(content, image_bytes)

        os.remove(decrypted_screenshot_output_path)


    def test_07_logger_init_with_existing_key(self):
        """Test that initialize_logger loads an existing key correctly."""
        # Key is created in setUp. We need to simulate re-initialization.
        # First, grab the key content.
        with open(self.test_key_file_path, 'rb') as f:
            original_key_content = f.read()

        # Reset cipher_suite in logger and utils to force re-init path
        app_logger.cipher_suite = None
        utils._CIPHER_SUITE = None
        utils._ENCRYPTION_KEY_BYTES = None # This is what utils.initialize_encryption checks

        # Re-initialize
        app_logger.initialize_logger(self.config)

        # Check that the key file was NOT regenerated (i.e., content is the same)
        with open(self.test_key_file_path, 'rb') as f:
            current_key_content = f.read()
        self.assertEqual(original_key_content, current_key_content, "Encryption key was regenerated, not loaded.")
        self.assertIsNotNone(utils._CIPHER_SUITE, "Cipher suite not initialized after loading key.")


    def test_08_log_directory_path_resolution(self):
        """Test how log_directory paths (relative/absolute) are handled."""
        # Case 1: log_directory is relative, config_file_path is set
        # This is the default self.config setup.
        expected_daily_dir_rel, _, _ = self._get_expected_daily_dir_paths() # Uses self.config
        actual_daily_dir_rel, _ = app_logger.ensure_daily_log_dir(self.config)
        self.assertEqual(os.path.abspath(actual_daily_dir_rel), os.path.abspath(expected_daily_dir_rel))

        # Case 2: log_directory is absolute
        abs_log_dir = os.path.abspath(os.path.join(self.test_suite_dir, "AbsoluteLogs"))
        config_abs = self.config.copy()
        config_abs['log_directory'] = abs_log_dir

        # Re-initialize logger for this config (especially for key path if it's relative to log dir)
        # For this test, let's keep key path absolute to avoid complexity.
        utils._CIPHER_SUITE = None; utils._ENCRYPTION_KEY_BYTES = None; app_logger.cipher_suite = None
        app_logger.initialize_logger(config_abs) # Key will be re-verified/loaded

        today_str = datetime.date.today().strftime('%Y%m%d')
        expected_daily_dir_abs = os.path.join(abs_log_dir, today_str)
        actual_daily_dir_abs, _ = app_logger.ensure_daily_log_dir(config_abs)
        self.assertEqual(os.path.abspath(actual_daily_dir_abs), os.path.abspath(expected_daily_dir_abs))
        self.assertTrue(os.path.isdir(actual_daily_dir_abs))
        if os.path.exists(abs_log_dir): shutil.rmtree(abs_log_dir) # Clean up this specific dir


        # Case 3: log_directory is relative, config_file_path is None (fallback to CWD)
        # This is harder to test reliably without changing CWD and affecting other things.
        # The current logger code:
        # if config_file_location: base_log_dir = os.path.join(os.path.dirname(config_file_location), base_log_dir)
        # else: base_log_dir = os.path.abspath(base_log_dir) # relative to CWD
        # So, if config_file_path is None, log_directory becomes relative to CWD.

        config_no_cfg_path = self.config.copy()
        config_no_cfg_path['log_directory'] = "CwdRelativeLogs" # A new relative path
        config_no_cfg_path.pop('config_file_path', None) # Remove the key

        # Re-initialize logger
        utils._CIPHER_SUITE = None; utils._ENCRYPTION_KEY_BYTES = None; app_logger.cipher_suite = None
        # Key file path in config_no_cfg_path is still absolute, so that's fine.
        app_logger.initialize_logger(config_no_cfg_path)

        original_cwd = os.getcwd()
        os.chdir(self.test_suite_dir) # Change CWD to a known location

        expected_base_cwd_log_dir = os.path.join(self.test_suite_dir, "CwdRelativeLogs")
        expected_daily_cwd_log_dir = os.path.join(expected_base_cwd_log_dir, today_str)

        actual_daily_dir_cwd, _ = app_logger.ensure_daily_log_dir(config_no_cfg_path)
        self.assertEqual(os.path.abspath(actual_daily_dir_cwd), os.path.abspath(expected_daily_cwd_log_dir))
        self.assertTrue(os.path.isdir(actual_daily_dir_cwd))

        os.chdir(original_cwd) # Restore CWD
        if os.path.exists(expected_base_cwd_log_dir): shutil.rmtree(expected_base_cwd_log_dir)


if __name__ == '__main__':
    unittest.main()
