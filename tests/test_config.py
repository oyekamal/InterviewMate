import unittest
import os
import yaml
import shutil # For cleaning up created test files/dirs

# Adjust import path to access parental_monitor package
# This assumes tests are run from the root directory of the project (ParentalMonitor/)
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parental_monitor import config as app_config

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test config files
        self.test_dir = "temp_test_config_dir"
        os.makedirs(self.test_dir, exist_ok=True)

        # Store original CWD and change to test_dir to simulate running from different locations
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Path for a dummy config file
        self.test_config_file_name = "test_config.yaml" # app_config.CONFIG_FILE_NAME
        self.test_config_path = os.path.abspath(self.test_config_file_name)

        # Default config for comparison
        self.default_config = app_config.DEFAULT_CONFIG.copy()

        # Clean up any existing test config file before each test
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

        # Reset any cached path in config module (if any, not explicitly in current version but good practice)
        # For example, if app_config.get_config_path() had caching.

    def tearDown(self):
        # Change back to original CWD
        os.chdir(self.original_cwd)
        # Clean up: remove the temporary directory and its contents
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # pass

    def test_01_load_default_config_when_file_missing(self):
        """Test that default configuration is loaded if config.yaml is not found."""
        # Ensure file does not exist (done in setUp, but double check)
        self.assertFalse(os.path.exists(self.test_config_path), "Test config file should not exist for this test.")

        # Mock get_config_path to return path within our controlled test_dir
        original_get_config_path = app_config.get_config_path
        app_config.get_config_path = lambda: self.test_config_path

        loaded_cfg = app_config.load_config()

        # Restore original function
        app_config.get_config_path = original_get_config_path

        self.assertEqual(loaded_cfg['screenshot_interval_minutes'], self.default_config['screenshot_interval_minutes'])
        self.assertEqual(loaded_cfg['log_directory'], self.default_config['log_directory'])
        self.assertDictEqual(loaded_cfg['keyword_filters'], self.default_config['keyword_filters'])

    def test_02_load_custom_config_from_file(self):
        """Test loading custom configuration from an existing config.yaml."""
        custom_settings = {
            'screenshot_interval_minutes': 10,
            'log_directory': 'MyCustomLogs',
            'keyword_filters': {
                'include_processes': ['custom_app', 'another_app'],
                'exclude_words': ['confidential']
            },
            'new_custom_key': 'custom_value' # Test adding a new key
        }
        with open(self.test_config_path, 'w') as f:
            yaml.dump(custom_settings, f)

        self.assertTrue(os.path.exists(self.test_config_path))

        original_get_config_path = app_config.get_config_path
        app_config.get_config_path = lambda: self.test_config_path
        loaded_cfg = app_config.load_config()
        app_config.get_config_path = original_get_config_path

        self.assertEqual(loaded_cfg['screenshot_interval_minutes'], 10)
        self.assertEqual(loaded_cfg['log_directory'], 'MyCustomLogs')
        self.assertIn('custom_app', loaded_cfg['keyword_filters']['include_processes'])
        self.assertIn('confidential', loaded_cfg['keyword_filters']['exclude_words'])
        self.assertEqual(loaded_cfg['new_custom_key'], 'custom_value')
        # Check if default keys not in custom_settings are still present (e.g., encryption_key_file)
        self.assertEqual(loaded_cfg['encryption_key_file'], self.default_config['encryption_key_file'])


    def test_03_partial_custom_config_merges_with_defaults(self):
        """Test that a partial custom config merges correctly with defaults."""
        partial_settings = {
            'screenshot_interval_minutes': 15
            # log_directory and keyword_filters should come from defaults
        }
        with open(self.test_config_path, 'w') as f:
            yaml.dump(partial_settings, f)

        original_get_config_path = app_config.get_config_path
        app_config.get_config_path = lambda: self.test_config_path
        loaded_cfg = app_config.load_config()
        app_config.get_config_path = original_get_config_path

        self.assertEqual(loaded_cfg['screenshot_interval_minutes'], 15)
        self.assertEqual(loaded_cfg['log_directory'], self.default_config['log_directory']) # Should be default
        self.assertDictEqual(loaded_cfg['keyword_filters'], self.default_config['keyword_filters']) # Should be default


    def test_04_nested_keyword_filters_merge(self):
        """Test that nested keyword_filters are merged, not just overwritten."""
        custom_filters = {
            'keyword_filters': {
                'include_processes': ['only_this_app'], # Overwrites default include_processes
                # exclude_words should come from default
            }
        }
        with open(self.test_config_path, 'w') as f:
            yaml.dump(custom_filters, f)

        original_get_config_path = app_config.get_config_path
        app_config.get_config_path = lambda: self.test_config_path
        loaded_cfg = app_config.load_config()
        app_config.get_config_path = original_get_config_path

        self.assertEqual(loaded_cfg['keyword_filters']['include_processes'], ['only_this_app'])
        # Default exclude_words should still be there because the custom config didn't specify exclude_words
        self.assertEqual(loaded_cfg['keyword_filters']['exclude_words'], self.default_config['keyword_filters']['exclude_words'])

    def test_05_save_config(self):
        """Test saving a configuration to a file."""
        config_to_save = {
            'screenshot_interval_minutes': 20,
            'log_directory': 'SavedLogs',
            'keyword_filters': {'include_processes': ['saved_app'], 'exclude_words': ['saved_secret']},
            'encryption_key_file': 'saved.key'
        }

        # Use a different path for saving to avoid conflict with load tests' self.test_config_path
        save_path = os.path.abspath("saved_test_config.yaml")
        if os.path.exists(save_path): os.remove(save_path)

        app_config.save_config(config_to_save, save_path)
        self.assertTrue(os.path.exists(save_path))

        with open(save_path, 'r') as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data['screenshot_interval_minutes'], 20)
        self.assertEqual(saved_data['log_directory'], 'SavedLogs')
        self.assertEqual(saved_data['keyword_filters']['include_processes'], ['saved_app'])

        if os.path.exists(save_path):
            os.remove(save_path)

    def test_06_get_config_path_priority(self):
        """
        Test the get_config_path logic.
        1. CWD
        2. Script's directory (mocked)
        3. System-specific default path (mocked for predictability)
        """
        original_getcwd = os.getcwd
        original_path_exists = os.path.exists
        original_script_dir_func = app_config.os.path.dirname # used inside get_config_path via __file__
        original_abspath_func = app_config.os.path.abspath
        original_environ_get = os.environ.get
        original_makedirs = os.makedirs

        # --- Test 1: Config in CWD ---
        # CWD is self.test_dir (from setUp)
        # Create a dummy config file in CWD
        dummy_cwd_config_path = os.path.join(self.test_dir, app_config.CONFIG_FILE_NAME)
        with open(dummy_cwd_config_path, 'w') as f: f.write("test: cwd_config")

        # Ensure get_config_path points to our test CWD's config
        # Temporarily make os.getcwd() return self.test_dir for get_config_path()
        app_config.os.getcwd = lambda: self.test_dir
        # And ensure os.path.exists for this path returns True
        app_config.os.path.exists = lambda p: p == dummy_cwd_config_path or original_path_exists(p)

        found_path = app_config.get_config_path()
        self.assertEqual(found_path, dummy_cwd_config_path, "Should find config in CWD first.")

        os.remove(dummy_cwd_config_path) # Clean up

        # --- Test 2: Config in script's directory (mocked __file__) ---
        # Make CWD config not exist
        app_config.os.path.exists = lambda p: p != dummy_cwd_config_path and original_path_exists(p)

        # Mock script's directory
        mock_script_parent_dir = os.path.join(self.test_dir, "mock_script_location")
        mock_script_config_path = os.path.join(mock_script_parent_dir, app_config.CONFIG_FILE_NAME)
        os.makedirs(mock_script_parent_dir, exist_ok=True)
        with open(mock_script_config_path, 'w') as f: f.write("test: script_dir_config")

        # Mock __file__ for config.py to be inside mock_script_parent_dir
        # This is tricky as __file__ is module-level. We'll mock os.path.dirname(os.path.abspath(__file__))
        app_config.os.path.dirname = lambda p: mock_script_parent_dir if app_config.CONFIG_FILE_NAME in p else original_script_dir_func(p)
        app_config.os.path.abspath = lambda p: os.path.join(mock_script_parent_dir, os.path.basename(p)) if app_config.CONFIG_FILE_NAME in p else original_abspath_func(p)

        # Ensure os.path.exists for script path returns True, for CWD returns False
        app_config.os.path.exists = lambda p: (p == mock_script_config_path) or \
                                            (p != dummy_cwd_config_path and original_path_exists(p))

        found_path = app_config.get_config_path()
        self.assertEqual(found_path, mock_script_config_path, "Should find config in script's directory.")

        shutil.rmtree(mock_script_parent_dir) # Clean up

        # --- Test 3: Default system path (mocked) ---
        # Make CWD and script dir configs not exist
        app_config.os.path.exists = lambda p: p not in [dummy_cwd_config_path, mock_script_config_path] and \
                                             original_path_exists(p)
        app_config.os.path.dirname = original_script_dir_func # Restore
        app_config.os.path.abspath = original_abspath_func # Restore

        # Mock os.name and ProgramFiles for predictability
        original_os_name = os.name

        # Mock for Windows
        os.name = 'nt'
        mock_program_files = os.path.join(self.test_dir, "ProgramFiles", "ParentalMonitor")
        expected_win_path = os.path.join(mock_program_files, app_config.CONFIG_FILE_NAME)
        os.environ.get = lambda key, default: os.path.join(self.test_dir, "ProgramFiles") if key == 'ProgramFiles' else original_environ_get(key, default)
        # Mock makedirs to prevent actual creation outside test_dir
        app_config.os.makedirs = lambda p, exist_ok=True: None if p == mock_program_files else original_makedirs(p, exist_ok=exist_ok)

        found_path_win = app_config.get_config_path()
        self.assertEqual(found_path_win, expected_win_path, "Should use Windows default path.")

        # Mock for Linux
        os.name = 'posix'
        mock_opt_dir = "/opt/parental-monitor" # Standard Linux path
        expected_linux_path = os.path.join(mock_opt_dir, app_config.CONFIG_FILE_NAME)
        app_config.os.makedirs = lambda p, exist_ok=True: None if p == mock_opt_dir else original_makedirs(p, exist_ok=exist_ok)

        found_path_linux = app_config.get_config_path()
        self.assertEqual(found_path_linux, expected_linux_path, "Should use Linux default path.")

        # Restore all mocked functions and variables
        os.name = original_os_name
        app_config.os.getcwd = original_getcwd
        app_config.os.path.exists = original_path_exists
        os.environ.get = original_environ_get
        app_config.os.makedirs = original_makedirs


if __name__ == '__main__':
    unittest.main()
