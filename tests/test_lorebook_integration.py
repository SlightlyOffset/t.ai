import unittest
from unittest.mock import patch, MagicMock
import os
import json
from engines.responses import get_respond_stream

class TestLorebookIntegration(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "name": "TestAI",
            "llm_model": "test-model",
            "relationship_score": 0
        }
        self.user_input = "Tell me about the tavern."
        
        # Create a temporary lorebook
        os.makedirs("lorebooks", exist_ok=True)
        self.lore_path = "lorebooks/default.json"
        self.lore_data = {
            "entries": [
                {
                    "id": "1",
                    "keys": ["tavern"],
                    "content": "The tavern is a place of lore.",
                    "enabled": True,
                    "insertion_order": 50
                }
            ]
        }
        with open(self.lore_path, "w") as f:
            json.dump(self.lore_data, f)

    def tearDown(self):
        if os.path.exists(self.lore_path):
            os.remove(self.lore_path)
        if os.path.exists("lorebooks") and not os.listdir("lorebooks"):
            os.rmdir("lorebooks")

    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_lore_injection_in_respond_stream(self, mock_get_setting, mock_memory_manager, mock_ollama_chat):
        # Setup mocks
        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15
        }.get(key, default)
        
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Test Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.return_value = []
        
        # Mock ollama stream
        mock_ollama_chat.return_value = [{"message": {"content": "Response"}}]

        # Run get_respond_stream
        # We need to exhaust the generator
        list(get_respond_stream(self.user_input, self.profile, history_profile_name="test_profile"))

        # Verify that build_system_prompt was (indirectly) called with lore
        # We check the FIRST call to ollama.chat (the stream)
        args, kwargs = mock_ollama_chat.call_args_list[0]
        system_msg = kwargs['messages'][0]['content']
        
        self.assertIn("[WORLD INFO / LORE]", system_msg)
        self.assertIn("The tavern is a place of lore.", system_msg)

if __name__ == "__main__":
    unittest.main()
