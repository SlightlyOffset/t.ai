"""
t.ai - Primary Entry Point and Environment Setup.
Performs dependency checks and ensures the required environment is prepared
before launching the Textual User Interface (TUI) from menu.py.
"""

import os
import sys
import platform

def check_python_version():
    """Ensure the user is running Python 3.10+."""
    if sys.version_info < (3, 10):
        print(f"[CRITICAL] t.ai requires Python 3.10 or higher. Your version: {sys.version.split()[0]}")
        sys.exit(1)

def ensure_directories():
    """Automatically create necessary folders if they don't exist."""
    required_dirs = [
        "profiles",
        "user_profiles",
        "history",
        "img",
        "cache",
        "voices",
        "template",
        "response_rule",
        "lorebooks"
    ]
    for directory in required_dirs:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"[SETUP] Created missing directory: {directory}")
            except Exception as e:
                print(f"[ERROR] Failed to create directory '{directory}': {e}")

def check_dependencies():
    """Verify that all core third-party libraries are installed."""
    required_libraries = {
        "textual": "textual",
        "ollama": "ollama",
        "requests": "requests",
        "colorama": "colorama",
        "edge_tts": "edge-tts",
        "textual_image": "textual-image",
        "dotenv": "python-dotenv"
    }
    
    missing_libs = []
    for module, pip_name in required_libraries.items():
        try:
            __import__(module)
        except ImportError:
            missing_libs.append(pip_name)

    if missing_libs:
        print("[CRITICAL] Missing required dependencies:")
        for lib in missing_libs:
            print(f"  - {lib}")
        print("\nPlease run the following command to install them:")
        print(f"  pip install {' '.join(missing_libs)}")
        sys.exit(1)

def main():
    """Initialize environment and launch the TUI."""
    # 1. Environment and Dependency Checks
    check_python_version()
    ensure_directories()
    check_dependencies()

    # 2. Launch the Application loop
    while True:
        try:
            from menu import TaiMenu, set_terminal_appearance
            from engines.app_commands import RestartRequested
            from engines.config import get_setting
            
            if get_setting("clear_on_start", True):
                print("\033[H\033[J", end="")
            
            print(f"Running on: {platform.system()} {platform.release()}")
            set_terminal_appearance(title="t.ai")
            
            app = TaiMenu(char_path=None, user_path=None)
            app.run()
            
            # If app.run() returns normally, break the loop
            break
            
        except RestartRequested:
            # Clear screen and restart
            print("\033[H\033[J", end="")
            continue
        except ImportError as e:
            print(f"[CRITICAL] Failed to load application modules: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[CRITICAL ERROR] Application failed to start: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
