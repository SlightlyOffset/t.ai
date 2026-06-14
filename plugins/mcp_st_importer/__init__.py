from mcp.server.fastmcp import FastMCP
import os
import sys
import traceback

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from engines.character_importer import import_character, CharacterImporter
from engines.utilities import sanitize_profile_name
import json

mcp = FastMCP("st_importer")


@mcp.tool()
def import_st_card(filepath: str, overwrite: bool = False, refine: bool = True) -> str:
    """
    Imports a SillyTavern V2 character card (PNG or JSON) into a t.ai character profile.
    
    Args:
        filepath: The absolute path to the .png or .json card file.
        overwrite: If True, overwrites an existing profile with the same name.
        refine: MUST BE True. If True, uses local AI to properly format the card into the system's native format. Always set this to true to prevent text dumps.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found at {filepath}"
        
    try:
        # Extract name to see if profile already exists
        data = None
        if filepath.lower().endswith((".png", ".webp")):
            data = CharacterImporter.extract_from_png(filepath)
        elif filepath.lower().endswith(".json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_json = json.load(f)
                    data = raw_json.get("data") if "data" in raw_json else raw_json
            except Exception as e:
                return f"Error reading JSON: {str(e)}"
                
        if not data or "name" not in data:
            return f"Error: Could not extract character data or name from {filepath}"
            
        char_name = data["name"]
        safe_name = sanitize_profile_name(char_name)
        target_path = os.path.abspath(os.path.join("profiles", f"{safe_name}.json"))
        
        if os.path.exists(target_path) and not overwrite:
            return f"Failed to import character card from {filepath}. It already exists (try overwrite=True)."
            
        # Read plugin configuration
        config_path = os.path.join(project_root, "plugins", "mcp_st_importer", "plugin.json")
        refine_model = None
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    refine_model = cfg.get("refine_model")
            except Exception:
                pass

        success_path = import_character(filepath, refine=refine, model=refine_model)
        
        if success_path:
            return f"Successfully imported character card from {filepath} to {success_path}"
        else:
            return f"Failed to import character card from {filepath}."
    except Exception as e:
        return f"Error importing card: {str(e)}"

def initialize(context):
    """Initializes the MCP SillyTavern Card Importer plugin."""
    pass

if __name__ == "__main__":
    mcp.run()
