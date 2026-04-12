import unittest
from engines.app_commands import app_commands
import os

class TestAppCommandsLore(unittest.TestCase):
    def test_lore_reload_command(self):
        # Create a dummy lorebook file
        os.makedirs("lorebooks", exist_ok=True)
        with open("lorebooks/default.json", "w") as f:
            f.write("{}")
            
        success, messages = app_commands("//lore reload", suppress_output=True)
        self.assertTrue(success)
        self.assertIn("Lorebook reloaded successfully.", messages[0])

    def test_lore_invalid_subcommand(self):
        # app_commands returns True if the command DISPATCHER found the command,
        # but the command implementation itself might log an error.
        success, messages = app_commands("//lore invalid", suppress_output=True)
        self.assertTrue(success)
        self.assertIn("[ERROR] Unknown lore command", messages[0])

if __name__ == "__main__":
    unittest.main()
