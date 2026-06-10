import unittest
import os
import sys
import json
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.config import get_setting
from engines.utilities import redact_pii

class TestConfigSecurity(unittest.TestCase):
    def test_remote_url_validation(self):
        # Setup: Create a temporary settings file
        temp_settings = "settings_test.json"
        if os.path.exists(temp_settings):
            os.remove(temp_settings)
            
        with open(temp_settings, "w") as f:
            json.dump({
                "remote_llm_url": "http://insecure.com",
                "remote_tts_url": "https://secure.com"
            }, f)
            
        # Patch SETTINGS_FILE in engines.config
        import engines.config
        original_settings_file = engines.config.SETTINGS_FILE
        engines.config.SETTINGS_FILE = temp_settings
        
        # Capture stdout
        mock_stdout = StringIO()
        original_stdout = sys.stdout
        sys.stdout = mock_stdout
        
        try:
            # Insecure URL should return None and print a warning
            self.assertIsNone(get_setting("remote_llm_url"))
            output = mock_stdout.getvalue()
            self.assertIn("[SECURITY WARNING]", output)
            
            # Secure URL should be returned
            self.assertEqual(get_setting("remote_tts_url"), "https://secure.com")
            
        finally:
            sys.stdout = original_stdout
            engines.config.SETTINGS_FILE = original_settings_file
            if os.path.exists(temp_settings):
                os.remove(temp_settings)

    def test_pii_redaction(self):
        text = "Contact me at user@example.com or 192.168.1.1. My name is Alice."
        sanitized = redact_pii(text, user_name="Alice")
        
        self.assertNotIn("user@example.com", sanitized)
        self.assertIn("[EMAIL]", sanitized)
        self.assertNotIn("192.168.1.1", sanitized)
        self.assertIn("[IP_ADDR]", sanitized)
        self.assertNotIn("Alice", sanitized)
        self.assertIn("[USER]", sanitized)
        self.assertIn("Contact me at", sanitized)

if __name__ == "__main__":
    unittest.main()
