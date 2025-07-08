# Linux Installer Creation Guide (Conceptual)

This guide outlines the steps to create a DEB package for the Parental Monitor application on Debian/Ubuntu systems. Similar principles apply for RPMs on Fedora/CentOS using `fpm`.

## Tools

*   **PyInstaller**: To bundle the Python application into a standalone executable or folder.
*   **fpm** (recommended for ease of use) or standard Debian packaging tools (`dh-make`, `dpkg-buildpackage`): To create the `.deb` package.

## Steps

1.  **Bundle with PyInstaller:**
    *   Create a `.spec` file for PyInstaller.
        *   Bundle `parental_monitor.main` as the entry point.
        *   Include necessary data files (e.g., `config.yaml.example`).
        *   The output should ideally be a one-folder bundle (e.g., `dist/ParentalMonitorApp`).
    *   Command: `pyinstaller parental_monitor.spec` (run on Linux target or compatible environment).

2.  **Prepare Package Contents:**
    *   Create a staging directory (e.g., `staging_dir`).
    *   Inside `staging_dir`, replicate the target file system structure:
        ```
        staging_dir/
        ├── opt/
        │   └── parental-monitor/  # Installation directory
        │       ├── ParentalMonitorApp/ (from PyInstaller dist)
        │       │   ├── parental_monitor_main (executable)
        │       │   ├── ... (other bundled files)
        │       └── config.yaml.example
        └── etc/
            └── systemd/
                └── system/
                    └── parental-monitor.service (copy from scripts/)
        ```
    *   Ensure `parental-monitor.service` has correct `ExecStart` and `WorkingDirectory` paths pointing to `/opt/parental-monitor/ParentalMonitorApp/parental_monitor_main`.

3.  **Create Control Files (for DEB using `fpm` or standard tools):**
    *   **`control` file:** Contains package metadata (Name, Version, Maintainer, Description, Dependencies).
        *   Example Dependencies: `python3`, `xdotool`, `xprop`, `scrot | gnome-screenshot` (latter is tricky for auto-deps, might need manual user instruction or post-install check).
    *   **`postinst` script:** Post-installation script.
        *   Enable and start the systemd service:
            ```bash
            #!/bin/sh
            set -e
            systemctl enable parental-monitor.service
            systemctl daemon-reload # In case service file is new/changed
            systemctl restart parental-monitor.service # Use restart to ensure it starts even if already running/failed
            echo "Parental Monitor service installed and started."
            echo "Please configure by copying /opt/parental-monitor/config.yaml.example to /opt/parental-monitor/config.yaml"
            echo "Then edit config.yaml, especially 'eula_accepted: true' to enable monitoring."
            exit 0
            ```
    *   **`prerm` script:** Pre-removal script.
        *   Stop and disable the systemd service:
            ```bash
            #!/bin/sh
            set -e
            systemctl stop parental-monitor.service || true # Ignore error if not running
            systemctl disable parental-monitor.service || true # Ignore error if not enabled
            exit 0
            ```
    *   **`postrm` script:** Post-removal script.
        *   `systemctl daemon-reload` if service file was removed by package manager.
        *   Clean up (e.g., if logs/config were not in `/opt/parental-monitor` and need explicit removal, though generally package manager handles files it installed).

4.  **Build the DEB package with `fpm`:**
    *   Example `fpm` command:
        ```bash
        fpm -s dir -t deb -n parental-monitor -v 1.0.0 \
            -C staging_dir \
            --description "Parental Monitor application" \
            --maintainer "Your Name <you@example.com>" \
            --vendor "YourCompany" \
            --license "Proprietary" \
            --architecture amd64 \
            --depends python3 \
            --depends xdotool \
            --depends xprop \
            --depends scrot \
            --depends libxss1 # Example: pyscreenshot might need scrot, which might need libxss1 for idle time
            --post-install scripts/postinst.sh \
            --pre-uninstall scripts/prerm.sh \
            --post-uninstall scripts/postrm.sh \
            opt etc # Paths from staging_dir to include
        ```
    *   This creates `parental-monitor_1.0.0_amd64.deb`.

5.  **Alternative: Using standard Debian tools:**
    *   Use `dh-make` to create a Debian packaging skeleton.
    *   Populate `debian/control`, `debian/rules`, `debian/install`, `debian/*.service`, `debian/postinst`, etc.
    *   Run `dpkg-buildpackage -us -uc`. This is more complex but offers finer control.

## Post-Installation Steps for User

1.  Install the DEB package: `sudo dpkg -i parental-monitor_1.0.0_amd64.deb && sudo apt-get install -f` (the latter to fix dependencies if needed).
2.  The `postinst` script should have enabled and started the service.
3.  User must configure:
    *   Copy `/opt/parental-monitor/config.yaml.example` to `/opt/parental-monitor/config.yaml`.
    *   Edit `/opt/parental-monitor/config.yaml`:
        *   Set `log_directory` (absolute path recommended, ensure service user has write access).
        *   Set `encryption_key_file` (absolute path recommended, ensure service user has write access to its dir for creation, and read access).
        *   Configure filters.
        *   **Crucially, set `eula_accepted: true`**.
    *   The service should create `encryption.key` on first run (if `eula_accepted` is true). User must secure this key.
    *   Service logs can be viewed with `journalctl -u parental-monitor.service`.

This guide provides a high-level overview. Actual implementation requires detailed scripting and testing.
