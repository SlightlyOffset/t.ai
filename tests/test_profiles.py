import unittest
import json
import os
from legacy.legacy_main import load_profile

class TestProfileValidation(unittest.TestCase):
    def setUp(self):
        self.test_profile_path = "test_xtts_profile.json"
        self.test_data = {
            "name": "Test Character",
            "preferred_tts_voice": "en-GB-SoniaNeural",
            "tts_engine": "xtts",
            "voice_clone_ref": "voices/test_ref.wav",
            "colors": {"text": "white", "label": "bright"}
        }
        with open(self.test_profile_path, "w") as f:
            json.dump(self.test_data, f)

    def tearDown(self):
        if os.path.exists(self.test_profile_path):
            os.remove(self.test_profile_path)

    def test_load_profile_contains_xtts_fields(self):
        profile = load_profile(self.test_profile_path)
        self.assertEqual(profile["tts_engine"], "xtts")
        self.assertEqual(profile["voice_clone_ref"], "voices/test_ref.wav")

    def test_profile_defaults(self):
        # Test loading a profile without the new fields
        legacy_path = "legacy_profile.json"
        with open(legacy_path, "w") as f:
            json.dump({"name": "Legacy"}, f)
        
        profile = load_profile(legacy_path)
        self.assertEqual(profile.get("tts_engine", "edge-tts"), "edge-tts")
        self.assertIsNone(profile.get("voice_clone_ref"))
        
        os.remove(legacy_path)

if __name__ == '__main__':
    unittest.main()
