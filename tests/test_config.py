
import unittest
import os
import json
from engines.config import get_setting, update_setting, SETTINGS_FILE

class TestConfig(unittest.TestCase):
    def setUp(self):
        # Backup existing settings
        self.backup_path = SETTINGS_FILE + ".bak"
        if os.path.exists(SETTINGS_FILE):
            os.replace(SETTINGS_FILE, self.backup_path)
        
        # Create a fresh settings file for testing
        self.test_settings = {
            "tts_enabled": True,
            "suppress_errors": False
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.test_settings, f)

    def tearDown(self):
        # Restore backup
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
        if os.path.exists(self.backup_path):
            os.replace(self.backup_path, SETTINGS_FILE)

    def test_get_setting_exists(self):
        val = get_setting("tts_enabled", False)
        self.assertTrue(val)

    def test_get_setting_default(self):
        # Key that doesn't exist
        val = get_setting("non_existent_key", "default_val")
        self.assertEqual(val, "default_val")

    def test_update_setting(self):
        success = update_setting("suppress_errors", True)
        self.assertTrue(success)
        
        # Verify it was saved
        val = get_setting("suppress_errors", False)
        self.assertTrue(val)

    def test_new_settings_initial_state(self):
        # Verify the new settings we expect are there (or have defaults)
        self.assertTrue(get_setting("tts_enabled", True))
        self.assertFalse(get_setting("suppress_errors", False))

    def test_update_settings(self):
        from engines.config import update_settings
        updates = {
            "tts_enabled": False,
            "suppress_errors": True,
            "new_custom_setting": "hello"
        }
        success = update_settings(updates)
        self.assertTrue(success)
        
        # Verify they were saved
        self.assertFalse(get_setting("tts_enabled", True))
        self.assertTrue(get_setting("suppress_errors", False))
        self.assertEqual(get_setting("new_custom_setting"), "hello")

    def test_load_settings_corrupted_fallback(self):
        from engines.config import load_settings
        # Move real backup temporarily
        real_bak = self.backup_path + ".real"
        if os.path.exists(self.backup_path):
            os.replace(self.backup_path, real_bak)

        try:
            # 1. Corrupt primary settings file
            with open(SETTINGS_FILE, "w") as f:
                f.write("invalid json contents")

            # 2. Write a test backup file
            test_bak = {"tts_enabled": False, "suppress_errors": True}
            with open(self.backup_path, "w") as f:
                json.dump(test_bak, f)

            # 3. Call load_settings
            result = load_settings()
            self.assertEqual(result.get("tts_enabled"), False)
            self.assertEqual(result.get("suppress_errors"), True)

            # 4. Verify primary settings file was healed/restored
            with open(SETTINGS_FILE, "r") as f:
                healed = json.load(f)
            self.assertEqual(healed.get("tts_enabled"), False)
        finally:
            # Cleanup test backup
            if os.path.exists(self.backup_path):
                os.remove(self.backup_path)
            # Restore real backup
            if os.path.exists(real_bak):
                os.replace(real_bak, self.backup_path)

if __name__ == "__main__":
    unittest.main()
