import unittest
import os
import shutil
import json
from engines.app_commands import app_commands

class TestAppCommandsLore(unittest.TestCase):
    def setUp(self):
        # Setup a dedicated test environment for lorebook commands
        self.test_lore_dir = "test_lorebooks"
        os.makedirs(self.test_lore_dir, exist_ok=True)
        self.test_lore_path = os.path.join(self.test_lore_dir, "default.json")
        with open(self.test_lore_path, "w", encoding="UTF-8") as f:
            f.write("{}")
            
        # Temporarily mock the path or ensure the command uses a specific one
        # For this implementation, we'll just be careful to restore or use a side-effect
        # But for now, let's fix the test to NOT touch the real lorebooks/ directory
        # We'll use a patch for the file path if necessary, but since the command
        # currently has a hardcoded 'lorebooks/default.json', we'll have to be surgical.
        
        # Actually, let's fix the command to be more flexible first, 
        # but for this immediate fix, I will just make sure the test restores the file.
        if os.path.exists("lorebooks/default.json"):
            with open("lorebooks/default.json", "r", encoding="UTF-8") as f:
                self.original_content = f.read()
        else:
            self.original_content = None

    def tearDown(self):
        # Restore original content if we touched the real file
        if self.original_content is not None:
            os.makedirs("lorebooks", exist_ok=True)
            with open("lorebooks/default.json", "w", encoding="UTF-8") as f:
                f.write(self.original_content)
        
        if os.path.exists(self.test_lore_dir):
            shutil.rmtree(self.test_lore_dir)

    def test_lore_reload_command(self):
        # We ensure a file exists for the command to find
        os.makedirs("lorebooks", exist_ok=True)
        with open("lorebooks/default.json", "w", encoding="UTF-8") as f:
            f.write("{}")
            
        success, messages = app_commands("//lore reload", suppress_output=True)
        self.assertTrue(success)
        self.assertIn("Lorebook reloaded successfully.", messages[0])

    def test_lore_invalid_subcommand(self):
        success, messages = app_commands("//lore invalid", suppress_output=True)
        self.assertTrue(success)
        self.assertIn("[ERROR] Unknown lore command", messages[0])

if __name__ == "__main__":
    unittest.main()
