import unittest
import os
import sys
import json
import shutil

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.memory_v2 import HistoryManager

class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_history"
        self.manager = HistoryManager(history_dir=self.test_dir)
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_load(self):
        profile = "TestProfile"
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        self.manager.save_history(profile, history, relationship_score=10)
        
        loaded = self.manager.load_history(profile)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["content"], "Hello")
        
        # Check that we can also get the metadata
        data = self.manager.get_full_data(profile)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["relationship_score"], 10)
        self.assertIn("last_interaction", data["metadata"])

    def test_truncation(self):
        profile = "TruncateProfile"
        # 20 messages
        history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        self.manager.save_history(profile, history)
        
        # Should only load the last 15
        loaded = self.manager.load_history(profile, limit=15)
        self.assertEqual(len(loaded), 15)
        self.assertEqual(loaded[0]["content"], "msg 5")
        self.assertEqual(loaded[-1]["content"], "msg 19")

    def test_per_profile_files(self):
        self.manager.save_history("ProfileA", [{"role": "user", "content": "A"}])
        self.manager.save_history("ProfileB", [{"role": "user", "content": "B"}])
        
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ProfileA_history.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ProfileB_history.json")))

    def test_special_characters_in_filename(self):
        profile = "Ria(polite)-Variant_1"
        self.manager.save_history(profile, [{"role": "user", "content": "test"}])
        
        expected_path = os.path.join(self.test_dir, "Ria(polite)-Variant_1_history.json")
        self.assertTrue(os.path.exists(expected_path))
        
        loaded = self.manager.load_history(profile)
        self.assertEqual(len(loaded), 1)

    def test_is_recent_interaction(self):
        profile = "RecentProfile"
        # Save history (sets timestamp to now)
        self.manager.save_history(profile, [{"role": "user", "content": "hello"}])
        
        # Should be recent (within 24 hours)
        self.assertTrue(self.manager.is_recent_interaction(profile, hours=24))
        
        # Mocking an old timestamp (this is a bit tricky without patching, 
        # but I can manually overwrite the file for the test)
        filename = self.manager._get_filename(profile)
        with open(filename, "r", encoding="UTF-8") as f:
            data = json.load(f)
        
        # Set to 25 hours ago
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d | %H:%M:%S")
        data["metadata"]["last_interaction"] = old_time
        
        with open(filename, "w", encoding="UTF-8") as f:
            json.dump(data, f)
            
        # Should NOT be recent anymore
        self.assertFalse(self.manager.is_recent_interaction(profile, hours=24))

    def test_rewind_history_truncates_and_clamps_summarized_index(self):
        profile = "RewindProfile"
        history = [{"role": "user", "content": f"msg {i}"} for i in range(6)]
        self.manager.save_history(
            profile,
            history,
            relationship_score=12,
            current_scene="Cafe",
            memory_core="Summary exists",
            last_summarized_index=4,
        )

        original_count, kept_count = self.manager.rewind_history(profile, 3)
        self.assertEqual((original_count, kept_count), (6, 3))

        data = self.manager.get_full_data(profile)
        self.assertEqual(len(data["history"]), 3)
        self.assertEqual(data["metadata"]["last_summarized_index"], 0)
        self.assertEqual(data["metadata"]["memory_core"], "")
        self.assertEqual(data["metadata"]["relationship_score"], 12)
        self.assertEqual(data["metadata"]["current_scene"], "Cafe")

    def test_rewind_history_keeps_valid_summary_index(self):
        profile = "RewindProfile2"
        history = [{"role": "assistant", "content": f"msg {i}"} for i in range(5)]
        self.manager.save_history(
            profile,
            history,
            memory_core="Still valid",
            last_summarized_index=2,
        )

        self.manager.rewind_history(profile, 4)
        data = self.manager.get_full_data(profile)
        self.assertEqual(len(data["history"]), 4)
        self.assertEqual(data["metadata"]["last_summarized_index"], 2)
        self.assertEqual(data["metadata"]["memory_core"], "Still valid")

    def test_rewind_history_clears_memory_core_on_large_rewind_distance(self):
        profile = "RewindProfile3"
        history = [{"role": "user", "content": f"msg {i}"} for i in range(30)]
        self.manager.save_history(
            profile,
            history,
            memory_core="Large summary",
            last_summarized_index=10,
        )

        # Remove 15 messages (threshold): should clear summary state.
        self.manager.rewind_history(profile, 15)
        data = self.manager.get_full_data(profile)
        self.assertEqual(len(data["history"]), 15)
        self.assertEqual(data["metadata"]["memory_core"], "")
        self.assertEqual(data["metadata"]["last_summarized_index"], 0)

    def test_history_save_creates_hidden_backup(self):
        profile = "BackupProfile"
        history = [{"role": "user", "content": "Hello backup"}]
        self.manager.save_history(profile, history)
        
        filename = self.manager._get_filename(profile)
        bak_file = filename + ".bak"
        self.assertTrue(os.path.exists(filename))
        
        # Save a second time to trigger backup creation of the first run
        self.manager.save_history(profile, history)
        self.assertTrue(os.path.exists(bak_file))

        # Check Windows hidden attribute if on Windows
        if os.name == 'nt':
            import ctypes
            # GetFileAttributesW returns attributes bitmask; FILE_ATTRIBUTE_HIDDEN is 0x2
            attrs = ctypes.windll.kernel32.GetFileAttributesW(bak_file)
            self.assertTrue(bool(attrs & 2))

    def test_history_load_corrupted_fallback(self):
        profile = "CorruptHistoryProfile"
        filename = self.manager._get_filename(profile)
        bak_file = filename + ".bak"

        # 1. Create backup with valid data
        valid_data = {
            "metadata": {
                "relationship_score": 42,
                "current_scene": "School",
                "memory_core": "Old Memory",
                "last_summarized_index": 1,
            },
            "history": [{"role": "user", "content": "Hello"}]
        }
        with open(bak_file, "w", encoding="utf-8") as f:
            json.dump(valid_data, f)

        # 2. Create corrupted primary file
        with open(filename, "w", encoding="utf-8") as f:
            f.write("invalid json contents")

        # 3. Load history/full data and check fallback
        loaded_data = self.manager.get_full_data(profile)
        self.assertEqual(loaded_data["metadata"]["relationship_score"], 42)
        self.assertEqual(loaded_data["metadata"]["current_scene"], "School")
        self.assertEqual(len(loaded_data["history"]), 1)
        self.assertEqual(loaded_data["history"][0]["content"], "Hello")

        # 4. Verify primary file was healed/restored
        with open(filename, "r", encoding="utf-8") as f:
            healed = json.load(f)
        self.assertEqual(healed["metadata"]["relationship_score"], 42)

if __name__ == "__main__":
    unittest.main()

