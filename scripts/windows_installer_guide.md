# Windows Installer Creation Guide (Conceptual)

This guide outlines the steps to create an MSI/EXE installer for the Parental Monitor application on Windows.

## Tools

*   **PyInstaller**: To bundle the Python application into a standalone executable.
*   **Inno Setup** (recommended) or **NSIS**: To create the installer package (MSI or EXE) that handles installation, service registration, and uninstallation.

## Steps

1.  **Bundle with PyInstaller:**
    *   Create a `.spec` file for PyInstaller to control the bundling process.
        *   Include all necessary data files (e.g., `config.yaml.example` if it needs to be deployed).
        *   Ensure platform-specific dependencies are correctly handled.
        *   The output should be a single executable or a one-folder bundle.
    *   Command: `pyinstaller parental_monitor.spec`
    *   The bundled app will be in the `dist/ParentalMonitor` (or similar) directory.

2.  **Create Windows Service Management Script (`scripts/windows_service.py`):**
    *   This Python script will use `pywin32` to:
        *   Define a class inheriting from `win32serviceutil.ServiceFramework`.
        *   Implement `SvcDoRun()`: This method will contain the main logic from `parental_monitor.main.main()`, adapted to run in a service context (e.g., initialize, start monitoring, wait for stop signal).
        *   Implement `SvcStop()`: This method will signal the `SvcDoRun` loop to terminate and call `stop_monitoring_services()`.
        *   Handle command-line arguments for `install`, `start`, `stop`, `remove`, `debug`.
    *   This script will be bundled by PyInstaller alongside the main application logic, or the main executable can be made service-aware. For simplicity, a separate service script is often easier to manage with PyInstaller if the main app also has CLI tools like decryption. *Self-correction: It's often better if the main executable can register itself as a service.* The `main.py` would need to be adapted to handle service control messages if not using a separate `windows_service.py` that imports the core logic. For MVP, let's assume `main.py` is made service-aware or a thin wrapper `windows_service.py` calls `main.main()`.

3.  **Create Inno Setup Script (`scripts/installer.iss`):**
    *   **[Setup] Section:**
        *   `AppName`, `AppVersion`, `DefaultDirName` (e.g., `{pf}\ParentalMonitor`).
        *   `OutputBaseFilename` (e.g., `ParentalMonitorSetup`).
        *   Request admin privileges (`PrivilegesRequired=admin`).
    *   **[Files] Section:**
        *   Copy all files from PyInstaller's `dist` folder to the installation directory (`{app}`).
        *   Copy `config.yaml.example` to `{app}`.
    *   **[Icons] Section:** (Optional for a background app, but good for uninstaller)
        *   Create Start Menu entry for uninstaller.
    *   **[Run] Section (Post-Installation):**
        *   Register the application as a Windows Service.
            *   Command: `"{app}\ParentalMonitorMain.exe" install` (if main executable is service-aware) OR `"{sys}\sc.exe" create ParentalMonitor binPath= "\"C:\path\to\your\service\executable.exe\"" start= auto` (less ideal, direct `sc` use).
            *   Better: `"{app}\ParentalMonitorServiceWrapper.exe" install --startup auto` (if using a dedicated service wrapper).
            *   Then: `"{app}\ParentalMonitorServiceWrapper.exe" start` OR `net start ParentalMonitor`.
        *   Guide user to configure `config.yaml` and `encryption.key` (e.g., by opening a README or the config file).
    *   **[UninstallRun] Section (During Uninstallation):**
        *   Stop the service: `"{app}\ParentalMonitorServiceWrapper.exe" stop` OR `net stop ParentalMonitor`.
        *   Remove the service: `"{app}\ParentalMonitorServiceWrapper.exe" remove` OR `"{sys}\sc.exe" delete ParentalMonitor`.
    *   **[Code] Section (Pascal Scripting - Optional but Powerful):**
        *   Could be used for more complex logic like checking for dependencies, gracefully stopping the app if running, etc.

4.  **Compile the Inno Setup script:**
    *   Use the Inno Setup Compiler to build the `installer.iss` script, which produces the final setup executable.

## Post-Installation Steps for User

1.  Navigate to `%ProgramFiles%\ParentalMonitor`.
2.  Copy `config.yaml.example` to `config.yaml`.
3.  Edit `config.yaml`:
    *   Set `log_directory` (absolute path recommended).
    *   Set `encryption_key_file` (absolute path recommended, outside `log_directory`).
    *   Configure filters.
    *   **Crucially, set `eula_accepted: true`**.
4.  The service should ideally create the `encryption.key` on its first run if it doesn't exist, based on the path in `config.yaml`. The user must secure this key.
5.  The service should start automatically on boot. If not, use `services.msc` or `net start ParentalMonitor`.

This guide provides a high-level overview. Actual implementation requires detailed scripting.
