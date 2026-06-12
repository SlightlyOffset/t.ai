from mcp.server.fastmcp import FastMCP
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from card_importer import import_sillytavern_card

mcp = FastMCP("st_importer", description="SillyTavern Card Importer")

@mcp.tool()
def import_st_card(filepath: str, overwrite: bool = False) -> str:
    """
    Imports a SillyTavern V2 character card (PNG or JSON) into a t.ai character profile.
    
    Args:
        filepath: The absolute path to the .png or .json card file.
        overwrite: If True, overwrites an existing profile with the same name.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found at {filepath}"
        
    try:
        success = import_sillytavern_card(filepath, overwrite=overwrite)
        if success:
            return f"Successfully imported character card from {filepath}"
        else:
            return f"Failed to import character card from {filepath}. It may already exist (try overwrite=True)."
    except Exception as e:
        return f"Error importing card: {str(e)}"

if __name__ == "__main__":
    mcp.run()
