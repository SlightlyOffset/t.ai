import unittest
import os
import json
from engines.memory_v2 import HistoryManager

class TestMemoryRolling(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_history_rolling"
        self.manager = HistoryManager(history_dir=self.test_dir)
        self.profile_name = "test_rolling"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_save_and_load_memory_core(self):
        history = [{"role": "user", "content": "hello"}]
        # These methods don't exist yet, so this test should fail if I try to use them,
        # OR I can check the get_full_data output.
        self.manager.save_history(self.profile_name, history, memory_core="Old summary", last_summarized_index=5)
        
        data = self.manager.get_full_data(self.profile_name)
        self.assertEqual(data["metadata"].get("memory_core"), "Old summary")
        self.assertEqual(data["metadata"].get("last_summarized_index"), 5)

    def test_getter_setter_memory_core(self):
        # Initial state should be defaults
        self.assertEqual(self.manager.get_memory_core(self.profile_name), "")
        self.assertEqual(self.manager.get_last_summarized_index(self.profile_name), 0)
        
        # Set new values
        self.manager.update_memory_core(self.profile_name, "New summary", 10)
        
        # Verify
        self.assertEqual(self.manager.get_memory_core(self.profile_name), "New summary")
        self.assertEqual(self.manager.get_last_summarized_index(self.profile_name), 10)

if __name__ == "__main__":
    unittest.main()
