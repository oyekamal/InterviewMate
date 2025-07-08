import time
import sys
import os
import argparse

# It's good practice to put these imports within a try-except if they are optional
# or if the script needs to run to a certain point even if some are missing (e.g. for CLI tools)
try:
    from . import config as app_config
    from . import logger as app_logger
    from . import keystroke_capture as ks_capture
    from . import screenshot_capture as ss_capture
    # utils is used by logger, direct import not strictly needed here unless for decryption CLI
    from . import utils as app_utils
except ImportError as e:
    # This might happen if running main.py directly without the package context.
    # For development, running as `python -m parental_monitor.main` is preferred.
    print(f"Error importing submodules: {e}. Ensure you are running this as part of the 'parental_monitor' package (e.g., using 'python -m parental_monitor.main').")
    sys.exit(1)

# Global flag to indicate if monitoring components are active
monitoring_active = False

def handle_keyword_log(config, keyword_data):
    """
    Formats and logs keyword data.
    keyword_data is a dict: {"app": app_name, "word": word, "title": window_title}
    """
    try:
        app_name = keyword_data.get("app", "unknown_app")
        word = keyword_data.get("word", "")
        title = keyword_data.get("title", "") # Window title can be quite long

        # For MVP, let's keep the log entry simpler as per spec, but title is good info
        # Spec: [2025-07-08 09:02:15] chrome.exe: "how to bake bread"
        # We can choose to include title or not. Let's include it for more context if available.
        if title and title != "Unknown Title" and title != "Error":
            log_entry = f"{app_name}: \"{word}\" (Window: {title[:100]})" # Truncate long titles
        else:
            log_entry = f"{app_name}: \"{word}\""

        app_logger.log_keyword(log_entry, config)
    except Exception as e:
        # Fallback logging if the main logger itself has an issue here.
        print(f"Error in handle_keyword_log: {e}")
        # Try to log to error.log as well
        try:
            app_logger.log_error(f"Exception in handle_keyword_log: {e}", config, is_critical=False)
        except:
            pass # Avoid recursion if error logging is also failing


def start_monitoring_services(config):
    """Starts keystroke and screenshot capture services."""
    global monitoring_active
    print("Starting monitoring services...")

    keystroke_started = False
    screenshot_started = False

    try:
        # Define the callback with the config partially applied
        keyword_callback = lambda kw_data: handle_keyword_log(config, kw_data)
        ks_capture.start_capture(config, keyword_callback)
        print("Keystroke capture service initiated.")
        keystroke_started = True
    except NotImplementedError as e:
        print(f"Keystroke capture not started: {e}")
        app_logger.log_error(f"Keystroke capture not started: {e}", config, is_critical=False)
    except Exception as e:
        print(f"Failed to start keystroke capture: {e}")
        app_logger.log_error(f"Failed to start keystroke capture: {e}", config, is_critical=True)

    try:
        ss_capture.start_screenshot_scheduler(config)
        print("Screenshot capture service initiated.")
        screenshot_started = True
    except NotImplementedError as e:
        print(f"Screenshot scheduler not started: {e}")
        app_logger.log_error(f"Screenshot scheduler not started: {e}", config, is_critical=False)
    except Exception as e:
        print(f"Failed to start screenshot scheduler: {e}")
        app_logger.log_error(f"Failed to start screenshot scheduler: {e}", config, is_critical=True)

    monitoring_active = keystroke_started or screenshot_started
    if not monitoring_active:
        print("No monitoring services could be started. Application might not log any data.")
        app_logger.log_error("No monitoring services could be started.", config, is_critical=True)
    else:
        print("Monitoring services are active.")
        app_logger.log_error("Monitoring services started.", config, is_critical=False) # Use error log as an event log too


def stop_monitoring_services():
    """Stops keystroke and screenshot capture services."""
    global monitoring_active
    if not monitoring_active:
        # print("Monitoring services were not active or already stopped.")
        return

    print("Stopping monitoring services...")
    try:
        ks_capture.stop_capture()
        print("Keystroke capture service stopped.")
    except Exception as e:
        print(f"Error stopping keystroke capture: {e}")
        # Try to log this, assuming logger is still functional
        try:
            app_logger.log_error(f"Error stopping keystroke capture: {e}", app_config.load_config(), is_critical=False)
        except: pass


    try:
        ss_capture.stop_screenshot_scheduler()
        print("Screenshot capture service stopped.")
    except Exception as e:
        print(f"Error stopping screenshot scheduler: {e}")
        try:
            app_logger.log_error(f"Error stopping screenshot scheduler: {e}", app_config.load_config(), is_critical=False)
        except: pass

    monitoring_active = False
    print("Monitoring services stopped.")
    try:
        app_logger.log_error("Monitoring services stopped.", app_config.load_config(), is_critical=False)
    except: pass


def run_decryption_tool(args, config_for_paths):
    """Handles command-line decryption tasks."""
    # Key file path must be provided for decryption
    if not args.keyfile or not os.path.exists(args.keyfile):
        print(f"Error: Valid encryption key file must be provided via --keyfile. Path given: {args.keyfile}")
        sys.exit(1)

    # No need to initialize the full logger or utils encryption here,
    # as the decryption functions in app_logger handle key loading themselves.
    # However, app_logger.initialize_logger is what sets up the utils cipher.
    # The decryption functions in logger.py load the key directly.

    if args.decrypt_keywords:
        if not os.path.exists(args.decrypt_keywords):
            print(f"Error: Encrypted keyword log file not found: {args.decrypt_keywords}")
            sys.exit(1)
        print(f"Decrypting keyword log: {args.decrypt_keywords} using key: {args.keyfile}")
        try:
            app_logger.decrypt_keyword_log(args.decrypt_keywords, args.keyfile)
        except Exception as e:
            print(f"Failed to decrypt keyword log: {e}")
            # Potentially log to error.log if logger is available and it makes sense for CLI tool
            # app_logger.log_error(f"CLI Decryption failed for keywords log {args.decrypt_keywords}: {e}", config_for_paths, is_critical=False)

    elif args.decrypt_screenshot:
        if not os.path.exists(args.decrypt_screenshot):
            print(f"Error: Encrypted screenshot file not found: {args.decrypt_screenshot}")
            sys.exit(1)
        if not args.output:
            print("Error: Output path --output must be specified for decrypted screenshot.")
            sys.exit(1)

        # Ensure output directory exists
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")
            except Exception as e:
                print(f"Error creating output directory {output_dir}: {e}")
                sys.exit(1)

        print(f"Decrypting screenshot: {args.decrypt_screenshot} to {args.output} using key: {args.keyfile}")
        try:
            app_logger.decrypt_screenshot(args.decrypt_screenshot, args.keyfile, args.output)
        except Exception as e:
            print(f"Failed to decrypt screenshot: {e}")
            # app_logger.log_error(f"CLI Decryption failed for screenshot {args.decrypt_screenshot}: {e}", config_for_paths, is_critical=False)
    else:
        print("No decryption action specified.")


def main():
    parser = argparse.ArgumentParser(description="Parental Monitor Application.")
    parser.add_argument('--decrypt-keywords', type=str, metavar='LOG_FILE', help='Path to encrypted keywords.log.enc to decrypt.')
    parser.add_argument('--decrypt-screenshot', type=str, metavar='SCREENSHOT_FILE', help='Path to encrypted screenshot.png.enc to decrypt.')
    parser.add_argument('--keyfile', type=str, metavar='KEY_FILE', help='Path to the encryption key file (required for decryption).')
    parser.add_argument('--output', type=str, metavar='OUTPUT_FILE', help='Output path for decrypted screenshot.')
    # Could add a --config argument to specify config file path if needed for decryption tools (e.g. to find default key path)

    args = parser.parse_args()

    # Determine actual config path and store it for logger's relative path resolution.
    # This needs to happen before logger initialization.
    # We need a temporary config object or a way to pass this path to the logger.
    # Let's modify how config is loaded slightly or how logger gets this info.

    # Approach: Load config, then update it with its own path, then init logger.
    config_data = app_config.load_config() # This loads based on its internal search logic

    # To ensure logger uses the correct base for relative paths (log_directory, encryption_key_file),
    # we should tell it where the config file was actually found, if possible.
    # app_config.get_config_path() returns the path it would use.
    # Let's assume for now that load_config uses get_config_path internally.
    # We need to add the found config_path to the config_data dict.
    # The current config.py doesn't save the path it found.
    # A simple way: call get_config_path() again and add it.
    # This assumes get_config_path() is deterministic and efficient.

    # Get the path that load_config would have used (or did use if we trust it's consistent)
    # This path is primarily for resolving relative paths within the config file itself by the logger.
    # For CLI tools, if a config is needed (e.g. to find default key path), it would be loaded here.
    # For the main monitoring service, config_data is primary.

    # For decryption, we might not need a full config, just the key.
    # But if error logging from decryption is desired, logger needs init.
    # Let's initialize logger minimally for CLI tools too.

    # Tentative: Add the config file path to the loaded config
    # This is a bit of a chicken-and-egg if get_config_path itself needs parts of config.
    # config.py's get_config_path is standalone.
    actual_config_file_path = app_config.get_config_path() # Get the path that would be used
    config_data['config_file_path'] = actual_config_file_path # Add it for logger

    # Initialize logger (handles encryption key loading/generation)
    # This should happen for both monitoring mode and CLI tool mode if errors are to be logged.
    try:
        app_logger.initialize_logger(config_data)
    except Exception as e:
        # If logger init fails (e.g. bad key, unwritable key path), this is critical.
        print(f"CRITICAL: Failed to initialize logger: {e}. Application cannot continue.")
        # Further logging here might be impossible.
        sys.exit(1)


    if args.decrypt_keywords or args.decrypt_screenshot:
        if not args.keyfile: # If keyfile isn't given, try to get from config
            args.keyfile = os.path.join(os.path.dirname(config_data['config_file_path']), config_data['encryption_key_file'])
            print(f"Keyfile not specified, attempting to use from config: {args.keyfile}")
        run_decryption_tool(args, config_data) # Pass config_data for error logging context
        sys.exit(0)

    # --- Main Monitoring Logic ---
    print("Parental Monitor starting...")
    app_logger.log_error("Parental Monitor application starting.", config_data, is_critical=False)


    # EULA Check
    if not config_data.get('eula_accepted', False):
        message = "EULA not accepted. Please set 'eula_accepted: true' in config.yaml to enable monitoring."
        print(message)
        app_logger.log_error(message, config_data, is_critical=True)
        sys.exit(1)

    print("EULA accepted. Proceeding with monitoring.")
    app_logger.log_error("EULA accepted.", config_data, is_critical=False)

    try:
        start_monitoring_services(config_data)

        if monitoring_active:
            print("Application is now monitoring. Press Ctrl+C to stop (if running in console).")
            while True:
                # Keep main thread alive. Service managers will handle process lifetime.
                # When run directly, this allows daemon threads to work.
                time.sleep(30) # Check for interrupt every 30 seconds
        else:
            print("Monitoring could not be started. Exiting.")
            app_logger.log_error("Exiting due to failure to start monitoring services.", config_data, is_critical=True)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")
        app_logger.log_error("KeyboardInterrupt received, shutting down.", config_data, is_critical=False)
    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
        app_logger.log_error(f"Unexpected error in main: {e}", config_data, is_critical=True)
    finally:
        stop_monitoring_services()
        print("Parental Monitor shut down.")
        app_logger.log_error("Parental Monitor shut down.", config_data, is_critical=False)

if __name__ == "__main__":
    # This structure allows parental_monitor.main to be an entry point for packaging tools like PyInstaller
    main()
