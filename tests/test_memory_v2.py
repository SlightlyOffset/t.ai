import unittest
import os
import sys
import json
import shutil

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.memory_v2 import HistoryManager

from unittest.mock import patch

class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('engines.config.get_setting')
        self.mock_get_setting = self.patcher.start()
        self.mock_get_setting.return_value = "default"

        self.test_dir = "test_history"
        self.manager = HistoryManager(history_dir=self.test_dir)
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        self.patcher.stop()
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
        
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ProfileA", "default_history.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "ProfileB", "default_history.json")))

    def test_special_characters_in_filename(self):
        profile = "Ria(polite)-Variant_1"
        self.manager.save_history(profile, [{"role": "user", "content": "test"}])
        
        expected_path = os.path.join(self.test_dir, "Ria(polite)-Variant_1", "default_history.json")
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

    def test_session_support(self):
        profile = "MultiSessionProfile"
        self.manager.save_history(profile, [{"role": "user", "content": "hello default"}], session_name="default")
        self.manager.save_history(profile, [{"role": "user", "content": "hello custom"}], session_name="custom")
        
        default_loaded = self.manager.load_history(profile, session_name="default")
        custom_loaded = self.manager.load_history(profile, session_name="custom")
        
        self.assertEqual(len(default_loaded), 1)
        self.assertEqual(default_loaded[0]["content"], "hello default")
        self.assertEqual(len(custom_loaded), 1)
        self.assertEqual(custom_loaded[0]["content"], "hello custom")
        
    def test_legacy_migration(self):
        profile = "LegacyProfile"
        # 1. Create a legacy flat file manually
        legacy_path = os.path.join(self.test_dir, f"{profile}_history.json")
        legacy_bak_path = legacy_path + ".bak"
        
        legacy_data = {
            "metadata": {
                "relationship_score": 50,
                "current_scene": "Library",
                "memory_core": "Some legacy summary",
                "last_summarized_index": 2,
            },
            "history": [{"role": "user", "content": "Legacy message"}]
        }
        
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)
        with open(legacy_bak_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)
            
        # 2. Access it via the manager under the default session name
        loaded = self.manager.load_history(profile, session_name="default")
        
        # 3. Assert transparent migration happened
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["content"], "Legacy message")
        
        new_path = os.path.join(self.test_dir, profile, "default_history.json")
        new_bak_path = new_path + ".bak"
        
        self.assertTrue(os.path.exists(new_path))
        self.assertTrue(os.path.exists(new_bak_path))
        self.assertFalse(os.path.exists(legacy_path))
        self.assertFalse(os.path.exists(legacy_bak_path))

    def test_legacy_migration_only_backup_exists(self):
        profile = "LegacyBackupProfile"
        # 1. Create a legacy backup file only
        legacy_bak_path = os.path.join(self.test_dir, f"{profile}_history.json.bak")
        
        legacy_data = {
            "metadata": {
                "relationship_score": 75,
                "current_scene": "Park",
                "memory_core": "Backup recovery",
                "last_summarized_index": 1,
            },
            "history": [{"role": "user", "content": "Backup legacy message"}]
        }
        
        with open(legacy_bak_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)
            
        # 2. Access it via the manager under the default session name
        loaded = self.manager.load_history(profile, session_name="default")
        
        # 3. Assert transparent migration from backup happened
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["content"], "Backup legacy message")
        
        new_path = os.path.join(self.test_dir, profile, "default_history.json")
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(legacy_bak_path))

    @patch('engines.config.get_setting')
    def test_user_profile_in_metadata(self, mock_get_setting):
        profile = "UserMetadataProfile"
        mock_get_setting.return_value = "Aiko.json"
        
        self.manager.save_history(profile, [{"role": "user", "content": "hello meta"}], session_name="default")
        
        # Verify metadata has user_profile
        full_data = self.manager.get_full_data(profile, session_name="default")
        self.assertEqual(full_data["metadata"].get("user_profile"), "Aiko.json")

    @patch('engines.config.update_settings')
    @patch('engines.config.get_setting')
    def test_get_filename_fallback_and_setting_update(self, mock_get_setting, mock_update_settings):
        profile = "FallbackProfile"
        # Return non-existent session
        mock_get_setting.return_value = "nonexistent_session"
        
        # Calling get_filename or using it should fallback to default and update setting
        filename = self.manager._get_filename(profile, session_name=None)
        
        # The filename should point to default
        self.assertTrue(filename.endswith("default_history.json"))
        # update_settings should be called to update "current_history_session" to "default" and "session_FallbackProfile" to "default"
        mock_update_settings.assert_called_once_with({
            "current_history_session": "default",
            "session_FallbackProfile": "default"
        })

if __name__ == "__main__":
    unittest.main()

