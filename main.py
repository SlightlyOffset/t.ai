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

def check_ollama_and_models():
    """If using local Ollama, verify it is running and the default model is pulled."""
    if "--force" in sys.argv or "-f" in sys.argv:
        print("[WARNING] Force launch requested. Skipping Ollama and model validations...")
        return

    project_root = os.path.abspath(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    try:
        from engines.config import get_setting
    except ImportError as e:
        print(f"[CRITICAL] Failed to load config engine: {e}")
        sys.exit(1)

    if get_setting("force_launch", False):
        print("[WARNING] force_launch is enabled in settings. Skipping Ollama and model validations...")
        return

    remote_llm = get_setting("remote_llm_url")
    if remote_llm:
        return

    default_model = get_setting("default_llm_model") or "fluffy/l3-8b-stheno-v3.2"

    try:
        import ollama
        response = ollama.list()
    except Exception as e:
        print("[CRITICAL] Local Ollama service is not running or not installed.")
        print("  Please make sure Ollama is installed and running on your system (https://ollama.com).")
        print(f"  Error details: {e}")
        sys.exit(1)

    models = []
    if isinstance(response, dict):
        models = [m.get("model", m.get("name", "")) for m in response.get("models", [])]
    else:
        try:
            models = [m.model for m in getattr(response, "models", [])]
        except Exception:
            try:
                models = [getattr(m, "name", "") for m in getattr(response, "models", [])]
            except Exception:
                pass

    def normalize_model_name(name):
        if not name: return ""
        name = name.strip().lower()
        return name

    normalized_models = [normalize_model_name(m) for m in models if m]
    normalized_default = normalize_model_name(default_model)

    has_model = normalized_default in normalized_models
    if not has_model and ":" not in normalized_default:
        has_model = (normalized_default + ":latest") in normalized_models

    if not has_model:
        for m in normalized_models:
            if m.startswith(normalized_default + ":") or (":" not in normalized_default and m == normalized_default):
                has_model = True
                break

    if not has_model:
        print(f"[CRITICAL] Default model '{default_model}' is not pulled in local Ollama.")
        print(f"  Please run: ollama pull {default_model}")
        if models:
            print("\n  Available local models:")
            for m in models:
                if m: print(f"    - {m}")
        sys.exit(1)

def main():
    """Initialize environment and launch the TUI."""
    # 1. Environment and Dependency Checks
    check_python_version()
    ensure_directories()
    check_dependencies()
    check_ollama_and_models()

    # 2. Launch the Application loop
    while True:
        try:
            from ui.menu import TaiMenu
            from engines.app_commands import RestartRequested
            from engines.config import get_setting
            from engines.utilities import set_terminal_appearance

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
