import unittest
from unittest.mock import MagicMock, patch
from engines.responses import get_respond_stream

class TestRollingInjection(unittest.TestCase):
    @patch('engines.responses.memory_manager')
    @patch('engines.responses.ollama.chat')
    @patch('engines.responses.get_setting')
    @patch('engines.responses.build_system_prompt')
    def test_context_injection(self, mock_build_prompt, mock_get_setting, mock_ollama_chat, mock_memory_manager):
        # Mock settings
        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "llama3",
            "memory_limit": 15,
            "interaction_mode": "rp"
        }.get(key, default)
        
        # Mock memory data with a Memory Core
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {
                "current_scene": "The woods",
                "memory_core": "PREVIOUS EVENTS: The hero found a sword."
            }
        }
        mock_memory_manager.load_history.return_value = []
        
        # Mock ollama stream
        mock_ollama_chat.return_value = []
        
        profile = {"name": "TestBot"}
        
        # Run generator to trigger logic
        list(get_respond_stream("Hi", profile, history_profile_name="test"))
        
        # Verify build_system_prompt was called with the memory core in extra_info or scene
        # Our implementation prepends it to scene_instruction which is passed as system_extra_info (or combined)
        # Wait, let's look at the code:
        # scene_instruction = f"{memory_core}\n\n{scene_instruction}"
        # system_content = build_system_prompt(..., system_extra_info)
        
        call_args = mock_build_prompt.call_args[0]
        extra_info = call_args[5] # system_extra_info is the 6th arg
        self.assertIn("PREVIOUS EVENTS: The hero found a sword.", extra_info)
        self.assertIn("CURRENT SCENE: The woods", extra_info)

if __name__ == "__main__":
    unittest.main()
