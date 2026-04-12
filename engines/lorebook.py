"""
Lorebook (World Info) management and scanning.
Efficiently injects world/character facts based on keywords in recent history.
"""

import json
import os
import re

def load_lorebook(filepath: str) -> dict:
    """
    Safely reads and parses the lorebook JSON file.
    """
    if not os.path.exists(filepath):
        return {"entries": []}
    
    try:
        with open(filepath, "r", encoding="UTF-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error loading lorebook: {e}")
        return {"entries": []}

def scan_for_lore(recent_messages: list, lorebook_data: dict) -> str:
    """
    Scans the most recent conversation history for keywords defined in the lorebook.
    Returns a formatted string of matched entries.
    """
    if not lorebook_data or not lorebook_data.get("entries"):
        return ""

    # Consolidate text from recent messages to scan
    text_to_scan = " ".join([msg.get("content", "").lower() for msg in recent_messages])
    active_lore = []

    for entry in lorebook_data.get("entries", []):
        if not entry.get("enabled", True):
            continue
            
        # Check if any of the keys are in the recent text using whole-word matching
        for key in entry.get("keys", []):
            # Use regex for whole word matching (\bkey\b) to avoid partial matches
            if re.search(fr'\b{re.escape(key.lower())}\b', text_to_scan):
                active_lore.append(entry)
                break 

    if not active_lore:
        return ""

    # Sort by insertion_order (allows you to control which info appears first)
    active_lore.sort(key=lambda x: x.get("insertion_order", 100))
    
    # Format the activated lore into a string block
    lore_text = "[WORLD INFO / LORE]\n"
    for entry in active_lore:
        content = entry.get("content", "").strip()
        if content:
            lore_text += f"- {content}\n"
    
    return lore_text.strip()
