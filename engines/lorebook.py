"""
Lorebook (World Info) management and scanning.
Efficiently injects world/character facts based on keywords in recent history.
"""

import json
import os
import requests

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

def sync_lore_to_remote(lorebook_data: dict, remote_url: str) -> bool:
    """
    Sync the lorebook to the remote bridge for semantic indexing.
    
    Args:
        lorebook_data (dict): The lorebook with entries
        remote_url (str): The base URL of the remote bridge
        
    Returns:
        bool: True if sync succeeded, False otherwise
    """
    if not remote_url or not lorebook_data:
        return False
    
    try:
        sync_url = f"{remote_url.rstrip('/')}/sync_lore"
        payload = lorebook_data
        
        response = requests.post(sync_url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") == "success":
            print(f"✓ Lore synced to remote bridge: {data.get('message', 'OK')}")
            return True
        else:
            print(f"✗ Failed to sync lore: {data.get('message', 'Unknown error')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error syncing lore to remote bridge: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error during lore sync: {e}")
        return False


# Try to import C-based pyahocorasick
try:
    import ahocorasick
    HAS_PYAHOCORASICK = True
except ImportError:
    HAS_PYAHOCORASICK = False

class PureAhoCorasick:
    """
    A pure-Python implementation of the Aho-Corasick string matching algorithm.
    Used as a fallback when the C-compiled pyahocorasick library is not available.
    """
    def __init__(self):
        self.trie = [{}]
        self.output = [[]]
        self.fail = [0]

    def add_word(self, word: str, value):
        if not word:
            return
        curr = 0
        for char in word:
            if char not in self.trie[curr]:
                self.trie.append({})
                self.output.append([])
                self.fail.append(0)
                self.trie[curr][char] = len(self.trie) - 1
            curr = self.trie[curr][char]
        self.output[curr].append(value)

    def make_automaton(self):
        from collections import deque
        queue = deque()
        for char, child in self.trie[0].items():
            self.fail[child] = 0
            queue.append(child)
        while queue:
            curr = queue.popleft()
            for char, child in self.trie[curr].items():
                fail_node = self.fail[curr]
                while fail_node > 0 and char not in self.trie[fail_node]:
                    fail_node = self.fail[fail_node]
                if char in self.trie[fail_node]:
                    self.fail[child] = self.trie[fail_node][char]
                else:
                    self.fail[child] = 0
                self.output[child].extend(self.output[self.fail[child]])
                queue.append(child)

    def iter(self, text: str):
        curr = 0
        for i, char in enumerate(text):
            while curr > 0 and char not in self.trie[curr]:
                curr = self.fail[curr]
            if char in self.trie[curr]:
                curr = self.trie[curr][char]
            else:
                curr = 0
            for value in self.output[curr]:
                yield i, value

def scan_for_lore(recent_messages: list, lorebook_data: dict) -> str:
    """
    Scans the most recent conversation history for keywords defined in the lorebook.
    Uses Aho-Corasick algorithm for O(N) multi-pattern matching with a pure-Python fallback.
    Returns a formatted string of matched entries.
    """
    if not lorebook_data or not lorebook_data.get("entries"):
        return ""

    # Consolidate text from recent messages to scan
    text_to_scan = " ".join([msg.get("content", "").lower() for msg in recent_messages])

    # Build map of unique lowercased keys to their respective lorebook entries
    key_to_entries = {}
    for entry in lorebook_data.get("entries", []):
        if not entry.get("enabled", True):
            continue
        for key in entry.get("keys", []):
            k = key.lower()
            if not k:
                continue
            if k not in key_to_entries:
                key_to_entries[k] = []
            key_to_entries[k].append(entry)

    if not key_to_entries:
        return ""

    # Initialize and populate automaton
    if HAS_PYAHOCORASICK:
        A = ahocorasick.Automaton()
    else:
        A = PureAhoCorasick()

    for k in key_to_entries:
        A.add_word(k, k)

    A.make_automaton()

    # Scan text for matches
    matched_keys = set()
    for end_idx, k in A.iter(text_to_scan):
        start_idx = end_idx - len(k) + 1
        
        # Word boundary verification (\b equivalent)
        is_word_boundary_start = (
            start_idx == 0 or 
            not (text_to_scan[start_idx - 1].isalnum() or text_to_scan[start_idx - 1] == '_')
        )
        is_word_boundary_end = (
            end_idx == len(text_to_scan) - 1 or 
            not (text_to_scan[end_idx + 1].isalnum() or text_to_scan[end_idx + 1] == '_')
        )
        
        if is_word_boundary_start and is_word_boundary_end:
            matched_keys.add(k)

    if not matched_keys:
        return ""

    # Gather matching entries uniquely
    active_lore_set = set()
    active_lore = []
    for k in matched_keys:
        for entry in key_to_entries[k]:
            entry_id = entry.get("id") or entry.get("content")
            if entry_id not in active_lore_set:
                active_lore_set.add(entry_id)
                active_lore.append(entry)

    # Sort by insertion_order (allows control over which info appears first)
    active_lore.sort(key=lambda x: x.get("insertion_order", 100))
    
    # Format the activated lore into a string block
    lore_text = "[WORLD INFO / LORE]\n"
    for entry in active_lore:
        content = entry.get("content", "").strip()
        if content:
            lore_text += f"- {content}\n"
    
    return lore_text.strip()


