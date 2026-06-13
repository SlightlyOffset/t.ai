from mcp.server.fastmcp import FastMCP
import os
import sys
import traceback
from datetime import datetime

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from engines.character_importer import import_character, CharacterImporter
from engines.utilities import sanitize_profile_name
import json

mcp = FastMCP("st_importer")

# ---------------------------------------------------------------------------
# Lightweight file logger (independent of main app's debug_mode setting,
# since this module runs inside a separate MCP subprocess).
# ---------------------------------------------------------------------------
_DEBUG_DIR = os.path.join(project_root, "debug")

def _log(category: str, detail):
    """Append a JSON-lines entry to debug/debug_YYYYMMDD.log."""
    try:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        ts = datetime.now()
        entry = {
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "category": f"MCP_ST_IMPORTER_{category}",
            "detail": detail,
        }
        log_path = os.path.join(_DEBUG_DIR, f"debug_{ts.strftime('%Y%m%d')}.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # never crash the tool over logging


@mcp.tool()
def import_st_card(filepath: str, overwrite: bool = False, refine: bool = True) -> str:
    """
    Imports a SillyTavern V2 character card (PNG or JSON) into a t.ai character profile.
    
    Args:
        filepath: The absolute path to the .png or .json card file.
        overwrite: If True, overwrites an existing profile with the same name.
        refine: If True, uses local AI to refine the extracted fields.
    """
    _log("CALL", {"filepath": filepath, "overwrite": overwrite, "refine": refine, "cwd": os.getcwd()})

    if not os.path.exists(filepath):
        _log("FILE_NOT_FOUND", {"filepath": filepath})
        return f"Error: File not found at {filepath}"
        
    try:
        # Extract name to see if profile already exists
        data = None
        if filepath.lower().endswith((".png", ".webp")):
            _log("EXTRACT_PNG", {"filepath": filepath})
            data = CharacterImporter.extract_from_png(filepath)
        elif filepath.lower().endswith(".json"):
            _log("EXTRACT_JSON", {"filepath": filepath})
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_json = json.load(f)
                    data = raw_json.get("data") if "data" in raw_json else raw_json
            except Exception as e:
                _log("JSON_READ_ERROR", {"filepath": filepath, "error": str(e)})
                return f"Error reading JSON: {str(e)}"
                
        if not data or "name" not in data:
            _log("NO_DATA_OR_NAME", {"filepath": filepath, "data_keys": list(data.keys()) if data else None})
            return f"Error: Could not extract character data or name from {filepath}"
            
        char_name = data["name"]
        safe_name = sanitize_profile_name(char_name)
        target_path = os.path.abspath(os.path.join("profiles", f"{safe_name}.json"))
        _log("RESOLVED", {"char_name": char_name, "safe_name": safe_name, "target_path": target_path, "exists": os.path.exists(target_path)})
        
        if os.path.exists(target_path) and not overwrite:
            msg = f"Failed to import character card from {filepath}. It already exists (try overwrite=True)."
            _log("ALREADY_EXISTS", {"target_path": target_path, "result": msg})
            return msg
            
        _log("IMPORT_START", {"filepath": filepath, "refine": refine})
        success_path = import_character(filepath, refine=refine)
        
        if success_path:
            msg = f"Successfully imported character card from {filepath} to {success_path}"
            _log("IMPORT_SUCCESS", {"success_path": success_path, "result": msg})
            return msg
        else:
            msg = f"Failed to import character card from {filepath}."
            _log("IMPORT_FAILED", {"result": msg})
            return msg
    except Exception as e:
        tb = traceback.format_exc()
        _log("IMPORT_EXCEPTION", {"error": str(e), "traceback": tb})
        return f"Error importing card: {str(e)}"

def initialize(context):
    """Initializes the MCP SillyTavern Card Importer plugin."""
    pass

if __name__ == "__main__":
    mcp.run()

