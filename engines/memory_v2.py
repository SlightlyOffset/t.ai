"""
Enhanced persistent memory management for conversation history.
Handles per-profile history storage, metadata (timestamps, mood), and history truncation.
"""

import json
import re
import os
from datetime import datetime

class HistoryManager:
    """
    Manages loading, saving, and truncation of conversation history.
    """
    def __init__(self, history_dir: str = "history"):
        self.history_dir = history_dir
        self._ensure_history_dir()

    def _ensure_history_dir(self) -> None:
        """Ensures the history directory exists on the filesystem."""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def _get_filename(self, profile_name: str) -> str:
        """Generates a safe filename for the history JSON file."""
        # Allow alphanumeric, underscores, dashes
        # Replace spaces with underscores
        safe_name = profile_name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in ('_', '-')).rstrip()
        return os.path.join(self.history_dir, f"{safe_name}_history.json")

    def has_history(self, profile_name: str) -> bool:
        """Checks if the history file exists for a given profile."""
        filename = self._get_filename(profile_name)
        return os.path.exists(filename)

    def get_history_length(self, profile_name: str) -> int:
        """Returns the number of messages in the history."""
        data = self.get_full_data(profile_name)
        return len(data.get("history", [])) if data else 0

    def save_history(self, profile_name: str, history: list, mood_score: int = 0) -> None:
        """
        Saves history to a JSON file with metadata.

        Args:
            profile_name (str): The name of the character.
            history (list): List of message dictionaries.
            mood_score (int): Current relationship/mood score.
        """
        filename = self._get_filename(profile_name)
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d | %H:%M:%S")

        data_to_save = {
            "metadata": {
                "last_interaction": current_time,
                "mood_score": mood_score
            },
            "history": history
        }

        with open(filename, "w", encoding="UTF-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)

    def get_full_data(self, profile_name: str) -> dict:
        """
        Loads the full JSON structure from the history file.
        Handles transition from the old format (list of messages).
        """
        filename = self._get_filename(profile_name)
        if not os.path.exists(filename):
            return {"metadata": {}, "history": []}

        try:
            with open(filename, "r", encoding="UTF-8") as f:
                data = json.load(f)

                # Handle old format (list)
                if isinstance(data, list):
                    # Try to find the timestamp in the last message (legacy behavior)
                    last_time = None
                    for msg in reversed(data):
                        if msg.get("role") == "system" and "Timestamp: " in msg.get("content", ""):
                            last_time = msg["content"].replace("Timestamp: ", "").strip()
                            break

                    return {
                        "metadata": {"last_interaction": last_time},
                        "history": [m for m in data if m.get("role") != "system"]
                    }

                return data
        except (json.JSONDecodeError, Exception):
            return {"metadata": {}, "history": []}

    def load_history(self, profile_name: str, limit: int = None) -> list:
        """
        Loads history list from a JSON file, optionally truncating it.

        Args:
            profile_name (str): The name of the character.
            limit (int, optional): The maximum number of messages to return.

        Returns:
            list: List of loaded messages.
        """
        data = self.get_full_data(profile_name)
        history = data.get("history", [])

        if limit and len(history) > limit:
            # Truncate to the last 'limit' messages
            return history[-limit:]
        return history

    def get_last_timestamp(self, profile_name: str) -> datetime | None:
        """
        Retrieves the last interaction timestamp for mood decay.
        """
        data = self.get_full_data(profile_name)
        time_str = data.get("metadata", {}).get("last_interaction")
        if time_str:
            try:
                return datetime.strptime(time_str, "%Y-%m-%d | %H:%M:%S")
            except ValueError:
                return None
        return None

    def is_recent_interaction(self, profile_name: str, hours: int = 24) -> bool:
        """
        Checks if the last interaction was within a certain number of hours.
        """
        last_time = self.get_last_timestamp(profile_name)
        if not last_time:
            return False

        now = datetime.now()
        diff = now - last_time
        return (diff.total_seconds() / 3600) <= hours

# Global instance for easy access across the application
memory_manager = HistoryManager()
