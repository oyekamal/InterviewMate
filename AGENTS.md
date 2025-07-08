# Agent Instructions for ParentalMonitor Project

This document provides guidance for AI agents working on the ParentalMonitor project.

## Project Overview

ParentalMonitor is a lightweight background application for Windows and Ubuntu to capture user activity (keywords, screenshots) for parental review. Key aspects include cross-platform compatibility, background operation, local encrypted storage, and configuration via `config.yaml`.

Refer to `README.md` for a general project overview and `docs/MVP_SPEC.md` for the detailed requirements.

## Development Guidelines

1.  **Cross-Platform Compatibility**:
    *   Core logic should be platform-agnostic where possible (e.g., in `logger.py`, `config.py`).
    *   Platform-specific code must be isolated in designated modules (e.g., `keystroke_capture/windows.py`, `screenshot_capture/linux.py`).
    *   Use `sys.platform` or `os.name` for conditional execution of platform-specific code.
    *   Test thoroughly on both Windows and Ubuntu environments if making changes to platform-specific modules or their interfaces.

2.  **Configuration (`config.yaml`)**:
    *   All user-configurable settings should be managed through `config.yaml`.
    *   Refer to `config.yaml.example` for structure and default values.
    *   The `config.py` module handles loading and providing access to these settings. Ensure it gracefully handles missing or malformed config files by using defaults.

3.  **Logging and Data Storage (`logger.py`)**:
    *   All captured data (keywords, screenshots) must be encrypted using AES-256 via `utils.py`.
    *   The `encryption.key` is critical; ensure its handling is secure (though for MVP, it's a local file).
    *   Data is stored in a daily-rotated folder structure: `log_directory/YYYYMMDD/`.
        *   Keywords: `keywords.log.enc` (append-only, each entry encrypted separately).
        *   Screenshots: `Screenshots/YYYYMMDD_HHMMSS.png.enc`.
    *   Error logging should go to a separate, unencrypted `error.log` file, typically located outside the main data folders (e.g., in the application's root install directory or one level above `log_directory`).
    *   Permissions on log files and directories should be restrictive (e.g., 0700 for dirs, 0600 for files on POSIX).

4.  **Error Handling and Resilience**:
    *   The application must run as a background service/daemon and be resilient to errors.
    *   Implement auto-restart on crash (via Windows Service manager or systemd).
    *   Log errors comprehensively in `error.log`. Critical errors (e.g., failure to initialize logging/encryption) should be clearly indicated.
    *   Gracefully handle missing dependencies or tools (e.g., `xdotool` on Linux), logging the issue and disabling the affected feature if possible, rather than crashing the entire application.

5.  **Resource Usage**:
    *   The application must be lightweight (<5% CPU, <100MB RAM).
    *   Avoid busy-waiting or inefficient loops. Use appropriate threading and sleep mechanisms.
    *   Optimize image handling and file I/O.

6.  **Code Style and Structure**:
    *   Follow PEP 8 guidelines for Python code.
    *   Use clear, descriptive names for variables, functions, and modules.
    *   Add comments to explain complex logic or non-obvious decisions.
    *   Ensure platform-specific modules (`windows.py`, `linux.py`) in `keystroke_capture` and `screenshot_capture` directories implement a consistent interface defined or expected by their respective `__init__.py` files.

7.  **Dependencies**:
    *   Keep the number of external dependencies to a minimum.
    *   List all dependencies in `requirements.txt` (to be created/updated).
    *   Prefer well-maintained and widely used libraries.
        *   `PyYAML` for config.
        *   `cryptography` for encryption.
        *   `pynput` for keystroke capture.
        *   `Pillow` for screenshots on Windows.
        *   `psutil` for process information.
        *   `pygetwindow` for active window on Windows.
        *   `pyscreenshot` (or direct CLI tools like `scrot`, `gnome-screenshot`) for Linux screenshots.

8.  **Testing**:
    *   Write unit tests for core logic (config parsing, logging encryption/decryption, utility functions). Place tests in the `/tests` directory.
    *   Manually test platform-specific features (keystroke capture, screenshot capture, service/daemon operation) on both Windows and Ubuntu.
    *   Test edge cases, such as missing config files, incorrect configurations, or missing external tools (for Linux screenshots/window info).

9.  **Security & Privacy (MVP Focus)**:
    *   Primary focus is on local data encryption. No remote communication.
    *   The EULA/consent mechanism is via `eula_accepted: true` in `config.yaml`. Ensure the application checks this flag before starting any monitoring activity. (This check needs to be implemented in `main.py`).
    *   Do not log keystrokes if the identified application is not in `include_processes` (if the list is not empty).
    *   Do not log keywords that are in `exclude_words`.

10. **Task-Specific Notes**:
    *   When implementing `main.py`:
        *   It should initialize configuration and logging (including encryption) first.
        *   It must check `eula_accepted` from config. If false, it should log an informative message (to console and/or `error.log`) and exit or not start monitoring threads.
        *   It should start the keystroke listener thread and the screenshot scheduler thread.
        *   It needs a main loop that keeps the application alive (e.g., `while True: time.sleep(60)`), or rely on the non-daemon threads to do so. This is especially important when not running as a managed service.
        *   Implement graceful shutdown handling (e.g., on `KeyboardInterrupt` or SIGTERM), stopping threads and flushing any buffers.
    *   When creating installers:
        *   Windows: MSI/EXE via PyInstaller and Inno Setup/NSIS. Must install service.
        *   Ubuntu: DEB/AppImage via PyInstaller and fpm/dh-virtualenv. Must install systemd service.
        *   Install paths: `%ProgramFiles%\ParentalMonitor` (Win), `/opt/parental-monitor` (Linux).
        *   The installer should guide the user on configuring `config.yaml` (or place a default one) and creating/securing `encryption.key`.

## What NOT To Do

*   Do NOT implement any cloud synchronization or remote dashboard features for the MVP.
*   Do NOT add real-time alerting features (SMS, email) for the MVP.
*   Do NOT store the `encryption.key` in version control. Add `*.key` or the specific key filename to `.gitignore`.
*   Do NOT log passwords or other explicitly excluded keywords (ensure filters are effective).
*   Do NOT write platform-specific code outside the designated `windows.py`/`linux.py` modules without strong justification.

By following these guidelines, you will help ensure the ParentalMonitor project is developed consistently, securely, and meets the specified requirements.```python
# AGENTS.md
# Agent Instructions for ParentalMonitor Project

This document provides guidance for AI agents working on the ParentalMonitor project.

## Project Overview

ParentalMonitor is a lightweight background application for Windows and Ubuntu to capture user activity (keywords, screenshots) for parental review. Key aspects include cross-platform compatibility, background operation, local encrypted storage, and configuration via `config.yaml`.

Refer to `README.md` for a general project overview and `docs/MVP_SPEC.md` for the detailed requirements.

## Development Guidelines

1.  **Cross-Platform Compatibility**:
    *   Core logic should be platform-agnostic where possible (e.g., in `logger.py`, `config.py`).
    *   Platform-specific code must be isolated in designated modules (e.g., `keystroke_capture/windows.py`, `screenshot_capture/linux.py`).
    *   Use `sys.platform` or `os.name` for conditional execution of platform-specific code.
    *   Test thoroughly on both Windows and Ubuntu environments if making changes to platform-specific modules or their interfaces.

2.  **Configuration (`config.yaml`)**:
    *   All user-configurable settings should be managed through `config.yaml`.
    *   Refer to `config.yaml.example` for structure and default values.
    *   The `config.py` module handles loading and providing access to these settings. Ensure it gracefully handles missing or malformed config files by using defaults.

3.  **Logging and Data Storage (`logger.py`)**:
    *   All captured data (keywords, screenshots) must be encrypted using AES-256 via `utils.py`.
    *   The `encryption.key` is critical; ensure its handling is secure (though for MVP, it's a local file).
    *   Data is stored in a daily-rotated folder structure: `log_directory/YYYYMMDD/`.
        *   Keywords: `keywords.log.enc` (append-only, each entry encrypted separately).
        *   Screenshots: `Screenshots/YYYYMMDD_HHMMSS.png.enc`.
    *   Error logging should go to a separate, unencrypted `error.log` file, typically located outside the main data folders (e.g., in the application's root install directory or one level above `log_directory`).
    *   Permissions on log files and directories should be restrictive (e.g., 0700 for dirs, 0600 for files on POSIX).

4.  **Error Handling and Resilience**:
    *   The application must run as a background service/daemon and be resilient to errors.
    *   Implement auto-restart on crash (via Windows Service manager or systemd).
    *   Log errors comprehensively in `error.log`. Critical errors (e.g., failure to initialize logging/encryption) should be clearly indicated.
    *   Gracefully handle missing dependencies or tools (e.g., `xdotool` on Linux), logging the issue and disabling the affected feature if possible, rather than crashing the entire application.

5.  **Resource Usage**:
    *   The application must be lightweight (<5% CPU, <100MB RAM).
    *   Avoid busy-waiting or inefficient loops. Use appropriate threading and sleep mechanisms.
    *   Optimize image handling and file I/O.

6.  **Code Style and Structure**:
    *   Follow PEP 8 guidelines for Python code.
    *   Use clear, descriptive names for variables, functions, and modules.
    *   Add comments to explain complex logic or non-obvious decisions.
    *   Ensure platform-specific modules (`windows.py`, `linux.py`) in `keystroke_capture` and `screenshot_capture` directories implement a consistent interface defined or expected by their respective `__init__.py` files.

7.  **Dependencies**:
    *   Keep the number of external dependencies to a minimum.
    *   List all dependencies in `requirements.txt` (to be created/updated).
    *   Prefer well-maintained and widely used libraries.
        *   `PyYAML` for config.
        *   `cryptography` for encryption.
        *   `pynput` for keystroke capture.
        *   `Pillow` for screenshots on Windows.
        *   `psutil` for process information.
        *   `pygetwindow` for active window on Windows.
        *   `pyscreenshot` (or direct CLI tools like `scrot`, `gnome-screenshot`) for Linux screenshots.

8.  **Testing**:
    *   Write unit tests for core logic (config parsing, logging encryption/decryption, utility functions). Place tests in the `/tests` directory.
    *   Manually test platform-specific features (keystroke capture, screenshot capture, service/daemon operation) on both Windows and Ubuntu.
    *   Test edge cases, such as missing config files, incorrect configurations, or missing external tools (for Linux screenshots/window info).

9.  **Security & Privacy (MVP Focus)**:
    *   Primary focus is on local data encryption. No remote communication.
    *   The EULA/consent mechanism is via `eula_accepted: true` in `config.yaml`. Ensure the application checks this flag before starting any monitoring activity. (This check needs to be implemented in `main.py`).
    *   Do not log keystrokes if the identified application is not in `include_processes` (if the list is not empty).
    *   Do not log keywords that are in `exclude_words`.

10. **Task-Specific Notes**:
    *   When implementing `main.py`:
        *   It should initialize configuration and logging (including encryption) first.
        *   It must check `eula_accepted` from config. If false, it should log an informative message (to console and/or `error.log`) and exit or not start monitoring threads.
        *   It should start the keystroke listener thread and the screenshot scheduler thread.
        *   It needs a main loop that keeps the application alive (e.g., `while True: time.sleep(60)`), or rely on the non-daemon threads to do so. This is especially important when not running as a managed service.
        *   Implement graceful shutdown handling (e.g., on `KeyboardInterrupt` or SIGTERM), stopping threads and flushing any buffers.
    *   When creating installers:
        *   Windows: MSI/EXE via PyInstaller and Inno Setup/NSIS. Must install service.
        *   Ubuntu: DEB/AppImage via PyInstaller and fpm/dh-virtualenv. Must install systemd service.
        *   Install paths: `%ProgramFiles%\ParentalMonitor` (Win), `/opt/parental-monitor` (Linux).
        *   The installer should guide the user on configuring `config.yaml` (or place a default one) and creating/securing `encryption.key`.

## What NOT To Do

*   Do NOT implement any cloud synchronization or remote dashboard features for the MVP.
*   Do NOT add real-time alerting features (SMS, email) for the MVP.
*   Do NOT store the `encryption.key` in version control. Add `*.key` or the specific key filename to `.gitignore`.
*   Do NOT log passwords or other explicitly excluded keywords (ensure filters are effective).
*   Do NOT write platform-specific code outside the designated `windows.py`/`linux.py` modules without strong justification.

By following these guidelines, you will help ensure the ParentalMonitor project is developed consistently, securely, and meets the specified requirements.
```
