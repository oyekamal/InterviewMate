# Parental Monitor

Parental Monitor is a lightweight background application for Windows and Ubuntu designed to provide parents with visibility into their children's online activities. It captures keywords typed and periodic screenshots, storing them locally for review.

## MVP Features

*   **Keyword Logging**: Records typed keywords from browsers, chat applications, etc., into an encrypted `keywords.log` file.
*   **Screenshot Capture**: Takes full-screen screenshots at configurable intervals, saving them as encrypted PNG files.
*   **Local Storage**: All data is stored locally in a structured, timestamped folder hierarchy.
*   **Configuration**: A simple `config.yaml` file allows customization of screenshot intervals and keyword filters.
*   **Cross-Platform**: Supports Windows 10+ and Ubuntu 20.04+.
*   **Background Operation**: Runs as a Windows Service or a systemd daemon on Ubuntu.
*   **Encryption**: Log files and screenshots are encrypted at rest using AES-256.

## Project Structure

```
/ParentalMonitor/
├── parental_monitor/       # Main application source code
│   ├── __init__.py
│   ├── config.py           # Configuration loading (config.yaml)
│   ├── logger.py           # Data logging (keywords, screenshots), encryption
│   ├── keystroke_capture/  # Keystroke capture logic (platform-specific)
│   │   ├── __init__.py
│   │   ├── windows.py
│   │   └── linux.py
│   ├── screenshot_capture/ # Screenshot capture logic (platform-specific)
│   │   ├── __init__.py
│   │   ├── windows.py
│   │   └── linux.py
│   ├── utils.py            # Utility functions (encryption helpers)
│   └── main.py             # Main application entry point (to be created)
├── scripts/                # Helper scripts
│   └── parental-monitor.service # systemd service file for Linux
├── tests/                  # Unit and integration tests
│   ├── test_config.py
│   └── test_logger.py
├── config.yaml.example     # Example configuration file
├── README.md               # This file
├── AGENTS.md               # Instructions for AI agents
└── .gitignore              # Git ignore rules
```

## Setup and Installation (Conceptual - Details TBD)

**Prerequisites:**

*   Python 3.8+
*   pip (Python package installer)
*   **Windows**: May require Microsoft Visual C++ Redistributable. `pywin32` for service management.
*   **Linux**: `xdotool`, `xprop` (for active window detection by keystroke logger), `scrot` or `gnome-screenshot` (as fallback screenshot tool). `python3-dev`, `build-essential` (for some pip packages).

**General Steps (Manual/Development):**

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd ParentalMonitor
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt # (requirements.txt to be created)
    # Key dependencies: PyYAML, cryptography, pynput, Pillow, psutil, pygetwindow (Windows), pyscreenshot (Linux)
    ```

4.  **Configure the application:**
    *   Copy `config.yaml.example` to `config.yaml`.
    *   Edit `config.yaml` to set your desired `log_directory`, `screenshot_interval_minutes`, and filters.
    *   **Crucially**: Review the EULA section (or a separate EULA.txt if provided) and set `eula_accepted: true` in `config.yaml` to enable monitoring.
    *   The first run will generate an `encryption.key` file (or as specified by `encryption_key_file` in `config.yaml`). **Back up this key safely!**

5.  **Running the application (Development/Directly):**
    ```bash
    python -m parental_monitor.main # (Once main.py is created)
    ```

**Installation as a Service/Daemon (MVP - manual steps, to be automated by installers):**

*   **Windows:**
    *   The application will need to be packaged (e.g., with PyInstaller).
    *   A script will use `pywin32` to install it as a Windows Service, configured to run automatically.
    *   Installation directory: `%ProgramFiles%\ParentalMonitor`
*   **Ubuntu:**
    *   The application will need to be packaged (e.g., with PyInstaller and `fpm`).
    *   The `scripts/parental-monitor.service` file will be copied to `/etc/systemd/system/`.
    *   Commands like `sudo systemctl enable parental-monitor.service` and `sudo systemctl start parental-monitor.service` will be used.
    *   Installation directory: `/opt/parental-monitor`

## Data Storage

Logged data is stored in the directory specified by `log_directory` in `config.yaml`. The structure is:

```
/YourLogDirectory/
├── YYYYMMDD/                  # Folder for each day
│   ├── keywords.log.enc       # Encrypted keyword log
│   └── Screenshots/           # Folder for screenshots of that day
│       ├── YYYYMMDD_HHMMSS.png.enc
│       └── ...
├── YYYYMMDD_another_day/
│   └── ...
├── config.yaml                # (If log_directory is where config is also placed)
└── encryption.key             # (If encryption_key_file path makes it land here)
```

*   `keywords.log.enc`: Contains timestamped keyword entries, encrypted.
    *   Format before encryption: `[YYYY-MM-DD HH:MM:SS] process_name: "captured keywords"`
*   Screenshot files are named `YYYYMMDD_HHMMSS.png.enc` and are encrypted.
*   `error.log`: A separate, unencrypted log file for application errors, typically stored one level above the `log_directory` or in the application's installation directory.

## Decrypting Data (Manual Tool - TBD)

A separate utility script or command-line option in the main application will be provided to decrypt `keywords.log.enc` and screenshot files using the `encryption.key`.

Example (conceptual):
```bash
python -m parental_monitor.main --decrypt-keywords /path/to/YYYYMMDD/keywords.log.enc --keyfile /path/to/encryption.key
python -m parental_monitor.main --decrypt-screenshot /path/to/screenshot.png.enc --keyfile /path/to/encryption.key --output /path/to/decrypted_image.png
```
The `logger.py` already contains example decryption functions that can be adapted for this tool.

## Security and Privacy

*   **At-Rest Encryption**: AES-256 for logs and screenshots. The `encryption.key` is vital.
*   **Local Storage**: Data remains on the local machine in the MVP. No cloud sync.
*   **Permissions**: It's recommended to set restrictive OS-level permissions on the `log_directory` and `encryption.key` file, allowing access only to the parent's user account. The logger attempts to set 0700/0600 permissions on POSIX systems for created log files and directories.
*   **EULA & Consent**: The `eula_accepted` flag in `config.yaml` acts as a consent mechanism for the MVP. Parents must manually acknowledge this.

## Future Development (Post-MVP)

*   Remote dashboard / cloud synchronization.
*   Real-time alerting (e.g., SMS/email for specific keywords).
*   Detailed analytics and reporting UI.
*   Web interface for configuration and viewing logs.
*   More robust installer packages for all platforms.
*   Enhanced security for key management.

## Contributing

Contributions are not being accepted at this time.

## License

Refer to `EULA.txt` for licensing terms.
