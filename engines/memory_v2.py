"""
Enhanced persistent memory management for conversation history.
Handles per-profile history storage, metadata (timestamps, mood), and history truncation.
"""

import json
import re
import os
from datetime import datetime
from engines.utilities import sanitize_profile_name

class HistoryManager:
    """
    Manages loading, saving, and truncation of conversation history.
    """
    REWIND_MEMORY_CORE_RESET_THRESHOLD = 15

    def __init__(self, history_dir: str = "history"):
        self.history_dir = history_dir
        self._ensure_history_dir()

    def _ensure_history_dir(self) -> None:
        """Ensures the history directory exists on the filesystem."""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def _get_filename(self, profile_name: str) -> str:
        """Generates a safe filename for the history JSON file."""
        safe_name = sanitize_profile_name(profile_name) or "session"
        return os.path.join(self.history_dir, f"{safe_name}_history.json")

    def has_history(self, profile_name: str) -> bool:
        """Checks if the history file exists for a given profile."""
        filename = self._get_filename(profile_name)
        return os.path.exists(filename)

    def get_history_length(self, profile_name: str) -> int:
        """Returns the number of messages in the history."""
        data = self.get_full_data(profile_name)
        return len(data.get("history", [])) if data else 0

    def save_history(self, profile_name: str, history: list, mood_score: int = 0,
                     current_scene: str = "Unknown Location", memory_core: str = "",
                     last_summarized_index: int = 0) -> None:
        """
        Saves history to a JSON file with metadata.

        Args:
            profile_name (str): The name of the character.
            history (list): List of message dictionaries.
            mood_score (int): Current relationship/mood score.
            current_scene (str): The physical location or state of the RP.
            memory_core (str): The consolidated rolling summary.
            last_summarized_index (int): The index of the last message included in the summary.
        """
        filename = self._get_filename(profile_name)
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d | %H:%M:%S")

        data_to_save = {
            "metadata": {
                "last_interaction": current_time,
                "mood_score": mood_score,
                "current_scene": current_scene,
                "memory_core": memory_core,
                "last_summarized_index": last_summarized_index
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
        default_data = {
            "metadata": {
                "last_interaction": None,
                "mood_score": 0,
                "current_scene": "Unknown Location",
                "memory_core": "",
                "last_summarized_index": 0,
                "narrative_state": {},
                "last_turn_metrics": {},
            },
            "history": []
        }

        if not os.path.exists(filename):
            return default_data

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
                        "metadata": {
                            "last_interaction": last_time,
                            "mood_score": 0,
                            "current_scene": "Unknown Location",
                            "memory_core": "",
                            "last_summarized_index": 0,
                            "narrative_state": {},
                            "last_turn_metrics": {},
                        },
                        "history": [m for m in data if m.get("role") != "system"]
                    }

                # Ensure all metadata fields exist
                if "metadata" not in data:
                    data["metadata"] = default_data["metadata"]
                else:
                    for key, val in default_data["metadata"].items():
                        if key not in data["metadata"]:
                            data["metadata"][key] = val

                return data
        except (json.JSONDecodeError, Exception):
            return default_data

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

    def get_memory_core(self, profile_name: str) -> str:
        """Retrieves the consolidated rolling summary for a profile."""
        data = self.get_full_data(profile_name)
        return data.get("metadata", {}).get("memory_core", "")

    def get_last_summarized_index(self, profile_name: str) -> int:
        """Retrieves the index of the last summarized message."""
        data = self.get_full_data(profile_name)
        return data.get("metadata", {}).get("last_summarized_index", 0)

    def update_memory_core(self, profile_name: str, summary: str, last_index: int) -> None:
        """Updates the Memory Core and its last summarized index without losing history."""
        data = self.get_full_data(profile_name)
        data["metadata"]["memory_core"] = summary
        data["metadata"]["last_summarized_index"] = last_index

        filename = self._get_filename(profile_name)
        with open(filename, "w", encoding="UTF-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_narrative_state(self, profile_name: str) -> dict:
        """Retrieves persisted narrative state for pipeline-based generation."""
        data = self.get_full_data(profile_name)
        return data.get("metadata", {}).get("narrative_state", {})

    def update_narrative_state(self, profile_name: str, narrative_state: dict, turn_metrics: dict | None = None) -> None:
        """Persists narrative state and optional turn metrics without touching history messages."""
        data = self.get_full_data(profile_name)
        metadata = data.setdefault("metadata", {})
        metadata["narrative_state"] = narrative_state or {}
        if turn_metrics is not None:
            metadata["last_turn_metrics"] = turn_metrics

        filename = self._get_filename(profile_name)
        with open(filename, "w", encoding="UTF-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def rewind_history(self, profile_name: str, keep_count: int) -> tuple[int, int]:
        """
        Truncates conversation history to the first `keep_count` messages.

        Args:
            profile_name (str): The profile whose history should be rewound.
            keep_count (int): Number of earliest messages to keep (0..len(history)).

        Returns:
            tuple[int, int]: (original_count, kept_count)
        """
        if keep_count < 0:
            raise ValueError("keep_count must be 0 or greater")

        data = self.get_full_data(profile_name)
        history = data.get("history", [])
        original_count = len(history)
        removed_count = original_count - keep_count

        if keep_count > original_count:
            raise ValueError("keep_count cannot exceed history length")

        metadata = data.setdefault("metadata", {})
        old_last_summarized = int(metadata.get("last_summarized_index", 0) or 0)
        if removed_count >= self.REWIND_MEMORY_CORE_RESET_THRESHOLD or keep_count < old_last_summarized:
            metadata["memory_core"] = ""
            metadata["last_summarized_index"] = 0
        else:
            metadata["last_summarized_index"] = min(old_last_summarized, keep_count)

        metadata["last_interaction"] = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
        data["history"] = history[:keep_count]

        filename = self._get_filename(profile_name)
        with open(filename, "w", encoding="UTF-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return original_count, keep_count

# Global instance for easy access across the application
memory_manager = HistoryManager()
