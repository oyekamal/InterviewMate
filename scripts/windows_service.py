# Placeholder for Windows Service integration using pywin32
# This script would be responsible for defining the Windows service
# that runs the Parental Monitor application.

# This script would typically be bundled by PyInstaller along with the main app,
# or the main app executable itself would be made service-aware.

# Example structure (conceptual):

import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import os
import importlib # To potentially import main from the bundled app

# Assuming the main application logic is in `parental_monitor.main`
# If this script is at the root of the bundled app, paths might need adjustment.
# For a PyInstaller bundle, sys.frozen will be true.
if getattr(sys, 'frozen', False):
    # If run from PyInstaller bundle
    APPLICATION_PATH = os.path.dirname(sys.executable)
    # Need to add bundled 'parental_monitor' package to path if not already there
    # This depends on PyInstaller spec structure. Often, imports just work if main script is at root.
else:
    # If run as a normal script (development)
    APPLICATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, APPLICATION_PATH) # Ensure parental_monitor is importable

# It's better if parental_monitor.main.main() can be imported and run.
# Let's assume we can import the main function or relevant start/stop functions.
try:
    from parental_monitor import main as app_main
    from parental_monitor import config as app_config
    from parental_monitor import logger as app_logger # For service logging its own status
except ImportError:
    app_main = None
    app_config = None
    app_logger = None
    # Log this issue if possible, or raise error during service install
    # servicemanager.LogErrorMsg("ParentalMonitor Service: Failed to import core application modules.")


class ParentalMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ParentalMonitor"
    _svc_display_name_ = "Parental Monitor Service"
    _svc_description_ = "Monitors keyword and screen activity for parental review."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = False
        self._config = None # To store loaded config for logging

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        if app_main and hasattr(app_main, 'stop_monitoring_services'):
            try:
                # This call should ideally be quick and not block SvcStop for too long.
                # app_main.stop_monitoring_services() might need its own config if not global.
                servicemanager.LogInfoMsg(f"{self._svc_name_} - Stop signal received, attempting to stop monitoring.")
                app_main.stop_monitoring_services() # Call the main app's stop function
            except Exception as e:
                servicemanager.LogErrorMsg(f"{self._svc_name_} - Exception during stop_monitoring_services: {e}")
        servicemanager.LogInfoMsg(f"{self._svc_name_} - Service stop requested successfully.")


    def SvcDoRun(self):
        servicemanager.LogInfoMsg(f"{self._svc_name_} - Service starting.")
        self.is_running = True

        try:
            # It's crucial that paths are resolved correctly when running as a service.
            # The working directory for a service is usually C:\Windows\System32.
            # config.py's get_config_path() needs to find config.yaml in the install dir.
            # Ensure PyInstaller bundles config.yaml.example to the install dir,
            # and the user is instructed to create config.yaml there.

            # Load config and initialize logger (as done in main.py)
            # This is important because the service needs its own context for these.
            self._config = app_config.load_config()
            if self._config:
                actual_config_path = app_config.get_config_path()
                self._config['config_file_path'] = actual_config_path
                app_logger.initialize_logger(self._config)
                servicemanager.LogInfoMsg(f"{self._svc_name_} - Logger initialized. Config loaded from: {actual_config_path}")
            else:
                servicemanager.LogErrorMsg(f"{self._svc_name_} - Failed to load configuration. Service might not function correctly.")
                # Decide if service should stop or try to run with defaults (current load_config uses defaults)

            # EULA Check (critical for service to run)
            if not self._config.get('eula_accepted', False):
                msg = f"{self._svc_name_} - EULA not accepted in config. Service will not start monitoring."
                servicemanager.LogErrorMsg(msg)
                app_logger.log_error(msg, self._config, is_critical=True) # Also to file log
                self.SvcStop() # Stop the service if EULA not accepted.
                return

            servicemanager.LogInfoMsg(f"{self._svc_name_} - EULA accepted. Proceeding to start monitoring.")

            if app_main and hasattr(app_main, 'start_monitoring_services') and hasattr(app_main, 'handle_keyword_log'):
                # The main app's start_monitoring_services function should start threads.
                # The service's SvcDoRun then just needs to wait for a stop signal.
                app_main.start_monitoring_services(self._config) # Pass the loaded config
                servicemanager.LogInfoMsg(f"{self._svc_name_} - Monitoring services initiated by app_main.")
            else:
                servicemanager.LogErrorMsg(f"{self._svc_name_} - app_main or its functions not found. Cannot start monitoring.")
                self.SvcStop()
                return

            servicemanager.LogInfoMsg(f"{self._svc_name_} - Service is running.")

            # Wait for stop signal
            while self.is_running:
                rc = win32event.WaitForSingleObject(self.hWaitStop, 5000) # Wait 5 seconds
                if rc == win32event.WAIT_OBJECT_0:
                    # Stop event was signaled
                    break
            servicemanager.LogInfoMsg(f"{self._svc_name_} - Service run loop ended.")

        except Exception as e:
            servicemanager.LogErrorMsg(f"{self._svc_name_} - Unhandled exception in SvcDoRun: {e}")
            # Also log to file via app_logger if available
            if self._config and app_logger:
                 app_logger.log_error(f"Service SvcDoRun unhandled exception: {e}", self._config, is_critical=True)
            # This will cause the service to stop.
            # The service controller will then restart it based on recovery options.

def handle_service_command():
    if len(sys.argv) == 1:
        # Called by SCM, try to start the service.
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(ParentalMonitorService)
            servicemanager.StartServiceCtrlDispatcher()
        except win32service.error as details:
            if details.winerror == win32service.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                # Not called by SCM, perhaps user double-clicked executable
                print("This is a Windows service. Use install/start/stop/remove commands or manage via services.msc.")
                print("Or run 'python windows_service.py debug' to run in console.")
    else:
        # Called from command line (install, start, stop, remove, debug)
        # Ensure current directory is the script's directory for pywin32 to find the service class
        # This is important if PyInstaller puts this script somewhere nested.
        # However, win32serviceutil.HandleCommandLine should work if the class is defined in __main__
        # when this script is executed.

        # If this script is `scripts/windows_service.py` and run directly for install,
        # it needs to correctly register the *bundled* executable, not itself as a .py file.
        # This is a common complexity. The installer (Inno Setup) should handle registration
        # using the bundled .exe, which itself should be service-aware.

        # For now, let's make this script executable for direct pywin32 commands.
        # This means if you `python windows_service.py install`, it registers *python.exe*
        # running *this script*, which is okay for development but not for deployment.
        # Deployed version should have the main .exe handle these.

        # To make the main .exe service-aware, its main() would look like:
        # if len(sys.argv) > 1 and sys.argv[1] in ['install', 'start', ...]:
        #     win32serviceutil.HandleCommandLine(MyServiceClass) # MyServiceClass defined in main.py
        # else:
        #     # Normal app startup or SCM dispatcher start

        # For this placeholder, assume direct execution for dev/debug:
        win32serviceutil.HandleCommandLine(ParentalMonitorService)


if __name__ == '__main__':
    handle_service_command()

# To install (dev): python windows_service.py install
# To start: python windows_service.py start
# To stop: python windows_service.py stop
# To remove: python windows_service.py remove
# To debug (run in console): python windows_service.py debug
#
# For deployed app, the installer (e.g. Inno Setup) would execute:
# YourApp.exe install
# YourApp.exe start
# (Assuming YourApp.exe is built from a script like this or main.py adapted for it)
