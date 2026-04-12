import unittest
import json
import os
import shutil
from engines.lorebook import load_lorebook, scan_for_lore

class TestLorebook(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_lorebooks"
        os.makedirs(self.test_dir, exist_ok=True)
        self.lore_path = os.path.join(self.test_dir, "test_lore.json")
        self.lore_data = {
            "entries": [
                {
                    "id": "1",
                    "keys": ["tavern", "inn"],
                    "content": "The tavern is cozy.",
                    "enabled": True,
                    "insertion_order": 50
                },
                {
                    "id": "2",
                    "keys": ["elf", "legolas"],
                    "content": "Elves have pointy ears.",
                    "enabled": True,
                    "insertion_order": 10
                },
                {
                    "id": "3",
                    "keys": ["disabled"],
                    "content": "This should not show.",
                    "enabled": False,
                    "insertion_order": 100
                }
            ]
        }
        with open(self.lore_path, "w") as f:
            json.dump(self.lore_data, f)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_lorebook(self):
        loaded = load_lorebook(self.lore_path)
        self.assertEqual(len(loaded.get("entries", [])), 3)

    def test_scan_for_lore_match(self):
        messages = [{"role": "user", "content": "Let's go to the tavern."}]
        lore_text = scan_for_lore(messages, self.lore_data)
        self.assertIn("The tavern is cozy.", lore_text)
        self.assertIn("[WORLD INFO / LORE]", lore_text)

    def test_scan_for_lore_no_match(self):
        messages = [{"role": "user", "content": "Hello there."}]
        lore_text = scan_for_lore(messages, self.lore_data)
        self.assertEqual(lore_text, "")

    def test_scan_for_lore_disabled(self):
        messages = [{"role": "user", "content": "Something is disabled here."}]
        lore_text = scan_for_lore(messages, self.lore_data)
        self.assertNotIn("This should not show.", lore_text)

    def test_scan_for_lore_ordering(self):
        messages = [{"role": "user", "content": "An elf in a tavern."}]
        lore_text = scan_for_lore(messages, self.lore_data)
        # Insertion order 10 (elf) should come before 50 (tavern)
        elf_pos = lore_text.find("Elves have pointy ears.")
        tavern_pos = lore_text.find("The tavern is cozy.")
        self.assertTrue(elf_pos < tavern_pos)

    def test_scan_for_lore_whole_word(self):
        # "himself" contains "elf" but shouldn't match
        messages = [{"role": "user", "content": "He did it himself."}]
        lore_text = scan_for_lore(messages, self.lore_data)
        self.assertEqual(lore_text, "")

if __name__ == "__main__":
    unittest.main()
