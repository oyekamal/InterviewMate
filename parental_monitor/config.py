# Handles loading and managing configuration from config.yaml
import yaml
import os

DEFAULT_CONFIG = {
    'screenshot_interval_minutes': 5,
    'keyword_filters': {
        'include_processes': ["chrome", "firefox", "slack", "msedge", "brave"],
        'exclude_words': ["password", "secret", "pswd"]
    },
    'log_directory': 'ParentalMonitorData',
    'encryption_key_file': 'encryption.key' # Path to file storing the encryption key
}

CONFIG_FILE_NAME = 'config.yaml'

def get_config_path():
    # For MVP, config could be in the application directory or a user-specific directory.
    # Let's assume it's in the same directory as the script or a predefined system location.
    # For now, let's try to find it in the current working directory or script's directory.

    # Check current working directory
    cwd_config_path = os.path.join(os.getcwd(), CONFIG_FILE_NAME)
    if os.path.exists(cwd_config_path):
        return cwd_config_path

    # Check script's directory (if different from CWD)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_dir_config_path = os.path.join(script_dir, CONFIG_FILE_NAME)
    if os.path.exists(script_dir_config_path):
        return script_dir_config_path

    # Default path if not found (e.g., for initial setup or if packaged)
    # This might need to be adjusted based on installation location.
    # For Windows: %ProgramFiles%/ParentalMonitor
    # For Linux: /opt/parental-monitor
    if os.name == 'nt': # Windows
        program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
        app_dir = os.path.join(program_files, 'ParentalMonitor')
    else: # Linux/other
        app_dir = '/opt/parental-monitor'

    os.makedirs(app_dir, exist_ok=True) # Ensure directory exists if we decide to write a default one here
    return os.path.join(app_dir, CONFIG_FILE_NAME)


def load_config():
    """Loads configuration from config.yaml."""
    config_path = get_config_path()
    config = DEFAULT_CONFIG.copy()

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Deep merge would be better for nested dicts like keyword_filters
                    for key, value in user_config.items():
                        if isinstance(value, dict) and isinstance(config.get(key), dict):
                            config[key].update(value)
                        else:
                            config[key] = value
            print(f"Loaded configuration from {config_path}")
        else:
            print(f"Configuration file not found at {config_path}. Using default configuration.")
            # Optionally, create a default config file here if it doesn't exist
            # save_config(config, config_path)
    except Exception as e:
        print(f"Error loading configuration: {e}. Using default configuration.")
        # Log this error to error.log as well

    # Ensure essential directories exist
    log_dir = config.get('log_directory', DEFAULT_CONFIG['log_directory'])
    if not os.path.isabs(log_dir): # If relative path, make it relative to a base dir
        # For now, let's assume relative to where the app is run or installed.
        # This needs refinement based on install location.
        # Example: base_dir = os.path.dirname(get_config_path())
        # log_dir = os.path.join(base_dir, log_dir)
        pass # Keep as relative for now, logger module will handle absolute path creation

    return config

def save_config(config_data, config_path=None):
    """Saves configuration to config.yaml."""
    if config_path is None:
        config_path = get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, sort_keys=False)
        print(f"Configuration saved to {config_path}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        # Log this error

if __name__ == '__main__':
    # Example usage:
    config = load_config()
    print("Current configuration:", config)

    # Example of saving a default config if it doesn't exist
    # config_p = get_config_path()
    # if not os.path.exists(config_p):
    #     print(f"Creating default config at {config_p}")
    #     save_config(DEFAULT_CONFIG, config_p)

    # print(f"Log directory will be: {os.path.abspath(config['log_directory'])}")
    # print(f"Screenshot interval: {config['screenshot_interval_minutes']} minutes")
    # print(f"Include processes: {config['keyword_filters']['include_processes']}")
    # print(f"Exclude words: {config['keyword_filters']['exclude_words']}")
